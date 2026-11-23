"""Resolve configured model locations independently of the launch directory."""
from pathlib import Path


def model_path(value: str) -> Path:
    return (Path(__file__).resolve().parents[2] / Path(value).expanduser()).resolve()
