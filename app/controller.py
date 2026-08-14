from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from PySide6.QtCore import QObject, QPoint, QRect, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle, QSystemTrayIcon

from app.core.config import AppConfig, ConfigManager
from app.core.event_bus import EventBus
from app.core.filters import MessageFilter
from app.core.models import ChatMessage, ConnectionStatus, Platform
from app.twitch.client import TwitchClient
from app.ui.hotkeys import GlobalHotkeyFilter
from app.ui.overlay import OverlayWindow
from app.ui.settings_window import SettingsWindow
from app.ui.sounds import NotificationSound
from app.ui.tray_popup import TrayPopup
from app.utils.helpers import resource_path
from app.utils.windows import set_startup
from app.youtube.client import YouTubeClient


class StatusBridge(QObject):
    changed = Signal(str, object, str)


class ApplicationController(QObject):
    def __init__(self, app: QApplication, manager: ConfigManager) -> None:
        super().__init__()
        self.app = app
        self.manager = manager
        self.config = manager.config
        self.bus = EventBus(1000)
        self.filter = self._make_filter()
        self.overlay = OverlayWindow(self.config)
        self.settings = SettingsWindow(self.config)
        self.sound = NotificationSound(self.config)
        self.status = StatusBridge()
        self.status.changed.connect(self.settings.update_status)
        self.twitch: TwitchClient | None = None
        self.youtube: YouTubeClient | None = None
        self.tasks: dict[str, asyncio.Task] = {}
        self._consumer: asyncio.Task | None = None
        self._closing = False
        self._settings_positioned = False
        self._logger = logging.getLogger(__name__)
        self._connect_ui()
        self._create_tray()
        self._hotkeys: GlobalHotkeyFilter | None = None

    def _make_filter(self) -> MessageFilter:
        return MessageFilter(
            self.config.hide_commands,
            set(self.config.ignored_usernames),
            set(self.config.ignored_words),
        )

    def _connect_ui(self) -> None:
        self.overlay.settings_requested.connect(self.show_settings)
        self.overlay.exit_requested.connect(lambda: asyncio.create_task(self.shutdown()))
        self.overlay.geometry_changed.connect(self._save_geometry)
        self.settings.applied.connect(self.apply_settings)
        self.settings.test_message_requested.connect(self.send_test_messages)
        self.settings.reset_position_requested.connect(self.overlay.reset_position)
        self.settings.sound_preview_requested.connect(self.sound.preview)

    def _create_tray(self) -> None:
        icon = QIcon(str(resource_path("assets/tray-icon.png")))
        if icon.isNull():
            icon = self.app.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Оверлей чата Twitch + YouTube")
        self.tray_menu = TrayPopup()
        self.lock_action = self.tray_menu.add_command("Скрыть границы", self.overlay.toggle_locked)
        self.visibility_action = self.tray_menu.add_command("Показать оверлей", self.toggle_overlay)
        self.tray_menu.add_command("Настройки", self.show_settings)
        self.tray_menu.add_separator()
        self.tray_menu.add_command(
            "Переподключить Twitch",
            lambda: asyncio.create_task(self.restart_client("twitch")),
        )
        self.tray_menu.add_command(
            "Переподключить YouTube",
            lambda: asyncio.create_task(self.restart_client("youtube")),
        )
        self.tray_menu.add_separator()
        self.tray_menu.add_command("Выход", lambda: asyncio.create_task(self.shutdown()))
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_overlay()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self._update_tray_actions()
            self.tray_menu.show_at_cursor()

    def _update_tray_actions(self) -> None:
        self.visibility_action.setText("Скрыть оверлей" if self.overlay.isVisible() else "Показать оверлей")
        self.lock_action.setText("Показать границы" if self.overlay.locked else "Скрыть границы")

    async def start(self) -> None:
        if self.config.overlay_x is None or self.config.overlay_y is None:
            self.overlay.reset_position()
        else:
            self.overlay.move(self.config.overlay_x, self.config.overlay_y)
            self.overlay.ensure_on_screen()
        if not self.config.start_minimized:
            self.overlay.show()
        if not self.config.twitch_configured and not self.config.youtube_configured:
            self.show_settings()
        self._consumer = asyncio.create_task(self._consume(), name="message-consumer")
        await self.restart_client("twitch")
        await self.restart_client("youtube")
        self._register_hotkeys()

    def _register_hotkeys(self) -> None:
        bindings = {
            1: (self.config.hotkey_overlay, self.toggle_overlay),
            2: (self.config.hotkey_lock, self.overlay.toggle_locked),
            3: (self.config.hotkey_settings, self.show_settings),
        }
        self._hotkeys = GlobalHotkeyFilter(int(self.overlay.winId()), bindings)
        self.app.installNativeEventFilter(self._hotkeys)

    async def _consume(self) -> None:
        while True:
            message = await self.bus.next()
            try:
                if self.filter.should_display(message):
                    self.overlay.add_message(message)
                    self.sound.play()
            finally:
                self.bus.queue.task_done()

    async def restart_client(self, platform: str) -> None:
        old = self.tasks.pop(platform, None)
        client = self.twitch if platform == "twitch" else self.youtube
        if client:
            await client.stop()
        if old:
            old.cancel()
            await asyncio.gather(old, return_exceptions=True)
        callback = lambda status, detail, p=platform: self.status.changed.emit(p, status, detail)
        if platform == "twitch":
            self.twitch = TwitchClient(self.config, self.bus, callback)
            if self.config.twitch_enabled:
                self.tasks[platform] = asyncio.create_task(self.twitch.run(), name="twitch-client")
        else:
            self.youtube = YouTubeClient(self.config, self.bus, callback)
            if self.config.youtube_enabled:
                self.tasks[platform] = asyncio.create_task(self.youtube.run(), name="youtube-client")

    def apply_settings(self, config: AppConfig) -> None:
        old = self.config
        self.config = config
        self.manager.save(config)
        self.filter = self._make_filter()
        self.sound.apply_config(config)
        self.overlay.apply_config(config)
        try:
            set_startup(config.start_with_windows, self.manager.executable_path())
        except OSError as exc:
            self._logger.warning("Could not update Windows startup: %s", exc)
        if (old.twitch_enabled, old.twitch_channel, old.twitch_oauth_token) != (config.twitch_enabled, config.twitch_channel, config.twitch_oauth_token):
            asyncio.create_task(self.restart_client("twitch"))
        if (old.youtube_enabled, old.youtube_api_key, old.youtube_channel) != (config.youtube_enabled, config.youtube_api_key, config.youtube_channel):
            asyncio.create_task(self.restart_client("youtube"))

    def _save_geometry(self, x: int, y: int, width: int, height: int) -> None:
        self.config.overlay_x, self.config.overlay_y = x, y
        self.config.overlay_width, self.config.overlay_height = width, height
        try:
            self.manager.save(self.config)
        except OSError as exc:
            self._logger.warning("Could not save overlay geometry: %s", exc)

    def send_test_messages(self) -> None:
        self.bus.publish_nowait(ChatMessage(Platform.TWITCH, "ninedamage", "NineDamage", "Привет! 💜", datetime.now(UTC), "#A78BFA", ["subscriber/12"], is_subscriber=True))
        self.bus.publish_nowait(ChatMessage(Platform.YOUTUBE, "viewer123", "Зритель123", "Отличный стрим! 🎬", datetime.now(UTC), "#FDA4AF", is_moderator=True))

    def show_settings(self) -> None:
        self.settings.load(self.config)
        if not self._settings_positioned:
            self._position_settings_away_from_overlay()
            self._settings_positioned = True
        self.settings.show(); self.settings.raise_(); self.settings.activateWindow()

    def _position_settings_away_from_overlay(self) -> None:
        """Place settings close to the overlay without overlapping it."""
        screen = self.overlay.screen() or self.app.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        gap = 24
        size = self.settings.size()
        overlay = self.overlay.frameGeometry()
        candidates = (
            QPoint(overlay.left() - size.width() - gap, overlay.top()),
            QPoint(overlay.right() + gap + 1, overlay.top()),
            QPoint(overlay.left(), overlay.bottom() + gap + 1),
            QPoint(overlay.left(), overlay.top() - size.height() - gap),
        )
        for point in candidates:
            target = QRect(point, size)
            if area.contains(target):
                self.settings.move(point)
                return

        # Very small screens may not fit both windows side by side. Keep the
        # settings inside the screen and maximize the distance without overlap.
        x = max(area.left(), min(candidates[0].x(), area.right() - size.width() + 1))
        y = max(area.top(), min(overlay.top(), area.bottom() - size.height() + 1))
        self.settings.move(QPoint(x, y))

    def toggle_overlay(self) -> None:
        self.overlay.hide() if self.overlay.isVisible() else self.overlay.show()

    async def shutdown(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.manager.save(self.config)
        if self._hotkeys:
            self._hotkeys.unregister()
            self.app.removeNativeEventFilter(self._hotkeys)
        for client in (self.twitch, self.youtube):
            if client:
                await client.stop()
        for task in self.tasks.values():
            task.cancel()
        if self._consumer:
            self._consumer.cancel()
        await asyncio.gather(*self.tasks.values(), *( [self._consumer] if self._consumer else []), return_exceptions=True)
        self.tray.hide()
        self.app.quit()
