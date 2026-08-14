from __future__ import annotations

import ctypes
import os
from collections.abc import Callable

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QPushButton, QVBoxLayout, QWidget


_VK_MOUSE_BUTTONS = (0x01, 0x02, 0x04, 0x05, 0x06)


def _mouse_button_pressed() -> bool:
    if os.name == "nt":
        return any(ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000 for key in _VK_MOUSE_BUTTONS)
    return QApplication.mouseButtons() != Qt.MouseButton.NoButton


class TrayPopup(QWidget):
    """Mouse-driven tray menu that does not take focus from Explorer flyouts."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("trayPopup")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 14)
        self.panel = QFrame(self)
        self.panel.setObjectName("trayPopupPanel")
        outer_layout.addWidget(self.panel)

        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 210))
        self.panel.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            QWidget#trayPopup {
                background: transparent;
            }
            QFrame#trayPopupPanel {
                background-color: #18181b;
                border: 1px solid #8b5cf6;
                border-radius: 10px;
            }
            QFrame#trayPopupPanel QPushButton {
                background: transparent;
                color: #f4f4f5;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                text-align: left;
                min-width: 195px;
            }
            QFrame#trayPopupPanel QPushButton:hover {
                background-color: #7c3aed;
                color: #ffffff;
            }
        """)
        self._click_armed = False
        self._click_watch = QTimer(self)
        self._click_watch.setInterval(30)
        self._click_watch.timeout.connect(self._check_external_click)

        self._layout = QVBoxLayout(self.panel)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(2)

    def add_command(self, text: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text, self.panel)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False, fn=callback: self._run(fn))
        self._layout.addWidget(button)
        return button

    def add_separator(self) -> None:
        separator = QFrame(self.panel)
        separator.setFixedHeight(1)
        separator.setStyleSheet("border: none; background-color: #52525b; margin: 5px 8px;")
        self._layout.addWidget(separator)

    def show_at_cursor(self) -> None:
        self._click_armed = False
        self.adjustSize()
        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        point = QPoint(cursor.x() + 5, cursor.y() + 5)
        if screen:
            area = screen.availableGeometry()
            if point.x() + self.width() > area.right():
                point.setX(cursor.x() - self.width() - 5)
            if point.y() + self.height() > area.bottom():
                point.setY(cursor.y() - self.height() - 5)
            point.setX(max(area.left(), point.x()))
            point.setY(max(area.top(), point.y()))
        self.move(point)
        self.show()
        self.raise_()
        # Ignore the right button that opened the menu. Once it is released,
        # any later click outside behaves like light-dismiss in a normal menu.
        self._click_watch.start()

    def hideEvent(self, event) -> None:
        self._click_watch.stop()
        self._click_armed = False
        super().hideEvent(event)

    def _check_external_click(self) -> None:
        pressed = _mouse_button_pressed()
        if not self._click_armed:
            self._click_armed = not pressed
            return
        if pressed and not self.frameGeometry().contains(QCursor.pos()):
            self.hide()

    def _run(self, callback: Callable[[], None]) -> None:
        self.hide()
        callback()
