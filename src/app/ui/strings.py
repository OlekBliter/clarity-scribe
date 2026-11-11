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

# --- Кобильник: Екран сесії ---

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
