"""Перевірка реального фасаду без UI: пацієнт -> сесія -> обробка -> SOAP.

Запуск з кореня репозиторію (потрібні .env, моделі та ключ Gemini):
    python scripts/smoke_facade.py path/to/stereo.wav
    python scripts/smoke_facade.py --stub --make-sample       # лише схема, без моделей

Дані пишуться в тимчасову теку (друкується в кінці), справжня база не чіпається.
Ключ API береться з .env у корені (GEMINI_API_KEY).
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def make_sample(path: Path, seconds: int = 3, rate: int = 16000) -> None:
    """Двоканальний тестовий .wav (два тони). Транскрипція з нього буде порожньою."""
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = bytearray()
        for i in range(seconds * rate):
            left = int(8000 * math.sin(2 * math.pi * 220 * i / rate))
            right = int(8000 * math.sin(2 * math.pi * 330 * i / rate))
            frames += struct.pack("<hh", left, right)
        out.writeframes(bytes(frames))


def step(title: str) -> None:
    print(f"\n== {title}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", nargs="?", help="двоканальний .wav")
    parser.add_argument("--stub", action="store_true", help="заглушка замість реального фасаду")
    parser.add_argument("--make-sample", action="store_true", help="згенерувати тестовий .wav")
    args = parser.parse_args()

    data_dir = Path(tempfile.mkdtemp(prefix="clarityscribe_smoke_"))
    import os
    os.environ["CLARITYSCRIBE_DATA_DIR"] = str(data_dir)

    wav = Path(args.wav) if args.wav else data_dir / "sample.wav"
    if args.make_sample or not args.wav:
        make_sample(wav)
        print("Тестовий wav:", wav)

    from src.services.facade import FacadeError, create_facade

    facade = create_facade(args.stub)
    try:
        step("settings")
        print(facade.get_settings())

        step("create_patient")
        pid = facade.create_patient({
            "preferred_name": "Тест Пацієнт", "birth_date": "1990-01-01",
            "phone": "+380 50 123 45 67", "email": "t@example.com",
            "preferred_channel": "Telegram"})
        print("patient_id:", pid, "| next number:", facade.next_session_number(pid))

        step("add_session")
        sid = facade.add_session(pid, str(wav), "uk", time.strftime("%Y-%m-%d"))
        print("session_id:", sid)

        step("process_session")
        facade.process_session(sid, lambda s, st: print(f"  {s}: {st}"))
        print(facade.get_processing_state(sid))

        step("get_soap")
        soap = facade.get_soap(sid)
        for key in ("subjective", "objective", "assessment"):
            print(key, "->", str(soap[key])[:200])
        print("plan ->", str(soap["plan"])[:200])

        step("get_transcript / audio / profile")
        print(len(facade.get_transcript(sid)), "segments;", facade.get_audio_info(sid))
        print(facade.get_patient_profile(pid))
        print("\nOK: повний цикл пройдено")
        return 0
    except FacadeError as exc:
        print("\nFacadeError:", exc.user_message)
        print("Деталі (traceback причини) дивіться в логах вище/нижче.")
        return 1
    finally:
        print("Дані тесту:", data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
