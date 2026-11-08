import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .models import EntityType

# Zero-shot labels sent to GLiNER and the entity type each one means.
GLINER_LABELS = {
    "person": EntityType.PERSON, "людина": EntityType.PERSON, "пацієнт": EntityType.PERSON,
    "лікар": EntityType.PERSON, "ім'я та прізвище": EntityType.PERSON, "ім'я": EntityType.PERSON,
    "прізвище": EntityType.PERSON, "surname": EntityType.PERSON,
    "address": EntityType.ADDRESS, "адреса": EntityType.ADDRESS, "street address": EntityType.ADDRESS,
    "місто": EntityType.ADDRESS, "населений пункт": EntityType.ADDRESS, "вулиця": EntityType.ADDRESS,
    "street": EntityType.ADDRESS, "адреса проживання": EntityType.ADDRESS,
    "organization": EntityType.ORG, "організація": EntityType.ORG, "компанія": EntityType.ORG,
    "лікарня": EntityType.ORG, "медичний заклад": EntityType.ORG, "місце роботи": EntityType.ORG,
}

# Latin tags
TAG_PREFIXES = {
    EntityType.PERSON: "PER", EntityType.ADDRESS: "LOC", EntityType.ORG: "ORG",
    EntityType.PHONE: "TEL", EntityType.EMAIL: "MAIL", EntityType.BIRTH_DATE: "DOB",
    EntityType.OTHER_ID: "ID",
}

# Kinship and role words stay visible
# General roles and professions trimmed from the edges of PERSON spans.
KEEP_WORDS = (
    # Family
    "мама", "мати", "тато", "батько",
    "баба", "бабуся", "дід", "дідусь",
    "прабабуся", "прадідусь",
    "брат", "сестра", "син", "донька", "дочка",
    "онук", "онука",
    "чоловік", "дружина",
    "тітка", "дядько", "племінник", "племінниця",
    "кум", "кума",
    "свекруха", "теща", "тесть",
    "вітчим", "мачуха",
    "родич", "родичка",

    # Social connections and general roles
    "друг", "подруга", "колега",
    "сусід", "сусідка",
    "людина",
    "фахівець", "фахівчиня",
    "спеціаліст", "спеціалістка",
    "пацієнт", "пацієнтка",
    "клієнт", "клієнтка",
    "співробітник", "співробітниця",
    "працівник", "працівниця",

    # Medicine and psychological care
    "лікар", "лікарка",
    "психолог", "психологиня",
    "психіатр", "психіатриня",
    "психотерапевт", "психотерапевтка",
    "терапевт", "терапевтка",
    "педіатр", "педіатриня",
    "невролог", "неврологиня",
    "кардіолог", "кардіологиня",
    "ендокринолог", "ендокринологиня",
    "стоматолог", "стоматологиня",
    "гінеколог", "гінекологиня",
    "хірург", "хірургиня",
    "анестезіолог", "анестезіологиня",
    "реабілітолог", "реабілітологиня",
    "фізіотерапевт", "фізіотерапевтка",
    "логопед", "логопединя",
    "дієтолог", "дієтологиня",
    "фельдшер", "фельдшерка",
    "медсестра", "медбрат",
    "акушер", "акушерка",
    "санітар", "санітарка",
    "аптекар", "аптекарка",
    "фармацевт", "фармацевтка",
    "лаборант", "лаборантка",

    # Education
    "вчитель", "вчителька",
    "учитель", "учителька",
    "викладач", "викладачка",
    "вихователь", "вихователька",
    "репетитор", "репетиторка",
    "педагог", "педагогиня",
    "студент", "студентка",
    "аспірант", "аспірантка",

    # Management and office work
    "начальник", "начальниця",
    "керівник", "керівниця",
    "директор", "директорка",
    "завідувач", "завідувачка",
    "бухгалтер", "бухгалтерка",
    "економіст", "економістка",
    "менеджер", "менеджерка",
    "адміністратор", "адміністраторка",
    "секретар", "секретарка",
    "асистент", "асистентка",
    "консультант", "консультантка",
    "рекрутер", "рекрутерка",

    # Technical and creative professions
    "інженер", "інженерка",
    "програміст", "програмістка",
    "дизайнер", "дизайнерка",
    "архітектор", "архітекторка",
    "журналіст", "журналістка",
    "редактор", "редакторка",
    "перекладач", "перекладачка",

    # Law
    "юрист", "юристка",
    "адвокат", "адвокатка",
    "нотаріус", "нотаріуска",

    # Service industry
    "продавець", "продавчиня",
    "касир", "касирка",
    "офіціант", "офіціантка",
    "перукар", "перукарка",
    "косметолог", "косметологиня",
    "прибиральник", "прибиральниця",
    "охоронець", "охоронниця",
    "водій", "водійка",
    "кур'єр", "кур'єрка",
)

# General terms for places, institutions, and contacts.
# A candidate is rejected only when all its words are function words
# or belong to this list, and it contains no digits.
IGNORE_WORDS = (
    # Places and address terms
    "місто", "село", "селище",
    "вулиця", "провулок", "проспект",

    # Organizations
    "центр", "компанія", "організація",
    "фірма", "підприємство", "установа",

    # Medical institutions and their departments
    "лікарня", "клініка", "поліклініка",
    "амбулаторія", "диспансер",
    "відділення", "реєстратура",

    # Educational institutions
    "школа", "університет", "інститут",
    "коледж", "ліцей", "гімназія",

    # General workplaces
    "офіс", "кабінет",

    # Contacts
    "телефон", "пошта",

    # Known false positive
    "психологія",
)

ROLE_MODIFIERS = (
    # Seniority
    "головний",
    "старший",
    "молодший",
    "провідний",

    # Management roles
    "генеральний",
    "виконавчий",

    # Areas of work
    "фінансовий",
    "комерційний",
    "технічний",
    "операційний",
    "адміністративний",

    # Medical and support roles
    "сімейний",
    "дільничний",
    "лікуючий",
    "клінічний",
    "медичний",
    "соціальний",

    # Employment status
    "штатний",
    "позаштатний",
)

# Local GLiNER weights live next to the other models: <project root>/models/gliner_multi-v2.1.
# The location is set by GLINER_MODEL_DIR (see .env.example); the default matches the example value.
DEFAULT_GLINER_DIR = os.path.join("models", "gliner_multi-v2.1")


def _model_dir_from_env() -> str:
    load_dotenv()  # reads .env if present; real environment variables take precedence
    return os.environ.get("GLINER_MODEL_DIR") or DEFAULT_GLINER_DIR


@dataclass(frozen=True)
class NerConfig:
    gliner_model: str = field(default_factory=_model_dir_from_env)
    gliner_threshold: float = 0.15
    window_words: int = 100
    window_overlap: int = 20
    min_word_len: int = 3
    gliner_labels: dict = field(default_factory=lambda: dict(GLINER_LABELS))
    tag_prefixes: dict = field(default_factory=lambda: dict(TAG_PREFIXES))
    keep_words: tuple = KEEP_WORDS
    ignore_words: tuple = IGNORE_WORDS
    role_modifiers: tuple[str, ...] = ROLE_MODIFIERS