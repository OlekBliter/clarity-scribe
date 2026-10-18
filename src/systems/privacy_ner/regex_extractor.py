import re

from .models import EntityType, Span

UA_MONTHS = (
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
)


class RegexExtractor:
    """Extracting Spans with regex"""

    priority = 1

    def __init__(self) -> None:
        months = "|".join(UA_MONTHS)
        self._patterns = [
            (EntityType.EMAIL, re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
            (EntityType.PHONE, re.compile(
                r"(?<!\d)(?:\+?38[\s-]?\(?0\d{2}|\+?380[\s-]?\(?\d{2}|\(?0\d{2})"
                r"\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)")),
            (EntityType.BIRTH_DATE, re.compile(
                r"(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{4}(?!\d)"
                r"|(?<!\d)\d{4}[./-]\d{1,2}[./-]\d{1,2}(?!\d)"
                rf"|(?<!\d)\d{{1,2}}\s+(?:{months})\s+\d{{4}}(?:\s*(?:року|р\b))?", re.IGNORECASE)),
            (EntityType.OTHER_ID, re.compile(r"(?<!\d)(?:\d[ -]?){8,18}\d(?!\d)")),
        ]

    def extract(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for entity_type, pattern in self._patterns:
            for match in pattern.finditer(text):
                if not any(match.start() < s.end and s.start < match.end() for s in spans):
                    spans.append(Span(match.start(), match.end(), entity_type, self.priority))
        return spans