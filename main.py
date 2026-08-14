from __future__ import annotations

import asyncio
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from qasync import QEventLoop

from app.controller import ApplicationController
from app.core.config import ConfigManager
from app.core.logger import configure_logging
from app.ui.styles import application_stylesheet
from app.utils.helpers import resource_path


def main() -> int:
    configure_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Оверлей чата Twitch + YouTube")
    app.setOrganizationName("ChatOverlay")
    app.setWindowIcon(QIcon(str(resource_path("assets/app-icon.png"))))
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(application_stylesheet())
    manager = ConfigManager()
    manager.load()
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    controller = ApplicationController(app, manager)
    app.aboutToQuit.connect(loop.stop)
    with loop:
        loop.run_until_complete(controller.start())
        loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
