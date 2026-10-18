import re

from .config import NerConfig
from .map_manager import NerMapManager
from .models import EntityType, Span, TagMask
from .morphology import UkrainianMorphology

EDGE_CHARS = " \t\n,.;:!?"
TAG_RE = re.compile(r"\[[A-Za-z]+_\d+\]")
SENTENCE_BREAKS = ".!?…\n:—-\"«"


class Sanitizer:
    """Replaces sensitive fragments by tags. Detects, tags and masks. Works in two passes over all texts of a request, so tags are
    consistent across segments:
    1. every detected span gets the tag of its entity;
    2. other capitalised forms of known names ("Петренка" after "Іван Петренко") get the same tag.
    """

    def __init__(self, extractors: list, morphology: UkrainianMorphology, config: NerConfig) -> None:
        self._extractors = extractors
        self._morphology = morphology
        self._min_word_len = config.min_word_len
        self._keep_keys = frozenset(word.lower() for word in config.keep_words)

    def sanitize(self, texts: list[str], manager: NerMapManager) -> list[str]:
        detected = [self._detect(text, manager) for text in texts]
        result = []
        for text, masks in zip(texts, detected):
            masks = self._join_adjacent(sorted(masks + self._propagate(text, masks, manager),
                                               key=lambda m: m.start), text)
            result.append(self._apply(text, masks))
        return result

    def plan(self, text: str, manager: NerMapManager) -> list[TagMask]:
        """Masks of a single text (used for evaluation against labelled data)."""
        masks = self._detect(text, manager)
        return self._join_adjacent(sorted(masks + self._propagate(text, masks, manager),
                                          key=lambda m: m.start), text)

    def unmasked_names(self, sanitized_text: str) -> list[str]:
        """Capitalised words in mid-sentence that are still visible: possible missed names."""
        clean = TAG_RE.sub(" # ", sanitized_text)
        found = []
        for match in self._morphology.find_words(clean):
            before = clean[:match.start()].rstrip()
            if len(match.group()) >= self._min_word_len and match.group()[0].isupper() \
                    and before and before[-1] not in SENTENCE_BREAKS:
                found.append(match.group())
        return found

    def _detect(self, text: str, manager: NerMapManager) -> list[TagMask]:
        spans = [s for extractor in self._extractors for s in extractor.extract(text)]
        masks = []
        for span in self._merge(spans, text):
            span = self._without_keep_words(span, text)
            if span:
                masks.append(TagMask(span.start, span.end,
                                     manager.tag_for(text[span.start:span.end], span.entity_type)))
        return masks

    def _propagate(self, text: str, masks: list[TagMask], manager: NerMapManager) -> list[TagMask]:
        extra = []
        for match in self._morphology.find_words(text):
            if any(m.start < match.end() and match.start() < m.end for m in masks):
                continue
            tag = manager.tag_for_word(match.group())
            if tag:
                extra.append(TagMask(match.start(), match.end(), tag))
        return extra

    @staticmethod
    def _merge(spans: list[Span], text: str) -> list[Span]:
        """Union of overlapping spans (recall matters more than precision). The type comes from the
        member with the highest priority, among equals from the longest one."""
        groups: list[list[Span]] = []
        group_end = 0
        for span in sorted(spans, key=lambda s: (s.start, -s.end)):
            if groups and span.start < group_end:
                groups[-1].append(span)
                group_end = max(group_end, span.end)
            else:
                groups.append([span])
                group_end = span.end
        merged = []
        for group in groups:
            start, end = min(s.start for s in group), max(s.end for s in group)
            while start < end and text[start] in EDGE_CHARS:
                start += 1
            while end > start and text[end - 1] in EDGE_CHARS:
                end -= 1
            winner = max(group, key=lambda s: (s.priority, s.end - s.start))
            if end > start:
                merged.append(Span(start, end, winner.entity_type, winner.priority))
        return merged

    def _without_keep_words(self, span: Span, text: str) -> Span | None:
        """Cut kinship words ("баба", "лікар") from the edges of a person span; they stay visible."""
        if span.entity_type != EntityType.PERSON:
            return span
        words = list(self._morphology.find_words(text[span.start:span.end]))
        first, last = 0, len(words)
        while first < last and self._morphology.keys(words[first].group()) & self._keep_keys:
            first += 1
        while last > first and self._morphology.keys(words[last - 1].group()) & self._keep_keys:
            last -= 1
        if first == last:
            return None
        return Span(span.start + words[first].start(), span.start + words[last - 1].end(),
                    span.entity_type, span.priority)

    @staticmethod
    def _join_adjacent(masks: list[TagMask], text: str) -> list[TagMask]:
        """Merge neighbouring masks of one tag separated by at most one space."""
        joined = []
        for mask in masks:
            if joined and joined[-1].tag == mask.tag and text[joined[-1].end:mask.start] in ("", " "):
                joined[-1] = TagMask(joined[-1].start, mask.end, mask.tag)
            else:
                joined.append(mask)
        return joined

    @staticmethod
    def _apply(text: str, masks: list[TagMask]) -> str:
        parts, position = [], 0
        for mask in masks:
            parts += [text[position:mask.start], mask.tag]
            position = mask.end
        return "".join(parts) + text[position:]
