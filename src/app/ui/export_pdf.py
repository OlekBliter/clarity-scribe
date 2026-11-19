"""Facade-view dictionaries to paginated A4 PDF; call on the GUI thread."""
from __future__ import annotations

from html import escape
from pathlib import Path
import re

from PySide6.QtCore import QIODevice, QMarginsF, QRectF, QSaveFile, QSizeF, QUrl, Qt
from PySide6.QtGui import (QAbstractTextDocumentLayout, QColor, QFont, QImage,
                          QPainter, QPalette, QPageSize, QPdfWriter, QTextDocument)
from PySide6.QtWidgets import QApplication, QFileDialog
from . import strings as S


def ask_save_path(parent, default_name) -> str | None:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', default_name).rstrip(' .')
    path, _ = QFileDialog.getSaveFileName(parent, S.PDF_SAVE_TITLE, name, S.PDF_FILTER)
    if not path:
        return None
    return path if path.lower().endswith('.pdf') else path + '.pdf'


def _text(value) -> str:
    if value is None or value == '':
        value = S.PDF_MISSING
    elif isinstance(value, bool):
        value = S.MEDCARD_YES if value else S.MEDCARD_NO
    elif isinstance(value, (dict, list)):
        value = '\n'.join(f'{k}: {v}' for k, v in value.items()) if isinstance(value, dict) else '\n'.join(map(str, value))
    return escape(str(value)).replace('\n', '<br>')


def _p(value) -> str:
    return '<p>' + _text(value) + '</p>'


def _table(headers, rows) -> str:
    head = ''.join('<th bgcolor="#E5F3F3">'+_text(h)+'</th>' for h in headers)
    body = ''.join('<tr>'+''.join('<td>'+_text(v)+'</td>' for v in row)+'</tr>' for row in rows)
    return '<table width="100%" border="1" cellspacing="0" cellpadding="6"><thead><tr>'+head+'</tr></thead>'+body+'</table>'


def _sources(items) -> str:
    if not items:
        return ''
    return '<h4>'+S.PDF_SOURCES+'</h4>'+''.join(
        '<p><b style="color:#107E83">['+_text(s.get('time'))+']</b> '+_text(s.get('quote'))+'</p>' for s in items)


def _header(data, title) -> str:
    rows = [(data.get('patient_name'), data.get('number'), data.get('date'))]
    status = data.get('status', data.get('badge'))
    return ('<p><img src="export-logo" width="135" height="33"></p><h1>'+title+'</h1>'
            + _table((S.PDF_PATIENT, S.PDF_SESSION, S.PDF_DATE), rows)
            + _p(S.PDF_STATUS+': '+(data.get('status_label') or S.MEDCARD_STATUSES.get(status, status or S.PDF_MISSING))))


def _direction(item) -> str:
    direction = item.get('arrow', item.get('direction'))
    if direction:
        return S.PDF_DIRECTIONS.get(direction, direction)
    return S.PDF_DIRECTIONS['stable'] if item.get('value') is not None and item.get('baseline') is not None else S.PDF_MISSING


def _soap_html(data) -> str:
    parts = [_header(data, S.PDF_SOAP_TITLE)]
    for key, letter, title, english in S.PDF_SECTIONS:
        parts.append(f'<h2><span style="color:#107E83">{letter}</span> &nbsp; {title} <small>{english}</small></h2>')
        if key == 'plan':
            for item in data.get('plan', []):
                label = S.PLAN_ORIGINS.get(item.get('origin'), (S.PLAN_UNKNOWN, 'neutral'))[0]
                parts.append(_p(item.get('text'))+'<p style="color:#107E83">'+_text(label)+'</p>')
                parts.append(_sources(item.get('sources', [])))
            if not data.get('plan'):
                parts.append(_p(None))
            continue
        section = data.get(key) or {}
        parts.append(_p(section.get('text')))
        if key == 'objective' and section.get('chips'):
            parts.append('<h3>'+S.PDF_BIOMARKERS+'</h3>')
            parts.append(_table(S.PDF_METRIC_HEADERS, [
                (S.METRIC_TITLES.get(c.get('metric'), c.get('metric')), c.get('value'), c.get('baseline'), _direction(c))
                for c in section['chips']]))
        parts.append(_sources(section.get('sources', [])))
    parts.append('<p style="margin-top:24px">'+S.PDF_DOCTOR+' &nbsp;&nbsp; '+S.PDF_SIGNATURE+'</p>')
    return ''.join(parts)


def export_soap(data: dict, path: str):
    _write_pdf(_soap_html(data), path, S.PDF_SOAP_TITLE)


