import re

from .config import NerConfig
from .models import Entity, EntityType
from .morphology import UkrainianMorphology

TAG_NUMBER_RE = re.compile(r"^\[([A-Za-z]+)_(\d+)\]$")

def entities_from_dict(ner_map: dict) -> dict:
    """``{tag: {"type", "original"}}`` -> ``{tag: Entity}``."""
    return {tag: Entity(tag, EntityType(entry["type"]), entry["original"]) for tag, entry in ner_map.items()}

class NerMapManager:
    """Creates tags and groups several mentions of one entity under one tag."""

    def __init__(self, morphology: UkrainianMorphology, config: NerConfig, initial_map: dict) -> None:
        self._morphology = morphology
        self._prefixes = config.tag_prefixes
        self._min_word_len = config.min_word_len
        self._entities: dict = {}
        self._counters: dict = {}
        self._word_index: dict = {}  # lemma key -> tags of named entities that contain the word
        for entity in entities_from_dict(initial_map).values():
            self._register(entity)

    def tag_for(self, mention: str, entity_type: EntityType) -> str:
        """Tag of the entity the mention refers to; a new entity is created if none matches."""
        if entity_type.is_named:
            tag = self._find_named(mention, entity_type)
            if tag:
                self._extend(tag, mention)
                return tag
        else:
            for entity in self._entities.values():
                if entity.type == entity_type and entity.original == mention:
                    return entity.tag
        return self._create(mention, entity_type)

    def tag_for_word(self, word: str) -> str | None:
        """Tag of a known entity that this stray word is another form of, or None.

        Spoken (ASR) text has no capital letters, so a lowercase word is propagated only when it is
        safe: a name of a known person, or the whole mention of a one-word place. Capitalised words
        may belong to any named entity.
        """
        if not self._is_word(word):
            return None
        for tag in self._candidates(self._morphology.keys(word)):
            entity = self._entities[tag]
            if word[0].isupper():
                return tag
            if entity.type == EntityType.PERSON and self._morphology.has_name_grammeme(word):
                return tag
            if entity.type == EntityType.ADDRESS and len(entity.original.split()) == 1:
                return tag
        return None

    def to_dict(self) -> dict:
        """``{tag: Entity}`` -> ``{tag: {"type", "original"}}``."""
        return {tag: {"type": e.type.value, "original": e.original} for tag, e in self._entities.items()}

    def _create(self, mention: str, entity_type: EntityType) -> str:
        """Creates tag for new mention"""
        prefix = self._prefixes[entity_type]
        entity = Entity(f"[{prefix}_{self._counters.get(prefix, 0) + 1}]", entity_type, mention)
        self._register(entity)
        return entity.tag

    def _register(self, entity: Entity) -> None:
        """Registers entity to _entities dict (tag: Entity)"""
        self._entities[entity.tag] = entity
        found = TAG_NUMBER_RE.match(entity.tag)
        if found:
            self._counters[found.group(1)] = max(self._counters.get(found.group(1), 0), int(found.group(2)))
        self._index(entity.tag, entity.type, entity.original)

    def _index(self, tag: str, entity_type: EntityType, mention: str) -> None:
        """Registers all tags for an entity to _word_index dict (mention: [tags])"""
        if entity_type.is_named:
            for word in self._words(mention):
                for key in self._morphology.keys(word):
                    self._word_index.setdefault(key, []).append(tag)

    def _extend(self, tag: str, mention: str) -> None:
        """Keep the longest mention as the original and index its words."""
        entity = self._entities[tag]
        if self._is_better_original(mention, entity.original):
            entity.original = mention
        self._index(tag, entity.type, mention)

    def _is_better_original(self, new: str, old: str) -> bool:
        """More words win ("Іван Петренко" over "Петренка"); with equal length the dictionary form
        (nominative) wins, because inflecting from it is the most reliable."""
        if len(new.split()) != len(old.split()):
            return len(new.split()) > len(old.split())
        return self._morphology.is_dictionary_form(new) and not self._morphology.is_dictionary_form(old)

    def _find_named(self, mention: str, entity_type: EntityType) -> str | None:
        """An entity whose words cover every word of the shorter mention.

        "Іван Петренко" and "Петренка" match; "Іван Петренко" and "Іван Коваль" do not,
        so two people with one first name stay apart.
        """
        words = [self._morphology.keys(w) for w in self._words(mention)]
        if not words:
            return None
        for tag in self._candidates(frozenset().union(*words)):
            entity = self._entities[tag]
            if entity.type != entity_type:
                continue
            known = [self._morphology.keys(w) for w in self._words(entity.original)]
            shorter, longer = (words, known) if len(words) <= len(known) else (known, words)
            if all(any(keys & other for other in longer) for keys in shorter):
                return tag
        return None

    def _candidates(self, keys: frozenset) -> list:
        tags = {tag for key in keys for tag in self._word_index.get(key, [])}
        order = list(self._entities)
        return sorted(tags, key=order.index)

    def _words(self, text: str) -> list:
        """Words of a mention that identify the entity: long enough and not function words."""
        return [m.group() for m in self._morphology.find_words(text) if self._is_word(m.group())]

    def _is_word(self, word: str) -> bool:
        return len(word) >= self._min_word_len and not self._morphology.is_function_word(word)
