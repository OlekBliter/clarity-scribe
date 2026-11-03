from .config import NerConfig
from .gliner_extractor import GlinerExtractor
from .map_manager import NerMapManager, entities_from_dict
from .models import EntityType, InvalidRequestError
from .morphology import UkrainianMorphology
from .regex_extractor import RegexExtractor
from .restorer import Restorer
from .sanitizer import Sanitizer
from src.schemas.contracts import PLACEHOLDER_RE, S6RestoreOut, S6SanitizeOut

class PrivacyNerService:
    """
    Sanitize and restore text using a dict -> dict contract.

    Input:
        {
            "operation": ...,
            "items": ...,
            "map": ...,
        }

    Output for ``sanitize``:
        {
            "items": ...,
            "map": ...,
        }

    Output for ``restore``:
        {
            "items": ...,
        }
    """

    def __init__(self, config: NerConfig | None = None, extractors: list | None = None,
                 morphology: UkrainianMorphology | None = None) -> None:
        self._config = config if config is not None else NerConfig()
        self._morphology = morphology or UkrainianMorphology()
        if extractors is None:
            extractors = [RegexExtractor(), GlinerExtractor(self._config)]
        self._sanitizer = Sanitizer(extractors, self._morphology, self._config)
        self._restorer = Restorer(self._morphology, self._config)

    def process(self, input_data: dict) -> dict:
        """Handle one request and return a Pydantic-validated plain dictionary."""
        try:
            if not isinstance(input_data, dict) or not isinstance(input_data.get("items"), list):
                raise TypeError
            operation, items = input_data["operation"], input_data["items"]
            if any(not isinstance(item, dict) for item in items):
                raise TypeError
            keys, texts = [i["key"] for i in items], [i["text"] for i in items]
            ner_map = input_data.get("map", {})
            if not isinstance(ner_map, dict):
                raise TypeError
            entities_from_dict(ner_map)
            valid = all(isinstance(k, str) and k for k in keys) and all(isinstance(t, str) for t in texts)
            if operation not in ("sanitize", "restore") or not valid:
                raise ValueError(operation)
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidRequestError("request does not follow the contract") from error
        if operation == "sanitize":
            texts, ner_map = self._sanitize(texts, ner_map)
            result = {"items": [{"key": k, "text": t} for k, t in zip(keys, texts)], "map": ner_map}
            return S6SanitizeOut.model_validate(result).model_dump()
        texts = self._restore(texts, ner_map)
        if any(PLACEHOLDER_RE.search(text) for text in texts):
            raise InvalidRequestError("restore left unresolved placeholders")
        result = {"items": [{"key": k, "text": t} for k, t in zip(keys, texts)]}
        return S6RestoreOut.model_validate(result).model_dump()

    def _sanitize(self, texts: list[str], ner_map: dict) -> tuple[list[str], dict]:
        manager = NerMapManager(self._morphology, self._config, ner_map)
        result = self._sanitizer.sanitize(texts, manager)
        return result, manager.to_dict()

    def _restore(self, texts: list[str], ner_map: dict) -> list[str]:
        entities = entities_from_dict(ner_map)
        return [self._restorer.restore(text, entities) for text in texts]
