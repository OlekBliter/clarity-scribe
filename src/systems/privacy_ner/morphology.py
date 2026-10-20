import re
from typing import Iterator

import pymorphy3

WORD_RE = re.compile(r"[^\W\d_]+(?:['’ʼ\-][^\W\d_]+)*")
NAME_GRAMMEMES = {"Name", "Surn", "Patr"}
CLAUSE_END_RE = re.compile(r"[.!?;:\n]")
LOOKBACK_WORDS = 3 # how many words before a tag are searched for a preposition

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

    def find_words(self, text: str) -> Iterator[re.Match]:
        return WORD_RE.finditer(text)

    def keys(self, word: str) -> frozenset:
        """Finds all hypothetical normal forms of the word"""
        low = word.lower().replace("’", "'")
        if low not in self._keys_cache:
            self._keys_cache[low] = frozenset({low, *(p.normal_form for p in self._analyzer.parse(low))})
        
        return self._keys_cache[low]

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
        
        named = [p for p in parses if NAME_GRAMMEMES & set(p.tag.grammemes)]

        inflected = (named or parses)[0].inflect({case})
        
        return _match_case(word, inflected.word) if inflected else None

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
    