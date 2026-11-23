"""Точка входу UI.

Запуск з кореня репозиторію:
    python -m src.app.main --stub      # заглушка (для розробки фронтенду)
    python -m src.app.main             # реальний фасад (коли буде готовий)
"""
from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

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
    return create_facade(False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ClarityScribe")
    parser.add_argument("--stub", action="store_true", help="працювати із заглушкою фасаду")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ClarityScribe")
    load_theme(app)

    try:
        if not args.stub:
            from src.services.facade.factory import data_directory
            directory = data_directory()
            instance_lock = QLockFile(str(directory / "application.lock"))
            instance_lock.setStaleLockTime(0)
            if not instance_lock.tryLock(0):
                QMessageBox.warning(None, "ClarityScribe",
                                    "Не вдалося отримати доступ до каталогу даних. Перевірте, чи вже відкрито застосунок.")
                return 1
            from src.services.orchestrator.audio_files import clean_staged_imports
            clean_staged_imports(directory)

        window = MainWindow(make_facade(args.stub))
    except Exception as exc:
        logging.getLogger(__name__).error("Startup failed: %s", type(exc).__name__)
        QMessageBox.critical(None, "ClarityScribe",
                             "Не вдалося запустити застосунок. Перевірте доступ до каталогу даних і встановлені залежності.")
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
