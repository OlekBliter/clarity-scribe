"""Усі тексти інтерфейсу. У віджетах рядки не пишемо, лише беремо звідси.

Кожен розробник додає рядки ТІЛЬКИ у свою секцію (нижче), щоб не було
merge-конфліктів. Назви: ЕКРАН_ПРИЗНАЧЕННЯ, наприклад SESSION_EXPORT_NOTE.
"""

# --- Спільне (змінює лише тімлід) ---
APP_NAME = "ClarityScribe"
NAV_PATIENTS = "Пацієнти"
NAV_ARCHIVE = "Архів"
NAV_SETTINGS = "Налаштування"
LOCAL_DATA_NOTE = "Дані зберігаються локально на цьому комп'ютері"
NO_NAME = "Без імені"
BACK = "Назад"
SAVE = "Зберегти"
CANCEL = "Скасувати"
ERROR_GENERIC = "Сталася помилка. Спробуйте ще раз"
PLACEHOLDER_HINT = "Екран у розробці"

# Бейджі стану (значення badge з фасаду: review / approved / processing / error)
BADGE_REVIEW = "Чекає на перегляд"
BADGE_APPROVED = "Підтверджено"
BADGE_PROCESSING = "Обробка запису…"
BADGE_ERROR = "Помилка обробки"

# --- Лідер: Пацієнти, Профіль, Додати сесію ---
PATIENTS_TITLE = "Пацієнти"
PATIENTS_SEARCH_PLACEHOLDER = "Пошук за ім'ям"
PATIENTS_ADD = "Додати пацієнта"
PATIENTS_EMPTY = "Пацієнтів не знайдено"
PROFILE_ADD_SESSION = "Додати сесію"
PROFILE_CARD = "Медкартка"
PROFILE_DYNAMICS = "Трекінг динаміки"
PROFILE_SESSIONS = "Сесії"
SESSION_ROW_TITLE = "Сесія {number} • {date}"
STAGES_TITLE = "Обробка запису"
STAGES_FOOTER = "Готову нотатку знайдете в профілі пацієнта"
STAGE_TITLES = {
    "transcription": "Транскрибація",
    "anonymization": "Анонімізація тексту",
    "biomarkers": "Біомаркери голосу",
    "medical_card": "Медкартка (лише 1-ша сесія)",
    "soap": "SOAP-нотатка",
}
STAGE_STATE_DONE = "Готово"
STAGE_STATE_RUNNING = "Триває"
STAGE_STATE_PENDING = "Очікує"
STAGE_STATE_NOT_NEEDED = "Не потрібно"
STAGE_STATE_ERROR = "Помилка"

DROPZONE_TITLE = "Перетягніть двоканальний файл"
DROPZONE_HINT = ".wav · канал 0 — лікар, канал 1 — пацієнт"
DROPZONE_BUTTON = "Додати файл"
DROPZONE_CLEAR = "Скасувати"
DROPZONE_DIALOG_TITLE = "Оберіть аудіофайл"
DROPZONE_FILTER = "Аудіо"
DROPZONE_BAD_TYPE = "Підтримуються лише файли: {types}"
DROPZONE_FILE_FMT = "{name} ({size_mb:.1f} MB)"

#Для add_session
ADD_TITLE = "Додати запис сесії"
ADD_CRUMB = "Нова сесія"
ADD_LANGUAGE = "Мова запису"
ADD_LANG_UK = "Українська"
ADD_NUMBER = "Номер сесії"
ADD_DATE = "Дата сесії"
ADD_START = "Запустити обробку"
ADD_AGAIN = "Додати запис знову"
ADD_TO_PROFILE = "До профілю пацієнта"
ADD_DONE_TOAST = "Обробку завершено"
ADD_RESUMED_HINT = "Обробка цієї сесії не розпочалась. Додайте запис знову: обробка почнеться з нуля з тим самим номером."

# --- Кобильник: Екран сесії ---
SOURCE_TIME = "[{time}]"
TRANSCRIPT_SEARCH = "Пошук за текстом..."
TRANSCRIPT_SPEAKERS = {"DOCTOR": "Лікар", "PATIENT": "Пацієнт"}
TRANSCRIPT_ROW = "{time} {speaker}: «{text}»"
AUDIO_PLAY = "Відтворити"
AUDIO_PAUSE = "Пауза"
AUDIO_MUTE = "Вимкнути звук"
AUDIO_UNMUTE = "Увімкнути звук"
AUDIO_SPEED = "Швидкість відтворення"
AUDIO_VOLUME = "Гучність"
AUDIO_RATES = ((1.0, "1.0x"), (1.25, "1.25x"), (1.5, "1.5x"), (2.0, "2.0x"))
AUDIO_TIMESTAMP = "{minutes:02d}:{seconds:02d}"
AUDIO_TIME = "{current} / {total}"


# --- Лаврик: Медкартка, Динаміка ---
DYNAMICS_TITLE = "Трекінг динаміки"
DYNAMICS_PATIENT_TITLE = "Трекінг динаміки • {name}"
DYNAMICS_BREADCRUMB = "Динаміка"
DYNAMICS_SESSIONS = "Аналіз за сесіями {sessions}"
DYNAMICS_EXPORT = "Експорт звіту"
DYNAMICS_EXPORT_SOON = "Скоро"
DYNAMICS_LOADING = "Завантаження динаміки…"
DYNAMICS_EMPTY = "Для відображення динаміки потрібні щонайменше 2 підтверджені візити."
DYNAMICS_ERROR = "Не вдалося завантажити динаміку."
DYNAMICS_NOTE = "Підказка, а не діагноз • графіки доступні від 2 підтверджених візитів."
DYNAMICS_SLOPE = "нахил: {value:+.4g} / візит"
DYNAMICS_SLOPE_WITH_UNIT = "нахил: {value:+.4g} {unit} / візит"
DYNAMICS_NO_SLOPE = "нахил: —"
DYNAMICS_POINT_TOOLTIP = "Сесія {session}: {value} {unit}"
DYNAMICS_NEEDS_SESSIONS = "Для перегляду динаміки потрібні щонайменше 2 підтверджені сесії."
DYNAMICS_DIRECTIONS = {"up": "↑ зростає", "down": "↓ зменшується", "stable": "→ стабільно"}
DYNAMICS_METRIC_NAMES = {
    "pause_ratio": "Частка пауз",
    "speech_rate_syllables_per_sec": "Темп мовлення",
    "f0_variability_sd": "Варіативність F0",
    "psychomotor_retardation_index": "Індекс психомоторної загальмованості",
}
DYNAMICS_PERCENT_UNIT = "%"
DYNAMICS_POINT_BUBBLE = "Сесія {session}\n{value} {unit}"
DYNAMICS_SLOPE_UNITS = {
    "pause_ratio": "в.п.",
    "speech_rate_syllables_per_sec": "складів/с",
    "f0_variability_sd": "Гц",
}

# --- Вероніка: Новий пацієнт, Налаштування, Архів ---