def export_card(data: dict, path: str):
    parts = [_header(data, S.PDF_CARD_TITLE), '<h2>'+S.PDF_CONTACTS+'</h2>']
    parts.extend(_p(S.MEDCARD_CONTACTS.get(k, k)+': '+str(v if v is not None else S.PDF_MISSING))
                 for k, v in data.get('contacts', {}).items())
    for field in data.get('fields', []):
        key = field.get('field_id', '')
        parts.extend(('<h2>'+_text(S.MEDCARD_FIELDS.get(key, key))+'</h2>', _p(S.MEDCARD_RISKS.get(field.get("value"), field.get("value")) if key == "hypotheses.risk" else field.get("value")),
                      _sources(field.get('sources', []))))
        if field.get('contradiction_text'):
            parts.append(_p(field['contradiction_text']))
    _write_pdf(''.join(parts), path, S.PDF_CARD_TITLE)


def export_dynamics(data: dict, path: str):
    parts = ['<h1>'+S.PDF_DYNAMICS_TITLE+'</h1>']
    if data.get('patient_name'):
        parts.append(_p(data['patient_name']))
    if not data.get('available'):
        parts.append(_p(S.DYNAMICS_EMPTY))
    else:
        parts.extend((_p(S.DYNAMICS_SESSIONS.format(sessions=data.get('sessions_label', ''))), _p(data.get('summary_text'))))
        for trend in data.get('trends', []):
            metric = trend.get('metric', '')
            parts.extend(('<h2>'+_text(S.DYNAMICS_METRIC_NAMES.get(metric, S.METRIC_TITLES.get(metric, metric)))+'</h2>',
                          _p(_direction(trend)), _p(S.DYNAMICS_SLOPE.format(value=trend['slope'])) if trend.get('slope') is not None else '',
                          _table((S.PDF_SESSION, S.PDF_VALUE), [(v.get('session_number'), v.get('value')) for v in trend.get('values', [])])))
    _write_pdf(''.join(parts), path, S.PDF_DYNAMICS_TITLE)


def _write_pdf(html: str, path: str, title: str) -> None:
    if QApplication.instance() is None:
        raise RuntimeError(S.PDF_NO_GUI)
    device = QSaveFile(str(path))
    device.setDirectWriteFallback(False)
    if not device.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(device.errorString())
    painter = QPainter()
    try:
        writer = QPdfWriter(device)
        writer.setResolution(96)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(17, 16, 17, 16))
        writer.setTitle(title)
        writer.setCreator('ClarityScribe')
        width, height = writer.width(), writer.height()
        body_height = height - 32
        doc = QTextDocument()
        doc.setDefaultFont(QFont('DejaVu Sans', 10))
        doc.setDocumentMargin(0)
        doc.setDefaultStyleSheet('''body {color:#173D4C;} p {margin-top:7px; margin-bottom:9px;}
            h1 {font-size:25pt; color:#103747;} h2 {font-size:13pt; margin-top:20px; margin-bottom:9px; page-break-after:avoid;}
            h3,h4 {color:#107E83; page-break-after:avoid;} small {font-size:9pt; color:#586B77;}
            td,th {border-color:#D5E5E8; font-size:9pt;}''')
        logo = QImage(str(Path(__file__).parent / 'assets' / 'export_logo.png'))
        if not logo.isNull():
            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl('export-logo'), logo)
        doc.setHtml(html)
        doc.setPageSize(QSizeF(width, body_height))
        total = doc.pageCount()
        if not painter.begin(writer):
            raise OSError(S.PDF_WRITE_FAILED)
        # PaintContext inherits the application palette, including white text in dark mode.
        print_palette = QPalette()
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                     QPalette.ColorRole.ButtonText):
            print_palette.setColor(role, QColor('#173D4C'))
        for role in (QPalette.ColorRole.Base, QPalette.ColorRole.Window):
            print_palette.setColor(role, QColor('#FFFFFF'))
        for page in range(total):
            if page and not writer.newPage():
                raise OSError(S.PDF_WRITE_FAILED)
            painter.save()
            painter.setClipRect(QRectF(0, 0, width, body_height))
            painter.translate(0, -page * body_height)
            context = QAbstractTextDocumentLayout.PaintContext()
            context.palette = print_palette
            context.clip = QRectF(0, page * body_height, width, body_height)
            doc.documentLayout().draw(painter, context)
            painter.restore()
            painter.setPen(QColor('#D5E5E8'))
            painter.drawLine(0, height - 24, width, height - 24)
            painter.setPen(QColor('#107E83'))
            painter.setFont(QFont('DejaVu Sans', 8))
            painter.drawText(QRectF(0, height - 21, width, 20), Qt.AlignmentFlag.AlignLeft, 'ClarityScribe')
            painter.drawText(QRectF(0, height - 21, width, 20), Qt.AlignmentFlag.AlignRight,
                             S.PDF_PAGE.format(page=page+1, total=total))
        if not painter.end():
            raise OSError(S.PDF_WRITE_FAILED)
        del writer
        if not device.commit():
            raise OSError(device.errorString())
    except Exception:
        if painter.isActive():
            painter.end()
        device.cancelWriting()
        raise
