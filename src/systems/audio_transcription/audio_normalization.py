from pydub.effects import normalize
from pydub import AudioSegment

def normalize_audio(audio: AudioSegment, headroom_db: float = 1.0, max_gain_db: float = 30.0) -> AudioSegment:
    """
    Scale the track so its peak is at -headroom_db dBFS, but never boost by
    more than max_gain_db (so a near-silent channel is not turned into loud noise).
    """
    if audio.max == 0:
        return audio
    gain = -headroom_db - audio.max_dBFS
    return audio.apply_gain(min(gain, max_gain_db))