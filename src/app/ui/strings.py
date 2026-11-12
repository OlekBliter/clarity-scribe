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

# --- Кобильник: Екран сесії ---

# --- Лаврик: Медкартка, Динаміка ---

# --- Вероніка: Новий пацієнт, Налаштування, Архів ---
