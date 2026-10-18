import os
import re
from typing import Iterator

from .config import NerConfig
from .models import NerError, Span


class ModelError(NerError):
    """The model could not be loaded or failed during inference."""


def resolve_device() -> str:
    """Pick the best available accelerator, falling back to CPU."""
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_model(config: NerConfig):
    """Load GLiNER from the local models folder and move it to the best available device."""
    if not os.path.isdir(config.gliner_model):
        raise ModelError(f"GLiNER model directory not found: {os.path.abspath(config.gliner_model)}")
    try:
        from gliner import GLiNER
        model = GLiNER.from_pretrained(config.gliner_model, local_files_only=True)
        return model.to(resolve_device()).eval()
    except Exception as error:
        raise ModelError("cannot load the GLiNER model") from error


class GlinerExtractor:
    """Extracting Spans with GLiNER model"""

    priority = 0

    def __init__(self, config: NerConfig, model=None) -> None:
        self._labels = config.gliner_labels
        self._threshold = config.gliner_threshold
        self._window = config.window_words
        self._overlap = config.window_overlap
        self._model = model if model is not None else load_model(config)

    def extract(self, text: str) -> list[Span]:
        spans = []
        for offset, chunk in self.windows(text):
            try:
                found = self._model.predict_entities(
                    chunk, list(self._labels), threshold=self._threshold, flat_ner=True
                )
            except Exception as error:
                raise ModelError("GLiNER inference failed") from error
            spans += [
                Span(offset + e["start"], offset + e["end"], self._labels[e["label"]], self.priority)
                for e in found
            ]
        return spans

    def windows(self, text: str) -> Iterator[tuple]:
        """Iterates through chunks"""
        words = list(re.finditer(r"\S+", text))
        step = max(1, self._window - self._overlap)
        for index in range(0, len(words), step):
            part = words[index:index + self._window]
            yield part[0].start(), text[part[0].start():part[-1].end()]
            if index + self._window >= len(words):
                break
