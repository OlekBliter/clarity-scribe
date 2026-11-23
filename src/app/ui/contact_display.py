"""Shared display of the date of birth on screen and in reports."""
from datetime import date
from . import strings as S


def birth_with_age(contacts):
    birth = contacts.get("birth_date")
    if not birth:
        return S.MEDCARD_NONE
    try:
        birth = date.fromisoformat(birth).strftime("%d.%m.%Y")
    except ValueError:
        pass
    age = contacts.get("age")
    if age is None:
        return birth
    last, last_two = age % 10, age % 100
    unit = S.MEDCARD_AGE_UNITS[0 if last == 1 and last_two != 11 else
                               1 if 2 <= last <= 4 and not 12 <= last_two <= 14 else 2]
    return S.MEDCARD_BIRTH_AGE.format(birth=birth, age=age, unit=unit)
