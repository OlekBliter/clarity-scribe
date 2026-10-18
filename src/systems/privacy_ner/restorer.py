import re

from .config import NerConfig
from .models import Entity, EntityType
from .morphology import UkrainianMorphology

class Restorer:
    """Puts the original data back into the text the LLM wrote. Tolerates the usual LLM distortions: ``[PER_1]``, ``PER_1``, ``[ PER-1 ]``, ``[per_1]`` and a
    Cyrillic ending glued to the tag (``[PER_1]ом``). The ending is dropped; the case is guessed
    from the preceding preposition (nominative by default). Unknown tags stay visible."""

    def __init__(self, morphology: UkrainianMorphology, config: NerConfig) -> None:
        self._morphology = morphology
        prefixes = "|".join(re.escape(p) for p in config.tag_prefixes.values())
        self._tag_re = re.compile(
            rf"\[\s*(?P<p1>{prefixes})\s*[_\-\s]?\s*(?P<n1>\d+)\s*\]"
            rf"|(?<![A-Za-z0-9_])(?P<p2>{prefixes})[_\-](?P<n2>\d+)(?!\d)", re.IGNORECASE)
        self._ending_re = re.compile(r"[а-яіїєґ']*", re.IGNORECASE)

    def restore(self, text: str, entities: dict) -> str:
        parts, position, unknown = [], 0, 0
        for match in self._tag_re.finditer(text):
            tag = f"[{(match.group('p1') or match.group('p2')).upper()}_{int(match.group('n1') or match.group('n2'))}]"
            parts.append(text[position:match.start()])
            if tag in entities:
                parts.append(self._render(entities[tag], text[:match.start()]))
                position = self._ending_re.match(text, match.end()).end()
            else:
                parts.append(match.group())
                position = match.end()
                unknown += 1
        return "".join(parts) + text[position:]

    def _render(self, entity: Entity, preceding_text: str) -> str:
        """Inflect names (and one-word places) by the guessed case; other data is inserted as is."""
        if not entity.type.is_named or (entity.type != EntityType.PERSON and " " in entity.original.strip()):
            return entity.original
        case = self._morphology.case_before(preceding_text, entity.type == EntityType.PERSON)
        return self._morphology.to_case(entity.original, case)
