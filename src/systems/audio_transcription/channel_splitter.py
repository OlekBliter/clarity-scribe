from pydub import AudioSegment
from pathlib import Path

def split(path: str, channel_map: dict[str, int]) -> dict:
    """
    Split a multi-channel audio file into separate mono tracks, one per speaker role,
    and convert each track to the format expected by the speech recognizer.

    Args:
        path: Path to the audio file (any format supported by ffmpeg: wav, mp3, m4a, ...).
        channel_map: Maps a speaker role to the index of the channel that holds
            that speaker's voice, e.g. {"doctor": 0, "patient": 1}.
            Indices are zero-based: 0 is the left channel, 1 is the right channel.

    Returns:
        A dict {role: AudioSegment}, where every AudioSegment is mono,
        16 kHz, 16-bit (the format Vosk and most ASR models require).
    """

    audio_path = Path(path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: '{path}'")

    if not channel_map:
        raise ValueError("channel_map cannot be empty.")
        
    try:
        full_audio = AudioSegment.from_file(path)
    except Exception as e:
        raise ValueError(f"Failed to load or decode audio file '{path}': {e}") from e
   
    channels = full_audio.split_to_mono()
    num_channels = len(channels)

    for role, idx in channel_map.items():
        if idx < 0:
            raise ValueError(f"Channel index for role '{role}' cannot be negative: {idx}")
        if idx >= num_channels:
            raise ValueError(f"Role '{role}' requires channel index {idx}, but the audio file only has {num_channels} channel(s).")

    return {role: channels[idx].set_frame_rate(16000).set_sample_width(2) for role, idx in channel_map.items()}