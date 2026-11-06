"""Local WAV file operations used by the ClarityScribe orchestrator."""

import logging
import os
import shutil
import sys
import tempfile
import wave
from array import array
from pathlib import Path

from src.database.exceptions import UserInputError


logger = logging.getLogger(__name__)


def _session_dir(data_dir: Path | str, patient_id: str, session_id: str) -> Path:
    """Build an audio directory without allowing identifiers to escape it."""
    for identifier in (patient_id, session_id):
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in (".", "..")
            or Path(identifier).name != identifier
            or "/" in identifier
            or "\\" in identifier
        ):
            raise UserInputError("Invalid patient or session identifier")
    return Path(data_dir) / "audio" / patient_id / session_id


def import_wav(
    source: Path | str,
    data_dir: Path | str,
    patient_id: str,
    session_id: str,
) -> Path:
    """Validate and atomically install a stereo WAV as session audio.wav.

    On failure, any existing audio.wav is retained. A temporary copy is
    removed, and a newly created empty session directory is cleaned up.
    """
    source_path = Path(source)
    if source_path.suffix.lower() != ".wav":
        raise UserInputError("Потрібен файл формату .wav")

    try:
        with wave.open(str(source_path), "rb") as wav_in:
            if wav_in.getnchannels() != 2:
                raise UserInputError("Потрібен двоканальний .wav")
    except (wave.Error, EOFError) as exc:
        raise UserInputError("Некоректний WAV-файл") from exc
    except OSError as exc:
        raise UserInputError("Не вдалося відкрити WAV-файл") from exc

    session_dir = _session_dir(data_dir, patient_id, session_id)
    dest_file = session_dir / "audio.wav"
    try:
        if source_path.resolve() == dest_file.resolve():
            return dest_file
    except OSError as exc:
        raise UserInputError("Не вдалося визначити шлях WAV-файлу") from exc

    existed_before = session_dir.exists()
    temp_path = None
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        # Keep the temporary file beside the destination for atomic replace.
        with tempfile.NamedTemporaryFile(
            prefix=".audio-", suffix=".tmp", dir=session_dir, delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            with source_path.open("rb") as source_file:
                shutil.copyfileobj(source_file, temp_file)

        os.replace(temp_path, dest_file)
    except OSError as exc:
        raise UserInputError("Не вдалося зберегти WAV-файл") from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to remove temporary WAV %s: %s", temp_path, exc)
        if not existed_before:
            try:
                session_dir.rmdir()  # Only removes an empty directory.
            except OSError:
                pass  # A successful copy leaves audio.wav in the directory.

    return dest_file


def duration_seconds(path: Path | str) -> float:
    """Return WAV duration in seconds or raise UserInputError."""
    try:
        with wave.open(str(path), "rb") as wav_in:
            rate = wav_in.getframerate()
            if rate <= 0:
                raise UserInputError("Некоректна частота дискретизації WAV")
            return wav_in.getnframes() / rate
    except (wave.Error, EOFError, OSError) as exc:
        raise UserInputError("Не вдалося визначити тривалість WAV-файлу") from exc


def waveform_peaks(path: Path | str, bins: int = 900) -> list[float]:
    """Return normalized maximum absolute amplitudes per time bin.

    Read only the frames in the current bin. Unsupported sample widths and
    unreadable files return an empty list. Empty bins have zero amplitude.
    """
    if bins <= 0:
        return []

    try:
        with wave.open(str(path), "rb") as wav_in:
            if wav_in.getsampwidth() != 2:
                return []

            total_frames = wav_in.getnframes()
            if total_frames == 0:
                return [0.0] * bins

            peaks = []
            for index in range(bins):
                start_frame = index * total_frames // bins
                end_frame = (index + 1) * total_frames // bins
                count = end_frame - start_frame
                if count == 0:
                    peaks.append(0.0)
                    continue

                wav_in.setpos(start_frame)
                samples = array("h")
                samples.frombytes(wav_in.readframes(count))
                if sys.byteorder != "little":
                    samples.byteswap()
                peak = max((abs(value) for value in samples), default=0)
                peaks.append(round(min(peak / 32768.0, 1.0), 4))

            return peaks
    except (wave.Error, EOFError, OSError, ValueError) as exc:
        logger.warning("Failed to read waveform from %s: %s", path, exc)
        return []


def delete_session_dir(data_dir: Path | str, patient_id: str, session_id: str) -> None:
    """Remove session audio after database commit; log filesystem failures."""
    session_dir = _session_dir(data_dir, patient_id, session_id)
    try:
        shutil.rmtree(session_dir)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Failed to delete session directory %s: %s", session_dir, exc)


def delete_patient_dir(data_dir: Path | str, patient_id: str) -> None:
    """Remove all patient audio after database commit; log failures."""
    # Apply the same identifier validation used by session paths.
    _session_dir(data_dir, patient_id, "validation")
    patient_dir = Path(data_dir) / "audio" / patient_id
    try:
        shutil.rmtree(patient_dir)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Failed to delete patient directory %s: %s", patient_dir, exc)
