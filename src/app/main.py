"""Точка входу UI.

Запуск з кореня репозиторію:
    python -m src.app.main --stub      # заглушка (для розробки фронтенду)
    python -m src.app.main             # реальний фасад (коли буде готовий)
"""
from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from src.app.ui.main_window import MainWindow
from src.app.ui.theme.loader import load_theme


def make_facade(use_stub: bool):
    """Створює фасад. Використовує create_facade, а якщо його ще немає
    (factory.py пишуть у команді фасаду), для --stub бере заглушку напряму.

    TODO: видалити запасний варіант, коли factory.py з'явиться в develop.
    """
    try:
        from src.services.facade import create_facade
    except ImportError:
        if not use_stub:
            raise SystemExit("create_facade ще не готовий: запускайте з --stub")
        from src.services.facade import ClarityScribeFacadeStub
        # step_delay: щоб на екрані обробки було видно прогрес
        return ClarityScribeFacadeStub(step_delay=0.6)
    return create_facade(use_stub)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ClarityScribe")
    parser.add_argument("--stub", action="store_true", help="працювати із заглушкою фасаду")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ClarityScribe")
    load_theme(app)

    window = MainWindow(make_facade(args.stub))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
