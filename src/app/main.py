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
    """Створює фасад: заглушку (--stub, із затримкою кроків) або реальний."""
    if use_stub:
        # Заглушка зі затримкою кроків: create_facade(True) створює її з step_delay=0.0,
        # тоді всі етапи «виконуються» миттєво і анімації прогресу не видно.
        from src.services.facade import ClarityScribeFacadeStub
        return ClarityScribeFacadeStub(step_delay=0.6)
    from src.services.facade import create_facade
    try:
        return create_facade(False)
    except Exception as exc:  # noqa: BLE001 (немає залежності/моделі/.env: показуємо причину)
        logging.getLogger(__name__).exception("Не вдалося створити реальний фасад")
        raise SystemExit(
            f"Не вдалося запустити реальний фасад: {exc}\n"
            "Перевірте .env, моделі та залежності (requirements.txt); "
            "для розробки UI запустіть з --stub.") from exc


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
