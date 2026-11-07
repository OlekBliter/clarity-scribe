"""Local WAV file operations used by the ClarityScribe orchestrator."""

import logging
import os
import shutil
import sys
import tempfile
import wave
from array import array
from pathlib import Path

from src.services.orchestrator.errors import DoctorInputError, OrchestratorError


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
            raise OrchestratorError("Invalid patient or session identifier")
    return Path(data_dir) / "audio" / patient_id / session_id


def stage_wav(source: Path | str, data_dir: Path | str) -> Path:
    """Validate a stereo WAV and copy it to a temporary file inside the data dir.

    The slow part of importing a recording. It touches no session directory and
    needs no database lock. The caller must either pass the returned path to
    :func:`install_staged` or delete it.
    """
    source_path = Path(source)
    if source_path.suffix.lower() != ".wav":
        raise DoctorInputError("Потрібен файл формату .wav")

    try:
        with wave.open(str(source_path), "rb") as wav_in:
            if wav_in.getnchannels() != 2:
                raise DoctorInputError("Потрібен двоканальний .wav")
            if wav_in.getnframes() == 0:
                raise DoctorInputError("WAV-файл порожній")
    except (wave.Error, EOFError) as exc:
        raise DoctorInputError("Некоректний WAV-файл") from exc
    except OSError as exc:
        raise DoctorInputError("Не вдалося відкрити WAV-файл") from exc

    staging_dir = Path(data_dir) / "audio"
    temp_path: Path | None = None
    try:
        staging_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=".staging-", suffix=".tmp", dir=staging_dir, delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            with source_path.open("rb") as source_file:
                shutil.copyfileobj(source_file, temp_file)
    except OSError as exc:
        discard_staged(temp_path)
        raise DoctorInputError("Не вдалося зберегти WAV-файл") from exc
    return temp_path


def discard_staged(staged: Path | None) -> None:
    """Remove a staged file if it still exists; log filesystem failures."""
    if staged is None:
        return
    try:
        staged.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to remove temporary WAV %s: %s", staged, exc)


def install_staged(
    staged: Path,
    data_dir: Path | str,
    patient_id: str,
    session_id: str,
) -> Path:
    """Atomically move a staged WAV to ``audio/<patient>/<session>/audio.wav``.

    A rename on the same filesystem: fast enough to run inside a transaction.
    """
    session_dir = _session_dir(data_dir, patient_id, session_id)
    dest_file = session_dir / "audio.wav"
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        os.replace(staged, dest_file)
    except OSError as exc:
        raise DoctorInputError("Не вдалося зберегти WAV-файл") from exc
    return dest_file


def import_wav(
    source: Path | str,
    data_dir: Path | str,
    patient_id: str,
    session_id: str,
) -> Path:
    """Validate and atomically install a stereo WAV as session audio.wav.

    On failure, any existing audio.wav is retained and the temporary copy is
    removed.
    """
    dest_file = _session_dir(data_dir, patient_id, session_id) / "audio.wav"
    try:
        if Path(source).resolve() == dest_file.resolve():
            return dest_file
    except OSError as exc:
        raise DoctorInputError("Не вдалося визначити шлях WAV-файлу") from exc

    staged = stage_wav(source, data_dir)
    try:
        return install_staged(staged, data_dir, patient_id, session_id)
    finally:
        discard_staged(staged)


def duration_seconds(path: Path | str) -> float:
    """Return WAV duration in seconds or raise DoctorInputError."""
    try:
        with wave.open(str(path), "rb") as wav_in:
            rate = wav_in.getframerate()
            if rate <= 0:
                raise DoctorInputError("Некоректна частота дискретизації WAV")
            return wav_in.getnframes() / rate
    except (wave.Error, EOFError, OSError) as exc:
        raise DoctorInputError("Не вдалося визначити тривалість WAV-файлу") from exc


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
