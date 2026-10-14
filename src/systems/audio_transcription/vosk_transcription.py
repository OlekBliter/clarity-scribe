from functools import lru_cache
from pydub import AudioSegment
from pathlib import Path
from vosk import Model, KaldiRecognizer
from .channel_splitter import split
import json
from dotenv import load_dotenv
import os

#Load vosk model
load_dotenv()
MODEL_DIR = os.getenv("MODEL_DIR", "models/vosk-model-small-uk-v3-small")

# Maximum pause (in seconds) between two neighbouring words that still keeps
# them in the same segment. A longer pause starts a new segment.
limit = 1.0                  

class Segment:
    """One continuous utterance of a single speaker (the final output unit)."""
    def __init__(self, segment_id, speaker, start_time, end_time, text, confidence):
        self.segment_id = segment_id
        self.speaker = speaker
        self.start_time = start_time    
        self.end_time = end_time
        self.text = text
        self.confidence = confidence

@lru_cache(maxsize=1)
def load_model(model_path = MODEL_DIR) -> Model:
    """
    Load the Vosk model from disk and cache it.

    Loading takes noticeable time and memory, and the model is needed once per
    speaker track, so lru_cache(maxsize=1) makes every call after the first
    return the same Model object instantly.

    Raises:
        FileNotFoundError: If the folder does not exist or is incomplete.
    """
    path = Path(model_path)

    if not path.is_dir():
        raise FileNotFoundError(f"Папку моделі не знайдено")
    missing = [d for d in ("am", "conf", "graph") if not (path / d).exists()]
    if missing:
        raise FileNotFoundError(
            f"{path} is missing {', '.join(missing)}: the model was not fully "
            f"extracted or the wrong folder was specified."
        )

    return Model(str(path))

def recognize_words(audio: AudioSegment, model: Model, speaker: str) -> list[dict]:
    """
    Transcribe one mono track and return its text grouped into segments.

    Args:
        audio: Mono, 16-bit track (the recognizer is created with its frame rate).
        model: Loaded Vosk model.
        speaker: Role label attached to every resulting segment.

    Returns:
        A list of segment dicts (see group_words).
    """
    rec = KaldiRecognizer(model, audio.frame_rate)
    rec.SetWords(True)
    step = 4000 * audio.frame_width
    raw, words = audio.raw_data, []

    for i in range(0, len(raw), step):
        if rec.AcceptWaveform(raw[i:i + step]):
            words += json.loads(rec.Result()).get("result", [])
    words += json.loads(rec.FinalResult()).get("result", [])

    return group_words(words, speaker)

def get_audio_duration_sec(audio: AudioSegment) -> float:
    """Return the duration of the audio in seconds (pydub gives it as a float)."""
    return audio.duration_seconds

def group_words(words: list[dict], speaker: str) -> list:
    """
    Merge a flat list of recognized words into segments.

    Consecutive words belong to the same segment while the pause between them
    does not exceed `limit` seconds. For every segment the function stores the
    start of its first word, the end of its last word, the joined text and the
    average word confidence.

    Args:
        words: Vosk words, each {"word", "start", "end", "conf"}, in time order.
        speaker: Role label stored in every segment.

    Returns:
        A list of dicts {"speaker", "start", "end", "text", "conf"}.
    """
    segments = []
    full_segment = {}
    count = 1

    if words:
        full_segment = {
            "speaker": speaker,
            "start": words[0]["start"],
            "end": words[0]["end"],
            "text": words[0]["word"],
            "conf": words[0]["conf"]
        }
        for i in range(1, len(words)):
            start_time = words[i]["start"]
            end_time = words[i]["end"]
            past_end_time = words[i - 1]["end"]

            if start_time - past_end_time <= limit:
                count += 1
                full_segment["end"] = end_time
                full_segment["text"] += " " + words[i]["word"]
                
                full_segment["conf"] = full_segment["conf"] + words[i]["conf"]
            else:
                full_segment["start"] = round(full_segment["start"], 2)
                full_segment["end"] = round(full_segment["end"], 2)
                full_segment["conf"] = round(full_segment["conf"] / count, 4)
                segments.append(full_segment)
                full_segment = {
                    "speaker": speaker,
                    "start": words[i]["start"],
                    "end": words[i]["end"],
                    "text": words[i]["word"],
                    "conf": words[i]["conf"]
                }
                count = 1

        full_segment["start"] = round(full_segment["start"], 2)
        full_segment["end"] = round(full_segment["end"], 2)
        full_segment["conf"] = round(full_segment["conf"] / count, 4)
        segments.append(full_segment)

    return segments

def create_output_segments(segments_patient: list[dict], segments_doctor: list[dict]) -> list[Segment]:
    """
    Merge both speakers' segments into one chronological dialogue.

    The result is a list of Segment objects with sequential ids starting at 0,
    ordered by start time. Overlapping speech is kept (segments may overlap).
    """
    full_segments = segments_patient + segments_doctor
    full_segments.sort(key=lambda s: s["start"])

    return [Segment(segment_id = i, 
                    speaker = full_segments[i]["speaker"],
                    start_time = full_segments[i]["start"],
                    end_time = full_segments[i]["end"],
                    text = full_segments[i]["text"],
                    confidence = full_segments[i]["conf"]
                    ) for i in range(0, len(full_segments))]

def collect_metadata(segments: list[Segment], audio: AudioSegment) -> dict:
    """
    Compute summary statistics of the conversation.

    Returns a dict with the total audio duration, the time each side spent
    speaking, and the total time when nobody was speaking.
    """
    audio_duration_sec = get_audio_duration_sec(audio)
    doctor_speaking_time_sec = 0.0
    patient_speaking_time_sec = 0.0
    silence_time_sec = 0.0
    last_time_speaking = 0.0

    for segment in sorted(segments, key=lambda s: s.start_time):
        if last_time_speaking < segment.start_time:
            silence_time_sec += segment.start_time - last_time_speaking
        if segment.speaker == "PATIENT":
            patient_speaking_time_sec += segment.end_time - segment.start_time
        else:
            doctor_speaking_time_sec += segment.end_time - segment.start_time
        last_time_speaking = max(last_time_speaking, segment.end_time)

    if audio_duration_sec > last_time_speaking:
        silence_time_sec += audio_duration_sec - last_time_speaking

    return {
        "audio_duration_sec": audio_duration_sec,
        "doctor_speaking_time_sec": doctor_speaking_time_sec,
        "patient_speaking_time_sec": patient_speaking_time_sec,
        "silence_time_sec": silence_time_sec,
    }
    
def transcription(audio_path: str, channel_map: dict[str, int]) -> dict:
    """
    Run the full S1 pipeline: split channels -> recognize each speaker -> merge -> metadata.

    Args:
        audio_path: Path to the stereo recording (one speaker per channel).
        channel_map: Role -> channel index, e.g. {"DOCTOR": 0, "PATIENT": 1}.
            Keys must be exactly "DOCTOR" and "PATIENT" (collect_metadata
            compares against "PATIENT").
        language: Language code copied into the output.

    Returns:
        A JSON-serializable dict: {"language", "metadata", "segments"}.
    """
    tracks = split(audio_path, channel_map)
    model = load_model()

    segments_doctor = recognize_words(tracks["DOCTOR"], model, "DOCTOR")
    segments_patient = recognize_words(tracks["PATIENT"], model, "PATIENT")

    segments = create_output_segments(segments_patient, segments_doctor)

    metadata = collect_metadata(segments, tracks["DOCTOR"])

    return {
        "metadata": {key: round(value, 2) for key, value in metadata.items()},
        "segments": [vars(segment) for segment in segments],
    }