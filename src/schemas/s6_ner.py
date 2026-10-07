import re
from typing import Annotated, Literal, Union

from pydantic import Field, RootModel, field_validator, model_validator

from .common import ContractModel, EntityType, NonEmptyStr

PLACEHOLDER_PREFIX: dict[EntityType, str] = {
    EntityType.PERSON: "ПІБ",
    EntityType.ADDRESS: "АДРЕСА",
    EntityType.PHONE: "ТЕЛЕФОН",
    EntityType.EMAIL: "EMAIL",
    EntityType.ORG: "ОРГ",
    EntityType.BIRTH_DATE: "ДН",
    EntityType.OTHER_ID: "ІД",
}
_PREFIXES = "|".join(PLACEHOLDER_PREFIX.values())
PLACEHOLDER_RE = re.compile(rf"\[(?:{_PREFIXES})_[1-9]\d*\]")
_PLACEHOLDER_FULL = re.compile(rf"^\[({_PREFIXES})_[1-9]\d*\]$")


def find_placeholders(text: str) -> list[str]:
    return PLACEHOLDER_RE.findall(text)


class NerEntry(ContractModel):
    type: EntityType
    original: NonEmptyStr


class NerMap(RootModel[dict[str, NerEntry]]):
    root: dict[str, NerEntry] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_types(self):
        for key, entry in self.root.items():
            m = _PLACEHOLDER_FULL.match(key)
            if not m:
                raise ValueError(f"некоректний плейсхолдер: {key!r}")
            if m.group(1) != PLACEHOLDER_PREFIX[entry.type]:
                raise ValueError(f"плейсхолдер {key!r} не відповідає типу {entry.type.value}")
        return self

    def __len__(self) -> int:
        return len(self.root)

    def __contains__(self, key: object) -> bool:
        return key in self.root


class NerItem(ContractModel):
    key: NonEmptyStr
    text: str


def _unique_keys(items: list[NerItem]) -> list[NerItem]:
    keys = [i.key for i in items]
    if len(set(keys)) != len(keys):
        raise ValueError("items[].key мають бути унікальними")
    return items


# ── sanitize ──
class S6SanitizeIn(ContractModel):
    operation: Literal["sanitize"]
    items: list[NerItem]
    map: NerMap = Field(default_factory=NerMap)

    _u = field_validator("items")(_unique_keys)


class S6SanitizeOut(ContractModel):
    items: list[NerItem]
    map: NerMap

    _u = field_validator("items")(_unique_keys)

    @model_validator(mode="after")
    def _no_leaks(self):
        for item in self.items:
            for ph in find_placeholders(item.text):
                if ph not in self.map:
                    raise ValueError(f"{item.key}: плейсхолдер {ph} відсутній у map")
            for ph, entry in self.map.root.items():
                if entry.original in item.text:
                    raise ValueError(f"{item.key}: у санітизованому тексті лишилась сутність {ph}")
        return self

    def check_against_input(self, inp: S6SanitizeIn) -> None:
        if [i.key for i in self.items] != [i.key for i in inp.items]:
            raise ValueError("ключі items не збігаються з вхідними")
        for ph, entry in inp.map.root.items():
            if self.map.root.get(ph) != entry:
                raise ValueError(f"запис {ph} у словнику змінено або видалено")


# ── restore ──
class S6RestoreIn(ContractModel):
    operation: Literal["restore"]
    items: list[NerItem]
    map: NerMap

    _u = field_validator("items")(_unique_keys)


class S6RestoreOut(ContractModel):
    items: list[NerItem]

    _u = field_validator("items")(_unique_keys)

    @model_validator(mode="after")
    def _fully_restored(self):
        for item in self.items:
            if find_placeholders(item.text):
                raise ValueError(f"{item.key}: після restore лишились нерозкриті плейсхолдери")
        return self

    def check_against_input(self, inp: S6RestoreIn) -> None:
        if [i.key for i in self.items] != [i.key for i in inp.items]:
            raise ValueError("ключі items не збігаються з вхідними")


S6In = Annotated[Union[S6SanitizeIn, S6RestoreIn], Field(discriminator="operation")]
