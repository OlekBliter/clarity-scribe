import re

import pytest

from src.systems.privacy_ner.config import NerConfig
from src.systems.privacy_ner.models import EntityType, InvalidRequestError, Span
from src.systems.privacy_ner.ner_service import PrivacyNerService


class FakeMorphology:
    def find_words(self, text):
        return re.finditer(r"[^\W\d_]+", text)

    def keys(self, word):
        return frozenset({word.lower()})

    def case_before(self, preceding_text, is_person):
        return "nomn"

    def to_case(self, phrase, case):
        return phrase


class EmailExtractor:
    def extract(self, text):
        return [
            Span(match.start(), match.end(), EntityType.EMAIL, priority=1)
            for match in re.finditer(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text
            )
        ]


@pytest.fixture
def service():
    return PrivacyNerService(
        config=NerConfig(),
        extractors=[EmailExtractor()],
        morphology=FakeMorphology(),
    )


def test_sanitize_returns_masked_items_and_map(service):
    payload = {
        "operation": "sanitize",
        "items": [
            {"key": "first", "text": "Contact alice@example.com."},
            {"key": "second", "text": "No private data here."},
        ],
    }

    result = service.process(payload)

    assert result == {
        "items": [
            {"key": "first", "text": "Contact [MAIL_1]."},
            {"key": "second", "text": "No private data here."},
        ],
        "map": {
            "[MAIL_1]": {
                "type": "EMAIL",
                "original": "alice@example.com",
            }
        },
    }


def test_sanitize_reuses_existing_map_and_continues_tag_numbers(service):
    payload = {
        "operation": "sanitize",
        "items": [{"key": "item", "text": "Write bob@example.com."}],
        "map": {
            "[MAIL_3]": {
                "type": "EMAIL",
                "original": "alice@example.com",
            }
        },
    }

    result = service.process(payload)

    assert result["items"] == [{"key": "item", "text": "Write [MAIL_4]."}]
    assert result["map"]["[MAIL_3]"]["original"] == "alice@example.com"
    assert result["map"]["[MAIL_4]"]["original"] == "bob@example.com"


def test_restore_returns_items_without_map(service):
    payload = {
        "operation": "restore",
        "items": [{"key": "note", "text": "Contact [MAIL_1]."}],
        "map": {
            "[MAIL_1]": {
                "type": "EMAIL",
                "original": "alice@example.com",
            }
        },
    }

    assert service.process(payload) == {
        "items": [{"key": "note", "text": "Contact alice@example.com."}]
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"operation": "unknown", "items": []},
        {"operation": "sanitize", "items": [{"key": "", "text": "text"}]},
        {"operation": "sanitize", "items": [{"key": "key", "text": 123}]},
    ],
)
def test_invalid_requests_raise_invalid_request_error(service, payload):
    with pytest.raises(InvalidRequestError):
        service.process(payload)
