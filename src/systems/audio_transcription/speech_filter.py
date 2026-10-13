from vad_detectors import get_timestamps
import io
from pydub import AudioSegment


def get_voice_activity(audio: AudioSegment) -> tuple[AudioSegment, list[dict[str, int]]]:
    """
    Remove silence and non-speech parts from a mono recording using a
    Voice Activity Detector (VAD), and return only the speech glued together.

    Args:
        audio: A mono AudioSegment, normally one speaker's track
            (16 kHz, 16-bit) produced by the channel-splitting step.

    Returns:
        A tuple (connected_audio, timestamps):
            connected_audio: AudioSegment made of all detected speech segments
                concatenated back to back, with the pauses removed.
            timestamps: The original VAD output, a list of dicts with "start" and
                "end" in seconds, relative to the ORIGINAL (uncut) audio.
                Keep it: the positions in connected_audio no longer match the
                original timeline, so these values are needed to map them back.

    Raises:
        ValueError: If the VAD finds no speech at all in the recording.
    """
    timestamps = get_timestamps(audio)
    audio_segments = []
    for timestamp in timestamps:
        start_ms = int(timestamp["start"] * 1000)
        end_ms = int(timestamp["end"] * 1000)
        segment = audio[start_ms:end_ms]

        audio_segments.append(segment)

    if len(audio_segments) == 0:
        raise ValueError("No speech segments were found in the audio")

    connected_audio = audio_segments[0]
    for i in range(1, len(audio_segments)):
        connected_audio += audio_segments[i]

    return connected_audio, timestamps
    