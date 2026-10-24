import re
from typing import Iterator

import pymorphy3

WORD_RE = re.compile(r"[^\W\d_]+(?:['’ʼ\-][^\W\d_]+)*")
NAME_GRAMMEMES = {"Name", "Surn", "Patr"}
CLAUSE_END_RE = re.compile(r"[.!?;:\n]")
LOOKBACK_WORDS = 3 # how many words before a tag are searched for a preposition
# Closed word classes (pronouns, prepositions, conjunctions, particles): the only words the sanitiser may discard
# when a model tags them as an entity. Verbs, adverbs and numerals are NOT here: many names and places look like them.
CLOSED_POS = {"NPRO", "PREP", "CONJ", "PRCL"}

# Parts of speech that are never names. 
FUNCTION_POS = {"NPRO", "PREP", "CONJ", "PRCL", "ADVB", "INTJ", "NUMR", "VERB", "INFN"}

def _build_prepositions() -> dict:
    """Preposition -> (case for a person, case for a place or organisation)."""
    table = {}
    for case, words in {"gent": "до від без для біля після щодо проти серед", "accs": "про через",
                        "ablt": "перед між над", "loct": "при"}.items():
        table.update({word: (case, case) for word in words.split()})
    table.update({word: ("ablt", "gent") for word in ("з", "із", "зі")}) 
    table.update({word: ("gent", "loct") for word in ("у", "в")}) 
    table["на"] = ("accs", "loct")
    
    return table

class UkrainianMorphology:
    def __init__(self) -> None:
        self._analyzer = pymorphy3.MorphAnalyzer(lang="uk")
        self._prepositions = _build_prepositions()
        self._keys_cache: dict = {}
        self._kind_cache: dict = {}

    def find_words(self, text: str) -> Iterator[re.Match]:
        return WORD_RE.finditer(text)

    def keys(self, word: str) -> frozenset:
        """Finds all hypothetical normal forms of the word"""
        low = word.lower().replace("’", "'")
        if low not in self._keys_cache:
            self._keys_cache[low] = frozenset({low, *(p.normal_form for p in self._analyzer.parse(low))})
        
        return self._keys_cache[low]

    def is_function_word(self, word: str) -> bool:
        """Pronouns, prepositions, particles, verbs and the like: never part of a name."""
        return self._kind(word)[0]

    def is_closed_class(self, word: str) -> bool:
        """A pronoun, preposition, conjunction or particle ("я", "вона", "мене", "на"): safe to leave unmasked."""
        low = word.lower().replace("’", "'")
        return any(p.tag.POS in CLOSED_POS for p in self._analyzer.parse(low))

    def is_name_like(self, word: str) -> bool:
        """The dictionary knows the word as a name/surname/patronymic, or does not know it at all."""
        function, has_name_grammeme, unknown = self._kind(word)
        return not function and (has_name_grammeme or unknown)

    def has_name_grammeme(self, word: str) -> bool:
        """The dictionary lists the word as a first name, surname or patronymic."""
        function, has_name_grammeme, _ = self._kind(word)
        return not function and has_name_grammeme

    def _kind(self, word: str) -> tuple:
        """(is function word, has a name grammeme, is unknown to the dictionary), cached."""
        low = word.lower().replace("’", "'")
        if low not in self._kind_cache:
            parses = self._analyzer.parse(low)
            self._kind_cache[low] = (
                any(p.tag.POS in FUNCTION_POS for p in parses),
                any(NAME_GRAMMEMES & set(p.tag.grammemes) for p in parses),
                not any(p.is_known for p in parses))
        return self._kind_cache[low]

    def case_before(self, preceding_text: str, is_person: bool) -> str:
        """Case required by the nearest preposition in the current clause, else nominative."""
        clause = CLAUSE_END_RE.split(preceding_text)[-1]
        words = [w.lower() for w in WORD_RE.findall(clause)][-LOOKBACK_WORDS:]

        for prep in reversed(words):
            if prep in self._prepositions:
                return self._prepositions[prep][0 if is_person else 1]
        
        return "nomn"
        
    def _inflect_word(self, word: str, case: str) -> str | None:
        """Inflects word in required case"""
        parses = [p for p in self._analyzer.parse(word.lower()) if p.is_known]
        if not parses:
          return None
        if any(case in p.tag and "Fixd" not in p.tag for p in parses):
            return word  # already in the required case: keep the speaker's own form

        named = [p for p in parses if NAME_GRAMMEMES & set(p.tag.grammemes)]

        inflected = (named or parses)[0].inflect({case})
        
        return _match_case(word, inflected.word) if inflected else None

    def is_dictionary_form(self, phrase: str) -> bool:
        """True if every word of the phrase is its own lemma (nominative, singular)."""
        words = [m.group().lower() for m in self.find_words(phrase)]
        return bool(words) and all(
            any(p.normal_form == w for p in self._analyzer.parse(w) if p.is_known) for w in words)

    def to_case(self, phrase: str, case: str) -> str:
        """Inflects the phrase in required case"""
        parts, position = [], 0
        
        for w in self.find_words(phrase):
            inflected = self._inflect_word(w.group(), case)
            if not inflected:
                return phrase
            parts.append(phrase[position:w.start()] + inflected)
            position = w.end()
        
        return "".join(parts) + phrase[position:]


def _match_case(original: str, new: str) -> str:
    """Copy the letter case of ``original`` (UPPER, Capitalised, lower) onto ``new``."""
    if len(original) > 1 and original.isupper():
        return new.upper()
    elif original[0].isupper():
        return new.capitalize()
    else:
        return new
    