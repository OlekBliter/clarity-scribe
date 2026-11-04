from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pathlib import Path
from .exceptions import InvalidAudioError

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

    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise InvalidAudioError("audio_path must be a non-empty path.")
    if not isinstance(channel_map, dict) or not channel_map:
        raise InvalidAudioError("channel_map must be a non-empty dictionary.")

    audio_path = Path(path)
    if not audio_path.is_file():
        raise InvalidAudioError(f"Audio file not found: '{path}'")
        
    try:
        full_audio = AudioSegment.from_file(path)
    except (CouldntDecodeError, OSError, FileNotFoundError) as error:
        raise InvalidAudioError(
            f"Failed to load or decode audio file '{path}': {error}"
        ) from error
   
    channels = full_audio.split_to_mono()
    num_channels = len(channels)

    for role, idx in channel_map.items():
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
            raise InvalidAudioError(
                f"Channel index for role '{role}' must be a non-negative integer: {idx}"
            )
        if idx >= num_channels:
            raise InvalidAudioError(
                f"Role '{role}' requires channel index {idx}, but the audio file "
                f"only has {num_channels} channel(s)."
            )

    return {
        role: channels[idx].set_frame_rate(16000).set_sample_width(2)
        for role, idx in channel_map.items()
    }