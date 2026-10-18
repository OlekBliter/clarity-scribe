from .config import NerConfig
from .gliner_extractor import GlinerExtractor
from .map_manager import NerMapManager, entities_from_dict
from .models import EntityType, InvalidRequestError
from .morphology import UkrainianMorphology
from .regex_extractor import RegexExtractor
from .restorer import Restorer
from .sanitizer import Sanitizer

class PrivacyNerService:
    def __init__(self, config: NerConfig | None = None, extractors: list | None = None,
                 morphology: UkrainianMorphology | None = None) -> None:
        self._config = config if config is not None else NerConfig()
        self._morphology = morphology or UkrainianMorphology()
        if extractors is None:
            extractors = [RegexExtractor(), GlinerExtractor(self._config)]
        self._sanitizer = Sanitizer(extractors, self._morphology, self._config)
        self._restorer = Restorer(self._morphology, self._config)

    def process(self, payload: dict) -> dict:
        """Handle one contract request and return the contract response."""
        try:
            operation, items = payload["operation"], payload["items"]
            keys, texts = [i["key"] for i in items], [i["text"] for i in items]
            ner_map = payload.get("map", {})
            entities_from_dict(ner_map)
            valid = all(isinstance(k, str) and k for k in keys) and all(isinstance(t, str) for t in texts)
            if operation not in ("sanitize", "restore") or not valid:
                raise ValueError(operation)
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidRequestError("request does not follow the contract") from error
        if operation == "sanitize":
            texts, ner_map = self.sanitize(texts, ner_map)
            return {"items": [{"key": k, "text": t} for k, t in zip(keys, texts)], "map": ner_map}
        texts = self.restore(texts, ner_map)
        return {"items": [{"key": k, "text": t} for k, t in zip(keys, texts)]}

    def sanitize(self, texts: list[str], ner_map: dict) -> tuple:
        manager = NerMapManager(self._morphology, self._config, ner_map)
        result = self._sanitizer.sanitize(texts, manager)
        missed = sum(len(self._sanitizer.unmasked_names(text)) for text in result)
        return result, manager.to_dict()

    def restore(self, texts: list[str], ner_map: dict) -> list[str]:
        entities = entities_from_dict(ner_map)
        return [self._restorer.restore(text, entities) for text in texts]
