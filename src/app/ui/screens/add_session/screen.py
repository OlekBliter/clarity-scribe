"""Екран «Додати запис сесії» (макет 5).

Фасад:
    next_session_number(patient_id)             номер для поля «Номер сесії»
    add_session(patient_id, wav, "uk", "РРРР-ММ-ДД") -> session_id
    process_session(session_id, on_progress)    у PipelineWorker (довго, синхронно)
    get_processing_state(session_id)            стани етапів для StageList
    get_patient_profile(patient_id)             лише ім'я для хлібних крихт

Маршрут: ADD_SESSION(patient_id [, session_id]).
  без session_id: форма додавання запису;
  із session_id: показ прогресу вже доданої сесії (лікар повернувся на екран
  або застосунок перезапускали).

Кнопки «повторити» немає (рішення плану): після збою форма знову активна,
лікар додає запис ще раз, і фасад запускає обробку з нуля з тим самим номером.

TODO (полірування): якщо лікар закриває застосунок під час обробки, попередити.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit,
                               QVBoxLayout, QWidget)

from src.app.ui import metrics, strings
from src.app.ui.errors import show_error
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import primary_button, secondary_button
from src.app.ui.widgets.drop_zone import DropZone
from src.app.ui.widgets.stage_list import StageList
from src.app.ui.widgets.date_field import DateField
from src.app.workers.pipeline_worker import PipelineWorker
from src.app.ui.qt_helpers import fit_combo_popup

log = logging.getLogger(__name__)
_ISO_DATE = "yyyy-MM-dd"


class AddSessionScreen(BaseScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._patient_id: str | None = None
        self._session_id: str | None = None
        self._worker: PipelineWorker | None = None
        self._resumed = False          # екран відкрито для вже доданої сесії
        self._state_request = 0        # щоб ігнорувати застарілі відповіді стану

        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)
        self._crumb = Breadcrumb()
        title = QLabel(strings.ADD_TITLE)
        title.setObjectName("ScreenTitle")
        root.addWidget(self._crumb)
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(metrics.SPACING)
        body.addWidget(self._build_form(), stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        self._stages = StageList()
        self._stages.setFixedWidth(metrics.STAGES_PANEL_WIDTH)
        body.addWidget(self._stages, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(body)

        self._hint = QLabel(strings.ADD_RESUMED_HINT)
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        after = QHBoxLayout()
        self._to_profile = primary_button(strings.ADD_TO_PROFILE)
        self._again = secondary_button(strings.ADD_AGAIN)
        self._to_profile.clicked.connect(self._open_profile)
        self._again.clicked.connect(self._show_form_mode)
        after.addWidget(self._to_profile)
        after.addWidget(self._again)
        after.addStretch(1)
        root.addLayout(after)
        root.addStretch(1)

    # ------------------------------------------------------------ верстка форми
    def _build_form(self) -> QWidget:
        self._form = QWidget()
        col = QVBoxLayout(self._form)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(metrics.SPACING)

        self._drop = DropZone()
        self._drop.file_selected.connect(lambda _p: self._update_start())
        self._drop.file_cleared.connect(self._update_start)
        self._drop.file_rejected.connect(lambda text: show_error(self, text))
        col.addWidget(self._drop)

        self._lang = QComboBox()
        self._lang.addItem(strings.ADD_LANG_UK, "uk")
        fit_combo_popup(self._lang)
        self._number = QLineEdit()
        self._number.setReadOnly(True)
        self._date = DateField()
        fields = QHBoxLayout()
        fields.setSpacing(metrics.SPACING)
        for caption, widget in ((strings.ADD_LANGUAGE, self._lang),
                                (strings.ADD_NUMBER, self._number),
                                (strings.ADD_DATE, self._date)):
            cell = QVBoxLayout()
            label = QLabel(caption)
            label.setObjectName("Muted")
            cell.addWidget(label)
            cell.addWidget(widget)
            fields.addLayout(cell)
        col.addLayout(fields)

        self._start = primary_button(strings.ADD_START)
        self._start.clicked.connect(self._on_start)
        col.addWidget(self._start, alignment=Qt.AlignmentFlag.AlignLeft)
        return self._form

    # ------------------------------------------------------------------ режими
    def on_open(self, **params: Any) -> None:
        self._patient_id = params["patient_id"]
        self.call(self.facade.get_patient_profile, self._patient_id,
                  on_success=lambda p: self._crumb.set_path(
                      [strings.NAV_PATIENTS, p["name"], strings.ADD_CRUMB]))
        if self._is_running():
            # Обробка йде: показуємо її прогрес (одночасно обробляється одна сесія).
            self._show_progress_mode(resumed=False)
            self._refresh_state()
            return
        session_id = params.get("session_id")
        if session_id:
            self._session_id = session_id
            self._show_progress_mode(resumed=True)
            self._refresh_state()
        else:
            self._show_form_mode()

    def _show_form_mode(self) -> None:
        self._session_id = None
        self._resumed = False
        self._drop.clear()
        self._date.setDate(QDate.currentDate())
        self._stages.reset()
        self._stages.hide()
        self._hint.hide()
        self._to_profile.hide()
        self._again.hide()
        self._form.show()
        self._form.setEnabled(True)
        self._update_start()
        self.call(self.facade.next_session_number, self._patient_id,
                  on_success=lambda n: self._number.setText(str(n)))

    def _show_progress_mode(self, resumed: bool) -> None:
        self._resumed = resumed
        self._stages.show()
        self._form.setVisible(not resumed)
        self._form.setEnabled(False)
        self._hint.hide()
        self._to_profile.hide()
        self._again.hide()

    def _update_start(self) -> None:
        self._start.setEnabled(self._drop.path is not None)

    def _is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    # ------------------------------------------------------------------ запуск
    def _on_start(self) -> None:
        path = self._drop.path
        if not path or self._patient_id is None:
            return
        self._form.setEnabled(False)
        self.call(self.facade.add_session, self._patient_id, path,
                  self._lang.currentData(), self._date.date().toString(_ISO_DATE),
                  on_success=self._on_session_added, on_error=self._on_add_failed)

    def _on_session_added(self, session_id: str) -> None:
        self._session_id = session_id
        self._show_progress_mode(resumed=False)
        self._worker = PipelineWorker(self.facade, session_id, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        self._refresh_state()

    def _on_add_failed(self, exc: BaseException) -> None:
        show_error(self, exc)
        self._form.setEnabled(True)

    # ---------------------------------------------------- прогрес і завершення
    def _on_progress(self, _step: str, _state: str) -> None:
        self._refresh_state()  # назви кроків не розбираємо: беремо стан із фасаду

    def _on_succeeded(self) -> None:
        self._refresh_state()
        self._to_profile.show()
        toast = getattr(self.window(), "toast", None)
        if toast is not None:
            toast.show_message(strings.ADD_DONE_TOAST)

    def _on_failed(self, exc: BaseException) -> None:
        show_error(self, exc)
        self._refresh_state()
        self._form.setEnabled(True)  # лікар додає запис ще раз

    def _refresh_state(self) -> None:
        if self._session_id is None:
            return
        self._state_request += 1
        rid = self._state_request
        self.call(self.facade.get_processing_state, self._session_id,
                  on_success=lambda state: self._apply_state(state, rid),
                  on_error=lambda exc: log.warning("get_processing_state: %s", exc))

    def _apply_state(self, state: dict, rid: int) -> None:
        if rid != self._state_request:
            return
        self._stages.set_states(state["stages"])
        self._stages.set_error(state["error"])
        if self._resumed:
            unfinished = not state["finished"]
            self._hint.setVisible(unfinished)
            self._again.setVisible(unfinished)
            self._to_profile.setVisible(state["finished"])

    def _open_profile(self) -> None:
        self.router.go(Route.PATIENT_PROFILE, patient_id=self._patient_id)
