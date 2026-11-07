import re

from .config import NerConfig
from .map_manager import NerMapManager
from .models import EntityType, Span, TagMask
from .morphology import UkrainianMorphology
from src.schemas.contracts import PLACEHOLDER_RE, find_original

EDGE_CHARS = " \t\n,.;:!?"
TAG_RE = re.compile(r"\[[A-Za-z]+_\d+\]")
NUMBER_RE = re.compile(r"\s*(?:№|N)\s?\d+")
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
        self._keep_keys = frozenset(
            key
            for word in config.keep_words
            for key in morphology.keys(word)
        )
        self._ignore_keys = frozenset(
            key
            for word in config.ignore_words
            for key in morphology.keys(word)
        )

    def sanitize(self, texts: list[str], manager: NerMapManager) -> list[str]:
        detected = [self._detect(text, manager) for text in texts]
        return [self._apply(text, self._finalize(text, masks, manager)) for text, masks in zip(texts, detected)]

    def plan(self, text: str, manager: NerMapManager) -> list[TagMask]:
        """Masks of a single text (used for evaluation against labelled data)."""
        return self._finalize(text, self._detect(text, manager), manager)

    def _finalize(self, text: str, masks: list[TagMask], manager: NerMapManager) -> list[TagMask]:
        """Detected masks + other forms of known names + a final sweep for every known entity."""
        masks = self._join_adjacent(sorted(masks + self._propagate(text, masks, manager),
                                           key=lambda m: m.start), text)
        return self._join_adjacent(self._sweep(text, masks, manager), text)

    def unmasked_names(self, sanitized_text: str) -> list[str]:
        """Visible words that look like names: listed as names in the dictionary (works for lowercase
        speech text) or capitalised in the middle of a sentence. Possible leaks, for logging only."""
        clean = TAG_RE.sub(" # ", sanitized_text)
        found = []
        for match in self._morphology.find_words(clean):
            word = match.group()
            if len(word) < self._min_word_len or self._morphology.keys(word) & self._keep_keys:
                continue
            before = clean[:match.start()].rstrip()
            capitalised = word[0].isupper() and before and before[-1] not in SENTENCE_BREAKS
            if (capitalised and not self._morphology.is_function_word(word)) \
                    or self._morphology.has_name_grammeme(word):
                found.append(word)
        return found

    def _detect(self, text: str, manager: NerMapManager) -> list[TagMask]:
        spans = self._outside_tags([s for extractor in self._extractors for s in extractor.extract(text)], text)
        masks = []
        merged = self._merge(spans, text)
        for index, span in enumerate(merged):
            limit = merged[index + 1].start if index + 1 < len(merged) else len(text)
            span = self._with_number(self._retype_digits(span, text), text, limit)
            span = self._without_keep_words(span, text)
            if span:
                masks.append(TagMask(span.start, span.end,
                                     manager.tag_for(text[span.start:span.end], span.entity_type)))
        return masks

    def _propagate(self, text: str, masks: list[TagMask], manager: NerMapManager) -> list[TagMask]:
        extra = []
        tags = [m.span() for m in PLACEHOLDER_RE.finditer(text)]  # a placeholder already in the input is not text
        for match in self._morphology.find_words(text):
            if any(m.start < match.end() and match.start() < m.end for m in masks) \
                    or any(start < match.end() and match.start() < end for start, end in tags):
                continue
            tag = manager.tag_for_word(match.group())
            if tag:
                extra.append(TagMask(match.start(), match.end(), tag))
        return extra

    @staticmethod
    def _outside_tags(spans: list[Span], text: str) -> list[Span]:
        """A placeholder already in the input ("[PER_1]") is not text: cut every span so it never covers one."""
        tags = [m.span() for m in PLACEHOLDER_RE.finditer(text)]
        result = []
        for span in spans:
            pieces = [(span.start, span.end)]
            for a, b in tags:
                kept = []
                for lo, hi in pieces:
                    if b <= lo or hi <= a:
                        kept.append((lo, hi))
                        continue
                    if lo < a:
                        kept.append((lo, a))
                    if b < hi:
                        kept.append((b, hi))
                pieces = kept
            result += [Span(lo, hi, span.entity_type, span.priority) for lo, hi in pieces]
        return result

    @staticmethod
    def _sweep(text: str, masks: list[TagMask], manager: NerMapManager) -> list[TagMask]:
        """Safety net: every known entity of the map is masked wherever its original still stands in the text (the
        extractor is context-dependent and ``_propagate`` is cautious with lowercase ASR text). Uses the same search
        as the ``S6SanitizeOut`` leak check (``find_original``), so a text that passes here passes the validator.
        Longer originals go first. An occurrence that already lies inside a mask is left alone; one that swallows
        smaller masks replaces them. When it only partly overlaps a mask of another entity, that mask stays and the
        rest of the occurrence gets this entity's tag, so no part of a known phrase stays visible. Known defect:
        restore then puts the overlapping part back twice (the validator does not check that)."""
        masks = list(masks)
        for tag, original in sorted(manager.originals().items(), key=lambda item: -len(item[1])):
            for start, end in find_original(original, text):
                inside = sorted((m for m in masks if m.start < end and start < m.end), key=lambda m: m.start)
                if any(m.start <= start and end <= m.end for m in inside):
                    continue
                if all(start <= m.start and m.end <= end for m in inside):
                    masks = [m for m in masks if m not in inside] + [TagMask(start, end, tag)]
                    continue
                position = start
                for m in inside + [TagMask(end, end, tag)]:
                    masks += Sanitizer._gap_masks(text, position, min(m.start, end), tag)
                    position = max(position, m.end)
        return sorted(masks, key=lambda m: m.start)

    @staticmethod
    def _gap_masks(text: str, start: int, end: int, tag: str) -> list[TagMask]:
        """The uncovered stretch [start, end) of a partly masked phrase, without edge spaces and punctuation."""
        while start < end and text[start] in EDGE_CHARS:
            start += 1
        while end > start and text[end - 1] in EDGE_CHARS:
            end -= 1
        return [TagMask(start, end, tag)] if end > start else []

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
        words = list(self._morphology.find_words(text[span.start:span.end]))
        if span.entity_type != EntityType.PERSON:
            has_digit = any(c.isdecimal() for c in text[span.start:span.end])
            return span if has_digit or not self._only_common_words(words) else None
        first, last = 0, len(words)
        while first < last and self._morphology.keys(words[first].group()) & self._keep_keys:
            first += 1
        while last > first and self._morphology.keys(words[last - 1].group()) & self._keep_keys:
            last -= 1
        if first == last:
            return None
        if not any(self._is_plausible_name(w.group()) for w in words[first:last]):
            return None  # the model tagged a pronoun or an adjective ("я", "сімейному")
        return Span(span.start + words[first].start(), span.start + words[last - 1].end(),
                    span.entity_type, span.priority)

    @staticmethod
    def _retype_digits(span: Span, text: str) -> Span:
        """A model span of three or more bare digits ("1234", "067") is the start of a number, not a place."""
        fragment = text[span.start:span.end]
        if span.entity_type in (EntityType.ADDRESS, EntityType.ORG, EntityType.PERSON) \
                and fragment.replace(" ", "").isdigit() and len(fragment.replace(" ", "")) >= 3:
            return Span(span.start, span.end, EntityType.OTHER_ID, span.priority)
        return span

    def _only_common_words(self, words: list) -> bool:
        """True when every word is a pronoun, preposition, particle or a known false-positive word ("центру")."""
        return bool(words) and all(self._morphology.is_closed_class(w.group())
                                   or self._morphology.keys(w.group()) & self._ignore_keys for w in words)

    @staticmethod
    def _with_number(span: Span, text: str, limit: int) -> Span:
        """Keep the number of an organisation with it ("ліцей №5", "лікарня № 4"), never reaching into the next span."""
        if span.entity_type != EntityType.ORG:
            return span
        match = NUMBER_RE.match(text, span.end)
        return Span(span.start, match.end(), span.entity_type, span.priority) if match and match.end() <= limit else span

    def _is_plausible_name(self, word: str) -> bool:
        """Only pronouns and other closed-class words are rejected. Rare lowercase surnames are often unknown to the
        dictionary or look like common nouns ("лико"), so requiring a dictionary name would leak them."""
        return not self._morphology.is_closed_class(word)

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
