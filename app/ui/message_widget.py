from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPaintEvent, QPainter, QPalette, QPixmap, QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from app.core.config import AppConfig
from app.core.colors import YOUTUBE_USERNAME_COLOR, twitch_username_color
from app.core.models import ChatMessage, Platform
from app.ui.styles import message_style
from app.utils.helpers import resource_path


class WrappingLabel(QLabel):
    """Plain-text label that also wraps very long words and links."""

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._build_layouts(max(1, width))[1]

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        width = self.width() if self.width() > 1 else hint.width()
        return QSize(hint.width(), self.heightForWidth(width))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        layouts, _ = self._build_layouts(max(1, self.contentsRect().width() - 2))
        origin = self.contentsRect().topLeft()
        for layout in layouts:
            layout.draw(painter, QPointF(origin))

    def _build_layouts(self, width: int) -> tuple[list[QTextLayout], int]:
        layouts: list[QTextLayout] = []
        y = 0.0
        paragraphs = self.text().split("\n")
        for paragraph in paragraphs:
            if not paragraph:
                y += self.fontMetrics().height()
                continue
            layout = QTextLayout(paragraph, self.font())
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            layout.setTextOption(option)
            layout.beginLayout()
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width)
                line.setPosition(QPointF(0, y))
                y += line.height()
            layout.endLayout()
            layouts.append(layout)
        return layouts, max(1, math.ceil(y))


def _capital_pixel_top(font: QFont) -> int:
    metrics = QFontMetrics(font)
    canvas = QPixmap(max(16, metrics.horizontalAdvance("H") + 4), metrics.height())
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setFont(font)
    painter.setPen(Qt.GlobalColor.white)
    painter.drawText(QPointF(0, metrics.ascent()), "H")
    painter.end()
    image = canvas.toImage()
    rows = [
        y
        for y in range(image.height())
        if any(image.pixelColor(x, y).alpha() > 32 for x in range(image.width()))
    ]
    return min(rows) if rows else 0


def _opaque_pixel_top(pixmap: QPixmap) -> int:
    image = pixmap.toImage()
    rows = [
        y
        for y in range(image.height())
        if any(image.pixelColor(x, y).alpha() > 8 for x in range(image.width()))
    ]
    return min(rows) if rows else 0


class MessageWidget(QFrame):
    def __init__(self, message: ChatMessage, config: AppConfig) -> None:
        super().__init__()
        self.message = message
        self._shadow_enabled = config.shadow
        self._target_height = 0
        self.setObjectName("messageCard")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        color = "#9146FF" if message.platform is Platform.TWITCH else "#FF0033"
        self.setStyleSheet(message_style(config, color))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 7, 10, 8)
        layout.setSpacing(4)
        common_font = QFont("Segoe UI", 10)
        common_font.setWeight(QFont.Weight.Bold)
        icon_name = "twitch-chat-icon.png" if message.platform is Platform.TWITCH else "youtube-chat-icon.png"
        icon_pixmap = QPixmap(str(resource_path(f"assets/{icon_name}")))
        font_metrics = QFontMetrics(common_font)
        icon_offset = _capital_pixel_top(common_font) - _opaque_pixel_top(icon_pixmap)
        icon_canvas_height = max(font_metrics.height(), 16 + max(0, icon_offset))
        icon_canvas = QPixmap(16, icon_canvas_height)
        icon_canvas.fill(Qt.GlobalColor.transparent)
        icon_painter = QPainter(icon_canvas)
        icon_painter.drawPixmap(0, icon_offset, icon_pixmap)
        icon_painter.end()
        platform_icon = QLabel()
        platform_icon.setFixedSize(16, icon_canvas_height)
        platform_icon.setPixmap(icon_canvas)
        platform_icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        platform_icon.setToolTip("Twitch" if message.platform is Platform.TWITCH else "YouTube")
        badges = []
        if message.is_owner:
            badges.append("ВЛАДЕЛЕЦ")
        elif message.is_moderator:
            badges.append("МОДЕРАТОР")
        if message.is_subscriber:
            badges.append("ПОДПИСЧИК")
        display = message.display_name
        username = QLabel(display)
        username.setToolTip(display + (f" · {' · '.join(badges)}" if badges else ""))
        username_color = (
            message.user_color or twitch_username_color(message.username)
            if message.platform is Platform.TWITCH
            else YOUTUBE_USERNAME_COLOR
        )
        username.setStyleSheet(f"color: {username_color};")
        username.setFont(common_font)
        username.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        username.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        username.setMaximumWidth(154)
        colon = QLabel(":")
        colon.setFont(common_font)
        colon.setStyleSheet(f"color: {config.text_color};")
        colon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        name_group = QWidget()
        name_group.setStyleSheet("background: transparent;")
        name_layout = QHBoxLayout(name_group)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(0)
        name_layout.addWidget(username)
        name_layout.addWidget(colon)
        name_group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        name_group.setMaximumWidth(160)
        body_text = message.message
        if message.donation_amount:
            body_text = f"СУПЕРЧАТ · {message.donation_amount}\n{body_text}"
        elif message.bits:
            body_text = f"ПОДДЕРЖКА · {message.bits} битов\n{body_text}"
        body = WrappingLabel(body_text)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        body.setFont(common_font)
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        body.setMinimumWidth(0)
        layout.addWidget(platform_icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(name_group, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body, 1, Qt.AlignmentFlag.AlignTop)
        self._restore_shadow()

    def expanded_height(self, width: int | None = None) -> int:
        layout = self.layout()
        target_width = max(1, width or self.width() or self.sizeHint().width())
        height = self.sizeHint().height()
        if layout is not None and layout.hasHeightForWidth():
            height = max(height, layout.heightForWidth(target_width))
        return max(1, height)

    def prepare_for_width(self, width: int) -> int:
        self.setMaximumWidth(max(1, width))
        self._target_height = self.expanded_height(width)
        self.setMinimumHeight(self._target_height)
        return self._target_height

    def _restore_shadow(self) -> None:
        self.setGraphicsEffect(None)
        if not self._shadow_enabled:
            return
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)
