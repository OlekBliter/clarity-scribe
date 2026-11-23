"""Build the facade the UI works with: the stub or the real implementation."""
from __future__ import annotations

import os
from pathlib import Path

from .facade import ClarityScribeFacade

# Database file name inside the data directory.
_DB_FILE = "clarityscribe.db"

# Repository root: relative CLARITYSCRIBE_DATA_DIR values are resolved from here.
_ROOT = Path(__file__).resolve().parents[3]


def data_directory() -> Path:
    """Return the data directory for ``clarityscribe.db`` and ``audio/``.

    Uses ``CLARITYSCRIBE_DATA_DIR`` from the environment or ``.env``; a relative
    value is resolved from the repository root. If it is empty, falls back to
    ``%APPDATA%/clarityscribe`` (``~/.clarityscribe`` on other platforms).
    The directory is created if it does not exist.
    """
    from dotenv import dotenv_values

    value = os.getenv("CLARITYSCRIBE_DATA_DIR")
    if value is None:
        value = dotenv_values(_ROOT / ".env").get("CLARITYSCRIBE_DATA_DIR") or ""
    value = value.strip()
    if value:
        directory = _ROOT / Path(value).expanduser()
    elif os.getenv("APPDATA"):
        directory = Path(os.environ["APPDATA"]) / "clarityscribe"
    else:
        directory = Path.home() / ".clarityscribe"
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_facade(use_stub: bool = True) -> ClarityScribeFacade:
    """Return a ready facade.

    Heavy imports happen inside the function, so the stub mode does not load
    the Orchestrator, Vosk or other ML libraries.

    Args:
        use_stub: ``True`` for the demo stub, ``False`` for the real facade.
    """
    if use_stub:
        from .stub import ClarityScribeFacadeStub

        return ClarityScribeFacadeStub()

    directory = data_directory()
    from dotenv import load_dotenv

    load_dotenv(directory / ".env", override=False)
    load_dotenv(_ROOT / ".env", override=False)

    from src.database.connection import Database
    from src.services.orchestrator import Orchestrator, build_default_systems

    from .impl import ClarityScribeFacadeImpl

    db = Database(directory / _DB_FILE)
    db.init_schema()
    orchestrator = Orchestrator(db, build_default_systems(), directory)
    orchestrator.retry_audio_cleanup()
    return ClarityScribeFacadeImpl(orchestrator, db)
