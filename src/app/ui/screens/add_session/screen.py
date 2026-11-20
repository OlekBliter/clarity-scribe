"""Екран «Додати запис сесії» (макет 5).

Фасад:
    next_session_number(patient_id)             номер для поля «Номер сесії»
    add_session(patient_id, wav, "uk", "РРРР-ММ-ДД") -> session_id
    process_session(session_id, on_progress)    у PipelineWorker (довго, синхронно)
    get_processing_state(session_id)            стани етапів для StageList
    get_patient_profile(patient_id)             лише ім'я для хлібних крихт

Маршрут: ADD_SESSION(patient_id [, session_id]).
  без session_id: форма додавання запису;
  із session_id: екран обробки вже доданої сесії.

Екран обробки керується станом, а не прапорцями:
  працює        (власний прапорець воркера) етапи, кнопок немає;
  помилка       (state["error"]) етапи + текст помилки; «До профілю» і
                «Додати запис повторно»: реальний фасад не повторює збійний крок,
                а при новому add_session перезапускає останню незавершену
                сесію (той самий номер, новий файл і дата);
  завершено     «До профілю пацієнта»;
  перервано     (не працює, не помилка, не завершено, напр. застосунок
                перезапускали): «До профілю» і «Продовжити обробку»
                (process_session відновлює з наступного кроку).
У реальному фасаді етап «running» позначає перший незавершений, навіть коли
нічого не виконується, тому «працює» визначаємо лише власним прапорцем.

TODO (полірування): якщо лікар закриває застосунок під час обробки, попередити.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from src.app.ui import metrics, strings
from src.app.ui.errors import show_error
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import primary_button, secondary_button
from src.app.ui.widgets.drop_zone import DropZone
from src.app.ui.widgets.file_info import file_meta
from src.app.ui.widgets.stage_list import StageList
from src.app.ui.widgets.date_field import DateField
from src.app.workers.pipeline_worker import PipelineWorker
from src.app.ui.qt_helpers import fit_combo_popup
from src.app.ui.widgets.action_icon import ActionIcon

log = logging.getLogger(__name__)
_ISO_DATE = "yyyy-MM-dd"


class AddSessionScreen(BaseScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._patient_id: str | None = None
        self._session_id: str | None = None
        self._worker: PipelineWorker | None = None
        self._pipeline_active = False  # від старту воркера до його сигналу (головний потік)
        self._state_request = 0        # щоб ігнорувати застарілі відповіді стану

        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)
        self._crumb = Breadcrumb()
        title = QLabel(strings.ADD_TITLE)
        title.setObjectName("ScreenTitle")
        top = QHBoxLayout()
        top.setSpacing(metrics.SPACING)
        back = ActionIcon("back", strings.BACK)
        back.clicked.connect(self.router.back)
        top.addWidget(back)
        top.addWidget(self._crumb, alignment=Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        root.addLayout(top)
        root.addWidget(title)

        # «Сесія №N» над обома колонками, щоб зона файла й етапи стояли на одному рівні
        self._number = QLabel()
        self._number.setObjectName("SectionTitle")
        root.addWidget(self._number)

        # Адаптивно (сітка з 4 клітинок): у широкому вікні
        #   [ зона файла ][ етапи ]   і нижче   [ мова · дата ][ кнопки ]  (кнопки на лінії полів),
        # у вужчому все в одну колонку. Прокрутка лише вертикальна.
        content = QWidget()
        self._wide = True
        self._form_hidden = False   # відкрито готову/перервану сесію: лише етапи
        self._side_visible = False
        self._grid = QGridLayout(content)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(metrics.SPACING)
        self._build_form()
        self._build_side()
        self._relayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------ адаптивність
    def _relayout(self) -> None:
        g = self._grid
        top, bottom = Qt.AlignmentFlag.AlignTop, Qt.AlignmentFlag.AlignBottom
        for w in (self._drop, self._controls, self._stages, self._actions):
            g.removeWidget(w)
        for i in range(5):
            g.setRowStretch(i, 0)
        for i in range(2):
            g.setColumnStretch(i, 0)
            g.setColumnMinimumWidth(i, 0)
        panel = metrics.STAGES_PANEL_WIDTH
        if self._wide and not self._form_hidden:
            g.addWidget(self._drop, 0, 0, alignment=top)
            g.addWidget(self._stages, 0, 1, alignment=top)
            g.addWidget(self._controls, 1, 0, alignment=bottom)
            g.addWidget(self._actions, 1, 1, alignment=bottom)
            g.setColumnStretch(0, 1)
            g.setColumnMinimumWidth(0, metrics.ADD_FORM_MIN_WIDTH)
            g.setColumnMinimumWidth(1, panel if self._side_visible else 0)
        elif self._wide:
            g.addWidget(self._stages, 0, 0, alignment=top)
            g.addWidget(self._actions, 1, 0, alignment=top)
            g.setColumnMinimumWidth(0, panel)
            g.setColumnStretch(1, 1)
        else:
            g.addWidget(self._drop, 0, 0, alignment=top)
            g.addWidget(self._controls, 1, 0, alignment=top)
            g.addWidget(self._stages, 2, 0, alignment=top)
            g.addWidget(self._actions, 3, 0, alignment=top)
            g.setColumnStretch(0, 1)
        g.setRowStretch(4, 1)
        for w in (self._stages, self._actions):
            if self._wide:
                w.setFixedWidth(panel)
            else:
                w.setMinimumWidth(0)
                w.setMaximumWidth(16777215)
        QTimer.singleShot(0, self._sync_drop_height)

    def _update_layout_mode(self) -> None:
        need = (metrics.ADD_FORM_MIN_WIDTH + metrics.SPACING + metrics.STAGES_PANEL_WIDTH
                + 2 * metrics.CONTENT_MARGIN)
        wide = self.width() >= need
        if wide != self._wide:
            self._wide = wide
            self._relayout()

    def _sync_drop_height(self) -> None:
        """Зона файла такої ж висоти, як картка етапів, коли вони стоять поруч."""
        if self._wide and self._side_visible and not self._form_hidden:
            self._drop.match_height(self._stages.sizeHint().height())
        else:
            self._drop.match_height(0)

    def _set_side_visible(self, visible: bool) -> None:
        self._side_visible = visible
        self._stages.setVisible(visible)
        self._actions.setVisible(visible)
        self._relayout()

    def _set_form_hidden(self, hidden: bool) -> None:
        self._form_hidden = hidden
        self._drop.setVisible(not hidden)
        self._controls.setVisible(not hidden)
        self._relayout()

    def _set_form_enabled(self, enabled: bool) -> None:
        self._drop.setEnabled(enabled)
        self._controls.setEnabled(enabled)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._update_layout_mode()

    def _build_side(self) -> None:
        """Етапи обробки та блок дій (підказка + кнопки, вертикально на всю ширину)."""
        self._stages = StageList()
        self._actions = QWidget()
        col = QVBoxLayout(self._actions)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(metrics.SPACING)
        self._hint = QLabel(strings.ADD_UNFINISHED_HINT)
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)
        col.addWidget(self._hint)
        self._leave = secondary_button(strings.ADD_LEAVE)
        self._repeat = primary_button(strings.ADD_REPEAT)      # після помилки
        self._continue = primary_button(strings.ADD_CONTINUE)  # після переривання
        self._to_profile = primary_button(strings.ADD_TO_PROFILE)
        self._leave.clicked.connect(self._open_profile)
        self._to_profile.clicked.connect(self._open_profile)
        self._repeat.clicked.connect(self._show_form_mode)
        self._continue.clicked.connect(self._start_pipeline)
        for btn in (self._repeat, self._continue, self._to_profile, self._leave):
            col.addWidget(btn)  # головна над другорядною «До профілю»
        self._stages.hide()
        self._actions.hide()

    # ------------------------------------------------------------ верстка форми
    def _build_form(self) -> None:
        # Зона файла: порожня велика або (після додавання) компактна картка з відомостями
        self._drop = DropZone()
        self._drop.file_selected.connect(self._on_file_selected)
        self._drop.file_cleared.connect(self._on_file_cleared)
        self._drop.file_rejected.connect(lambda text: show_error(self, text))

        self._lang = QComboBox()
        self._lang.addItem(strings.ADD_LANG_UK, "uk")
        fit_combo_popup(self._lang)
        self._lang.currentIndexChanged.connect(lambda _i: self._update_meta())
        self._date = DateField()

        # Рядок полів: мова, дата, а справа (лише в режимі форми) «Почати обробку»
        # на одній лінії з полями; під нею, поки вона вимкнена, пояснення чому.
        self._controls = QWidget()
        grid = QGridLayout(self._controls)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(metrics.SPACING)
        grid.setVerticalSpacing(metrics.SPACING_SMALL)
        for column, (caption, widget) in enumerate(((strings.ADD_LANGUAGE, self._lang),
                                                    (strings.ADD_DATE, self._date))):
            label = QLabel(caption)
            label.setObjectName("Muted")
            grid.addWidget(label, 0, column)
            grid.addWidget(widget, 1, column)
        grid.setColumnStretch(2, 1)
        self._start = primary_button(strings.ADD_START)
        self._start.clicked.connect(self._on_start)
        grid.addWidget(self._start, 1, 3, alignment=Qt.AlignmentFlag.AlignRight)
        self._start_hint = QLabel(strings.ADD_START_HINT)
        self._start_hint.setObjectName("Muted")
        grid.addWidget(self._start_hint, 2, 2, 1, 2, alignment=Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------ режими
    def on_open(self, **params: Any) -> None:
        self._patient_id = params["patient_id"]
        self.call(self.facade.get_patient_profile, self._patient_id,
                  on_success=lambda p: self._crumb.set_path(
                      [strings.NAV_PATIENTS, p["name"], strings.ADD_CRUMB]))
        if self._is_running():
            # Обробка йде: показуємо її прогрес (одночасно обробляється одна сесія).
            self._show_progress_mode(resumed=self._form_hidden)
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
        self._drop.clear()
        self._date.setDate(QDate.currentDate())
        self._stages.reset()
        self._hide_actions()
        self._start.show()
        self._form_hidden = False
        self._drop.show()
        self._controls.show()
        self._set_side_visible(False)
        self._set_form_enabled(True)
        self._update_start()
        self._number.setText("")
        self.call(self.facade.next_session_number, self._patient_id,
                  on_success=lambda n: self._number.setText(strings.ADD_NUMBER_FMT.format(number=n)))

    def _show_progress_mode(self, resumed: bool = False) -> None:
        """Свіжий запуск: форма із запитом лишається ліворуч (вимкнена), етапи праворуч.
        Відкрита готова/перервана сесія: форми немає, лише етапи."""
        self._set_form_enabled(False)
        if resumed:
            self._number.setText("")
        self._start.hide()
        self._start_hint.hide()
        self._hide_actions()
        self._form_hidden = resumed
        self._drop.setVisible(not resumed)
        self._controls.setVisible(not resumed)
        self._set_side_visible(True)

    def _hide_actions(self) -> None:
        for widget in (self._hint, self._leave, self._repeat, self._continue, self._to_profile):
            widget.hide()

    def _on_file_selected(self, _path: str) -> None:
        self._update_meta()
        self._update_start()

    def _on_file_cleared(self) -> None:
        self._update_start()

    def _update_meta(self) -> None:
        if self._drop.path:
            self._drop.set_meta(file_meta(self._drop.path, self._lang.currentText()))

    def _update_start(self) -> None:
        has_file = self._drop.path is not None
        self._start.setEnabled(has_file)
        self._start_hint.setVisible(not has_file)

    def _is_running(self) -> bool:
        return self._pipeline_active or (self._worker is not None and self._worker.isRunning())

    # ------------------------------------------------------------------ запуск
    def _on_start(self) -> None:
        path = self._drop.path
        if not path or self._patient_id is None:
            return
        self._set_form_enabled(False)
        self.call(self.facade.add_session, self._patient_id, path,
                  self._lang.currentData(), self._date.date().toString(_ISO_DATE),
                  on_success=self._on_session_added, on_error=self._on_add_failed)

    def _on_session_added(self, session_id: str) -> None:
        self._session_id = session_id
        self._show_progress_mode()
        self._start_pipeline()

    def _on_add_failed(self, exc: BaseException) -> None:
        show_error(self, exc)
        self._set_form_enabled(True)  # сесію не створено: форма лишається як була

    def _start_pipeline(self) -> None:
        """Запускає (або повторює) обробку поточної сесії у фоновому потоці."""
        if self._session_id is None or self._is_running():
            return
        self._pipeline_active = True
        self._hide_actions()
        self._worker = PipelineWorker(self.facade, self._session_id, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        self._refresh_state()

    # ---------------------------------------------------- прогрес і завершення
    def _on_progress(self, _step: str, _state: str) -> None:
        self._refresh_state()  # назви кроків не розбираємо: беремо стан із фасаду

    def _on_succeeded(self) -> None:
        self._pipeline_active = False
        self._refresh_state()
        toast = getattr(self.window(), "toast", None)
        if toast is not None:
            toast.show_message(strings.ADD_DONE_TOAST)

    def _on_failed(self, exc: BaseException) -> None:
        self._pipeline_active = False
        show_error(self, exc)
        self._refresh_state()  # стан «помилка» покаже кнопку «Повторити обробку»

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
        self._apply_actions(state)
        QTimer.singleShot(0, self._sync_drop_height)

    def _apply_actions(self, state: dict) -> None:
        """Підказка й кнопки залежать лише від стану обробки (див. docstring модуля)."""
        running = self._is_running()
        self._stages.set_footer_visible(running)
        self._hide_actions()
        if running:
            return
        if state["finished"]:
            self._to_profile.show()
            return
        self._leave.show()
        if state["error"]:
            self._hint.setText(strings.ADD_FAILED_HINT)
            self._repeat.show()
        else:
            self._hint.setText(strings.ADD_UNFINISHED_HINT)
            self._continue.show()
        self._hint.show()

    def _open_profile(self) -> None:
        self.router.go(Route.PATIENT_PROFILE, patient_id=self._patient_id)
