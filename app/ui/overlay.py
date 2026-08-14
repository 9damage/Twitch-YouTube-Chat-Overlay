from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QCloseEvent, QContextMenuEvent, QMouseEvent, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QScrollArea, QSizeGrip, QVBoxLayout, QWidget,
)

from app.core.config import AppConfig
from app.core.models import ChatMessage
from app.ui.message_widget import MessageWidget
from app.utils.windows import set_click_through
from app.utils.helpers import resource_path
from PySide6.QtGui import QIcon


class ResizeGrip(QSizeGrip):
    """Visible resize handle for a translucent frameless window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("Потяните, чтобы изменить размер оверлея")
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#DDD6FE"), 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        edge = self.width() - 4
        for offset in (0, 7, 14):
            painter.drawLine(edge - offset, edge, edge, edge - offset)
        painter.end()


class OverlayWindow(QWidget):
    settings_requested = Signal()
    exit_requested = Signal()
    geometry_changed = Signal(int, int, int, int)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.locked = False
        self._drag_offset: QPoint | None = None
        self._messages: deque[MessageWidget] = deque()
        self.setWindowTitle("Оверлей чата Twitch + YouTube")
        self.setWindowIcon(QIcon(str(resource_path("assets/app-icon.png"))))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._apply_window_flags()
        self.resize(config.overlay_width, config.overlay_height)
        self._build_ui()
        self.apply_config(config)

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)
        self.panel = QFrame()
        self.panel.setStyleSheet("QFrame#panel { background: rgba(9, 9, 11, 90); border: 2px solid rgba(167,139,250,245); border-radius: 10px; }")
        self.panel.setObjectName("panel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        self.header = QLabel("ОВЕРЛЕЙ ЧАТА   ·   РЕЖИМ РЕДАКТИРОВАНИЯ")
        self.header.setStyleSheet("color: #ffffff; background: rgba(124,58,237,180); border-radius: 5px; font-size: 11px; font-weight: 700; padding: 5px 8px;")
        panel_layout.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.messages_layout = QVBoxLayout(self.container)
        # The small vertical inset keeps rounded corners and shadows away from
        # the scroll area's clipping boundary.
        self.messages_layout.setContentsMargins(2, 5, 2, 5)
        self.messages_layout.setSpacing(self.config.message_spacing)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.container)
        panel_layout.addWidget(self.scroll)
        grip_row = QHBoxLayout()
        grip_row.addStretch()
        self.grip = ResizeGrip(self)
        grip_row.addWidget(self.grip)
        panel_layout.addLayout(grip_row)
        outer.addWidget(self.panel)

    def add_message(self, message: ChatMessage) -> None:
        widget = MessageWidget(message, self.config)
        self.messages_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignLeft)
        self._messages.append(widget)
        if self.config.message_lifetime > 0:
            QTimer.singleShot(self.config.message_lifetime * 1000, lambda w=widget: self.remove_message(w))
        QTimer.singleShot(0, lambda w=widget: self._finalize_added_message(w))

    def _finalize_added_message(self, widget: MessageWidget) -> None:
        if widget not in self._messages:
            return
        viewport = self.scroll.viewport()
        left, top, right, bottom = self.messages_layout.getContentsMargins()
        available_height = max(0, viewport.height() - top - bottom)
        available_width = max(1, viewport.width() - left - right)
        spacing = max(0, self.messages_layout.spacing())
        targets = {item: item.prepare_for_width(available_width) for item in self._messages}

        # A card taller than the entire message area cannot ever be displayed
        # without clipping, so it is the only case where the new card is
        # discarded.
        if targets[widget] > available_height:
            self._discard_widget(widget)
            return

        remaining = list(self._messages)
        victims: list[MessageWidget] = []

        def total_height(items: list[MessageWidget]) -> int:
            return sum(targets[item] for item in items) + spacing * max(0, len(items) - 1)

        while len(remaining) > 1 and (
            len(remaining) > self.config.maximum_messages
            or total_height(remaining) > available_height
        ):
            victims.append(remaining.pop(0))

        for victim in victims:
            self._discard_widget(victim)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _fit_messages_to_viewport(self) -> None:
        if not self._messages:
            return
        viewport = self.scroll.viewport()
        left, top, right, bottom = self.messages_layout.getContentsMargins()
        available_height = max(0, viewport.height() - top - bottom)
        available_width = max(1, viewport.width() - left - right)
        spacing = max(0, self.messages_layout.spacing())

        def occupied_height() -> int:
            heights = [widget.prepare_for_width(available_width) for widget in self._messages]
            return sum(heights) + spacing * max(0, len(heights) - 1)

        # Messages grow from top to bottom. If the next card cannot fit fully,
        # discard that bottom card instead of showing a clipped fragment.
        while self._messages and occupied_height() > available_height:
            self._discard_widget(self._messages[-1])
        self.messages_layout.activate()

    def remove_message(self, widget: MessageWidget) -> None:
        if widget not in self._messages:
            return
        self._discard_widget(widget)

    def _discard_widget(self, widget: MessageWidget) -> None:
        try:
            self._messages.remove(widget)
        except ValueError:
            pass
        self.messages_layout.removeWidget(widget)
        widget.deleteLater()

    def clear_messages(self) -> None:
        for widget in tuple(self._messages):
            self.remove_message(widget)

    def set_locked(self, locked: bool) -> None:
        self.locked = locked
        self.header.setVisible(not locked)
        self.grip.setVisible(not locked)
        self.panel.setStyleSheet("QFrame#panel { background: transparent; border: none; }" if locked else "QFrame#panel { background: rgba(9,9,11,90); border: 2px solid rgba(167,139,250,245); border-radius: 10px; }")
        if self.winId():
            set_click_through(int(self.winId()), locked)

    def toggle_locked(self) -> None:
        self.set_locked(not self.locked)

    def apply_config(self, config: AppConfig) -> None:
        flags_changed = self.config.always_on_top != config.always_on_top
        self.config = config
        if flags_changed:
            visible = self.isVisible()
            self._apply_window_flags()
            if visible:
                self.show()
        self.resize(config.overlay_width, config.overlay_height)
        self.messages_layout.setSpacing(config.message_spacing)
        self.set_locked(config.click_through)
        QTimer.singleShot(0, self._fit_messages_to_viewport)

    def reset_position(self) -> None:
        screen = self.screen() or self.windowHandle().screen()
        area = screen.availableGeometry()
        self.resize(420, 600)
        self.move(area.right() - self.width() - 40, area.top() + 40)

    def ensure_on_screen(self) -> None:
        if any(screen.availableGeometry().intersects(self.frameGeometry()) for screen in QApplication.screens()):
            return
        self.reset_position()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        self._emit_geometry()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_messages_to_viewport)
        QTimer.singleShot(0, self._emit_geometry)

    def _emit_geometry(self) -> None:
        self.geometry_changed.emit(self.x(), self.y(), self.width(), self.height())

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if self.locked:
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #18181b;
                color: #f4f4f5;
                border: 1px solid #52525b;
                border-radius: 8px;
                padding: 5px 0;
            }
            QMenu::item {
                background-color: transparent;
                padding: 7px 25px 7px 14px;
                margin: 1px 5px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #7c3aed;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #71717a;
                margin: 6px 9px;
            }
        """)
        lock = menu.addAction("Скрыть границы")
        settings = menu.addAction("Настройки")
        clear = menu.addAction("Очистить чат")
        hide = menu.addAction("Скрыть оверлей")
        menu.addSeparator()
        quit_action = menu.addAction("Выход")
        chosen = menu.exec(event.globalPos())
        if chosen is lock:
            self.set_locked(True)
        elif chosen is settings:
            self.settings_requested.emit()
        elif chosen is clear:
            self.clear_messages()
        elif chosen is hide:
            self.hide()
        elif chosen is quit_action:
            self.exit_requested.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
