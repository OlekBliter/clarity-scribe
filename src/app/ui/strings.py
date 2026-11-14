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
MEDCARD_REMOVE_SOURCE = "Прибрати джерело з цього поля"
MEDCARD_OPEN_BLOCK = "Відкрити"
MEDCARD_PANEL_CLOSE = "×"
MEDCARD_PANEL_CLOSE_LABEL = "Закрити панель"
MEDCARD_LOCAL_EDITS = "Правки ще не збережені. При виході з медкартки їх буде скинуто."
MEDCARD_QUOTE = "Цитата з розмови"
MEDCARD_TITLE = 'Медкартка першого прийому • {date}'
MEDCARD_BREADCRUMB = 'Медкартка'
MEDCARD_EXPORT = 'Експорт медкартки'
MEDCARD_SOON = 'Скоро'
MEDCARD_SAVE = 'Зберегти правки'
MEDCARD_APPROVE = 'Підтвердити'
MEDCARD_ACTIONS_HINT = 'Збереження та підтвердження будуть доступні в A4.'
MEDCARD_LOADING = 'Завантаження медкартки…'
MEDCARD_EMPTY = 'Медкартки ще немає.'
MEDCARD_ERROR = 'Не вдалося завантажити медкартку.'
MEDCARD_LOCAL = 'Лише локально'
MEDCARD_DOCTOR = 'Заповнює лікар'
MEDCARD_EDITED = 'Відредаговано лікарем'
MEDCARD_YES = 'Так'
MEDCARD_NO = 'Ні'
MEDCARD_NONE = '—'
MEDCARD_ATTENTION = 'Потребує уваги'
MEDCARD_ATTENTION_SOURCE = 'Потребує уваги • джерело {time}'
MEDCARD_CONTRADICTORY = 'Суперечливо'
MEDCARD_CONVERSATION = 'Із розмови'
MEDCARD_SOURCE_TITLE = 'Джерело {time}'
MEDCARD_EXTRA = 'Інші дані'
MEDCARD_BIRTH_AGE = '{birth} ({age} {unit})'
MEDCARD_AGE_UNITS = ('рік', 'роки', 'років')
MEDCARD_COLUMNS = {'left': 'Анамнез та дані з розмови', 'right': 'Клінічна оцінка та домовленості'}
MEDCARD_BLOCKS = {'contacts': 'Контакти й екстрений контакт',
 'safety': 'Безпека',
 'request': 'Запит',
 'history': 'Попередній досвід і лікування',
 'substance': 'Вживання ПАР',
 'context': 'Контекст життя',
 'scales': 'Шкали',
 'hypotheses': 'Гіпотези й оцінка ризику',
 'resources': 'Ресурси й цілі',
 'agreements': 'Домовленості'}
MEDCARD_FIELDS = {'safety.suicidal_past': 'Суїцидальні думки / самоушкодження в минулому',
 'safety.suicidal_now': 'Суїцидальні думки / самоушкодження зараз',
 'safety.details': 'Подробиці щодо безпеки',
 'request.complaint': 'Скарга',
 'request.onset': 'Коли почалося',
 'request.why_now': 'Чому звернулися зараз',
 'history.similar_before': 'Подібні стани раніше',
 'history.prior_therapy': 'Попередня терапія',
 'history.helpful_or_not': 'Що допомагало або не допомагало',
 'history.on_medication': 'Приймання ліків',
 'history.medications_list': 'Препарати',
 'substance.alcohol': 'Алкоголь',
 'substance.cannabis': 'Канабіс',
 'substance.other': 'Інші речовини',
 'context.work_study': 'Робота та навчання',
 'context.relationships_family': 'Стосунки й сім’я',
 'context.life_changes_year': 'Зміни за останній рік',
 'context.social_support': 'Соціальна підтримка',
 'scales.phq9': 'PHQ-9',
 'scales.gad7': 'GAD-7',
 'scales.other': 'Інші шкали',
 'hypotheses.notes': 'Клінічні спостереження',
 'hypotheses.risk': 'Оцінка ризику',
 'resources.coping': 'Що допомагає справлятися',
 'resources.strengths': 'Сильні сторони',
 'goals.change': 'Бажані зміни',
 'goals.success_criteria': 'Критерії успіху',
 'agreements.format': 'Формат',
 'agreements.frequency': 'Частота',
 'agreements.cost': 'Вартість',
 'agreements.initial_goals': 'Цілі на початковий період'}
MEDCARD_CONTACTS = {'preferred_name': 'Ім’я',
 'birth_date': 'Дата народження',
 'phone': 'Телефон',
 'email': 'Email',
 'preferred_channel': 'Зручний канал',
 'emergency_name': 'Екстрений контакт',
 'emergency_relation': 'Стосунок',
 'emergency_phone': 'Телефон екстреного контакту',
 'emergency_consent': 'Згода на звернення'}
MEDCARD_RISKS = {'low': 'Низький', 'moderate': 'Помірний', 'high': 'Високий'}
MEDCARD_STATUSES = {'draft': 'Чернетка', 'approved': 'Затверджено'}
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
