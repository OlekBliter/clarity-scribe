from pydub import AudioSegment

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
    full_audio = AudioSegment.from_file(path)   
    channels = full_audio.split_to_mono()

    return {role: channels[idx].set_frame_rate(16000).set_sample_width(2) for role, idx in channel_map.items()}