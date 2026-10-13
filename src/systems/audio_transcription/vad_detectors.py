from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
from functools import lru_cache
import numpy as np
import torch
from typing import Any
from pydub import AudioSegment

@lru_cache(maxsize=1)
def load_model() -> Any:
    """
    Load the Silero VAD model once and reuse it on every later call.

    lru_cache(maxsize=1) memoizes the result of this zero-argument function,
    so the model weights are read from disk only on the first call.
    Loading is relatively slow, and get_timestamps() is called once per
    speaker track, so caching avoids paying that cost repeatedly.
    """
    model = load_silero_vad()
    return model

def get_timestamps(audio: AudioSegment) -> list[dict[str, int]]:
    """
    Detect speech intervals in a mono recording with the Silero VAD model.

    Args:
        audio: A mono AudioSegment, 16-bit, sampled at 8 kHz or 16 kHz
            (the output of the channel-splitting step already matches this).

    Returns:
        A list of dicts [{"start": 0.52, "end": 3.10}, ...] with times in
        SECONDS (floats) measured from the start of the given audio.

    Raises:
        ValueError: If the audio format is not supported by the model.
    """
    if audio.channels != 1 or audio.sample_width != 2 or audio.frame_rate not in (8000, 16000):
        raise ValueError("Mono, 16-bit audio at 8 or 16 kHz is required")
    model = load_model()
    wav = torch.from_numpy(np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0)

    speech_timestamps = get_speech_timestamps(
        wav,
        model,
        return_seconds=True,
        sampling_rate=audio.frame_rate,
        speech_pad_ms=0
    )
    return speech_timestamps