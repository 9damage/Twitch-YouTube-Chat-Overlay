from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from app.core.config import AppConfig
from app.core.models import ConnectionStatus
from app.utils.helpers import resource_path
from PySide6.QtGui import QIcon


class CredentialsHelp(QFrame):
    """Compact credential help that appears immediately on hover."""

    def __init__(self, help_html: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("credentialsHelp")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QFrame#credentialsHelp {
                background-color: rgba(124, 58, 237, 38);
                border: 1px solid #7c3aed;
                border-radius: 6px;
            }
            QFrame#credentialsHelp:hover {
                background-color: rgba(139, 92, 246, 72);
                border-color: #a78bfa;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        text = QLabel("Где их получить?")
        text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text.setStyleSheet("color: #c4b5fd; font-weight: 700; background: transparent;")
        layout.addWidget(text)
        self.adjustSize()
        self.setFixedSize(self.sizeHint())

        self.popup = QFrame(
            self,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.popup.setObjectName("credentialsHelpPopup")
        self.popup.setStyleSheet("""
            QFrame#credentialsHelpPopup {
                background-color: #18181b;
                border: 1px solid #8b5cf6;
                border-radius: 7px;
            }
            QLabel { background: transparent; color: #f4f4f5; }
        """)
        popup_layout = QVBoxLayout(self.popup)
        popup_layout.setContentsMargins(11, 10, 11, 10)
        details = QLabel(help_html)
        details.setTextFormat(Qt.TextFormat.RichText)
        details.setWordWrap(True)
        details.setFixedWidth(390)
        popup_layout.addWidget(details)
        self.popup.adjustSize()

    def enterEvent(self, event) -> None:
        self._show_popup()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        QTimer.singleShot(90, self._hide_if_pointer_left)
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:
        self.popup.hide()
        super().hideEvent(event)

    def _show_popup(self) -> None:
        point = self.mapToGlobal(QPoint(0, self.height() + 6))
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            point.setX(max(area.left(), min(point.x(), area.right() - self.popup.width() + 1)))
            if point.y() + self.popup.height() > area.bottom():
                point.setY(self.mapToGlobal(QPoint(0, -self.popup.height() - 6)).y())
        self.popup.move(point)
        self.popup.show()

    def _hide_if_pointer_left(self) -> None:
        global_pos = QCursor.pos()
        if self.rect().contains(self.mapFromGlobal(global_pos)):
            return
        if self.popup.rect().contains(self.popup.mapFromGlobal(global_pos)):
            QTimer.singleShot(90, self._hide_if_pointer_left)
            return
        self.popup.hide()


class SettingsWindow(QDialog):
    applied = Signal(object)
    test_message_requested = Signal()
    reset_position_requested = Signal()
    sound_preview_requested = Signal(object)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setWindowTitle("Настройки оверлея чата")
        self.setWindowIcon(QIcon(str(resource_path("assets/app-icon.png"))))
        self.resize(590, 610)
        self._config = config
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self._general_tab()
        self._appearance_tab()
        self._twitch_tab()
        self._youtube_tab()
        self._hotkeys_tab()
        actions = QHBoxLayout()
        test = QPushButton("ОТПРАВИТЬ ТЕСТОВОЕ СООБЩЕНИЕ")
        test.clicked.connect(self.test_message_requested)
        reset_position = QPushButton("Сбросить положение")
        reset_position.clicked.connect(self.reset_position_requested)
        reset_appearance = QPushButton("Сбросить оформление")
        reset_appearance.clicked.connect(self._reset_appearance)
        actions.addWidget(test)
        actions.addWidget(reset_position)
        actions.addWidget(reset_appearance)
        root.addLayout(actions)
        buttons = QHBoxLayout()
        buttons.addStretch()
        apply_button = QPushButton("Применить")
        save_button = QPushButton("Сохранить")
        close_button = QPushButton("Закрыть")
        apply_button.clicked.connect(self._apply)
        save_button.clicked.connect(self._save)
        close_button.clicked.connect(self.hide)
        buttons.addWidget(apply_button)
        buttons.addWidget(save_button)
        buttons.addWidget(close_button)
        root.addLayout(buttons)
        self.load(config)

    def _new_tab(self, title: str) -> QFormLayout:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.tabs.addTab(widget, title)
        return form

    @staticmethod
    def _help_row(help_widget: CredentialsHelp) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.addWidget(help_widget)
        layout.addStretch()
        return container

    def _general_tab(self) -> None:
        form = self._new_tab("ОБЩИЕ")
        self.always_on_top = QCheckBox("Показывать оверлей поверх остальных окон")
        self.click_through = QCheckBox("Запускать со скрытыми границами (клики проходят сквозь окно)")
        self.startup = QCheckBox("Запускать вместе с Windows")
        self.start_minimized = QCheckBox("Запускать свёрнутым в область уведомлений")
        self.start_minimized_container = QWidget()
        minimized_layout = QHBoxLayout(self.start_minimized_container)
        minimized_layout.setContentsMargins(27, 0, 0, 0)
        minimized_layout.addWidget(self.start_minimized)
        minimized_layout.addStretch()
        self.startup.toggled.connect(self.start_minimized_container.setVisible)
        self.lifetime = QComboBox()
        self.lifetime.addItems(["0", "5", "10", "15", "30", "60"])
        self.maximum = QComboBox()
        self.maximum.addItems(["10", "20", "30", "50", "100"])
        self.hide_commands = QCheckBox("Скрывать сообщения, начинающиеся с !")
        self.sound_enabled = QCheckBox("Воспроизводить звук при новом сообщении")
        self.sound_name = QComboBox()
        self.sound_name.addItem("Мягкий", "soft")
        self.sound_name.addItem("Звонок", "chime")
        self.sound_name.addItem("Щелчок", "pop")
        self.sound_volume = QSpinBox(); self.sound_volume.setRange(0, 100); self.sound_volume.setSuffix(" %")
        preview_sound = QPushButton("Прослушать")
        preview_sound.clicked.connect(lambda: self.sound_preview_requested.emit(self.values()))
        self.ignored_users = QLineEdit()
        self.ignored_words = QLineEdit()
        form.addRow(self.always_on_top)
        form.addRow(self.click_through)
        form.addRow(self.startup)
        form.addRow(self.start_minimized_container)
        form.addRow("Время показа сообщения (секунд)", self.lifetime)
        form.addRow("Максимум сообщений", self.maximum)
        form.addRow(self.hide_commands)
        form.addRow(self.sound_enabled)
        form.addRow("Звук уведомления", self.sound_name)
        form.addRow("Громкость", self.sound_volume)
        form.addRow("", preview_sound)
        form.addRow("Игнорируемые пользователи (через запятую)", self.ignored_users)
        form.addRow("Игнорируемые слова (через запятую)", self.ignored_words)

    def _appearance_tab(self) -> None:
        form = self._new_tab("ОФОРМЛЕНИЕ")
        self.text_color = QPushButton("Выбрать цвет")
        self.text_color.clicked.connect(self._choose_color)
        self.opacity = QSpinBox(); self.opacity.setRange(0, 100); self.opacity.setSuffix(" %")
        self.shadow = QCheckBox("Тень текста и карточек")
        self.spacing = QSpinBox(); self.spacing.setRange(0, 30)
        self.width = QSpinBox(); self.width.setRange(260, 1600)
        self.height = QSpinBox(); self.height.setRange(200, 1400)
        form.addRow("Цвет текста", self.text_color)
        form.addRow("Прозрачность фона сообщений", self.opacity)
        form.addRow(self.shadow)
        form.addRow("Расстояние между сообщениями", self.spacing)
        form.addRow("Ширина оверлея", self.width)
        form.addRow("Высота оверлея", self.height)

    def _twitch_tab(self) -> None:
        form = self._new_tab("TWITCH")
        self.twitch_status = QLabel("Отключено")
        self.twitch_enabled = QCheckBox("Включить Twitch")
        self.twitch_channel = QLineEdit()
        self.twitch_token = QLineEdit(); self.twitch_token.setEchoMode(QLineEdit.EchoMode.Password)
        reveal = QPushButton("Показать / скрыть токен")
        reveal.clicked.connect(lambda: self._toggle_secret(self.twitch_token))
        form.addRow("Состояние", self.twitch_status)
        form.addRow(self.twitch_enabled)
        form.addRow("Канал", self.twitch_channel)
        form.addRow("Токен OAuth", self.twitch_token)
        form.addRow("", reveal)
        self.twitch_help = CredentialsHelp(
            "<b>Данные Twitch</b><br><br>"
            "<b>Канал:</b> название канала, чат которого нужно показывать. Например, "
            "для <code>twitch.tv/twitchdev</code> укажите <code>twitchdev</code>.<br>"
            "<b>Токен OAuth:</b> пользовательский токен Twitch с разрешением "
            "<code>chat:read</code>. Префикс <code>oauth:</code> можно не вводить.<br><br>"
            "Имя Twitch-пользователя вводить не нужно: приложение автоматически "
            "определяет владельца токена и проверяет токен при подключении."
        )
        form.addRow("", self._help_row(self.twitch_help))

    def _youtube_tab(self) -> None:
        form = self._new_tab("YOUTUBE")
        self.youtube_status = QLabel("Отключено")
        self.youtube_enabled = QCheckBox("Включить YouTube")
        self.youtube_key = QLineEdit(); self.youtube_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.youtube_channel = QLineEdit()
        reveal = QPushButton("Показать / скрыть ключ API")
        reveal.clicked.connect(lambda: self._toggle_secret(self.youtube_key))
        form.addRow("Состояние", self.youtube_status)
        form.addRow(self.youtube_enabled)
        form.addRow("Ключ API", self.youtube_key)
        form.addRow("Ссылка на канал", self.youtube_channel)
        form.addRow("", reveal)
        self.youtube_help = CredentialsHelp(
            "<b>Данные YouTube</b><br><br>"
            "Для чтения публичного чата нужны оба поля.<br><br>"
            "<b>Ключ API:</b> ключ проекта Google Cloud с включённым "
            "<i>YouTube Data API v3</i>. Вход в Google-аккаунт и OAuth не требуются.<br>"
            "<b>Ссылка на канал:</b> вставьте адрес вида "
            "<code>youtube.com/@имя</code> или <code>youtube.com/channel/UC...</code>. "
            "Можно также указать <code>@handle</code>.<br><br>"
            "Ссылка сохраняется один раз. Приложение само проверяет новые публикации "
            "канала, подключается к активному чату и после завершения эфира ожидает следующий."
        )
        form.addRow("", self._help_row(self.youtube_help))

    def _hotkeys_tab(self) -> None:
        form = self._new_tab("ГОРЯЧИЕ КЛАВИШИ")
        self.hotkey_overlay = QLineEdit()
        self.hotkey_lock = QLineEdit()
        self.hotkey_settings = QLineEdit()
        form.addRow("Показать / скрыть оверлей", self.hotkey_overlay)
        form.addRow("Скрыть / показать границы", self.hotkey_lock)
        form.addRow("Открыть настройки", self.hotkey_settings)
        form.addRow(QLabel("Изменения горячих клавиш вступят в силу после перезапуска программы."))

    @staticmethod
    def _toggle_secret(field: QLineEdit) -> None:
        mode = QLineEdit.EchoMode.Normal if field.echoMode() == QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password
        field.setEchoMode(mode)

    def _choose_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.text_color.property("value") or "#F4F4F5"), self)
        if chosen.isValid():
            self.text_color.setProperty("value", chosen.name())
            self.text_color.setStyleSheet(f"background: {chosen.name()};")

    def update_status(self, platform: str, status: ConnectionStatus, detail: str) -> None:
        label = self.twitch_status if platform == "twitch" else self.youtube_status
        names = {
            ConnectionStatus.DISCONNECTED: "Отключено",
            ConnectionStatus.CONNECTING: "Подключение",
            ConnectionStatus.CONNECTED: "Подключено",
            ConnectionStatus.WAITING: "Ожидание",
            ConnectionStatus.LIVE_ENDED: "Трансляция завершена",
            ConnectionStatus.ERROR: "Ошибка",
        }
        label.setText(f"{names[status]} — {detail}")

    def load(self, c: AppConfig) -> None:
        self._config = c
        self.always_on_top.setChecked(c.always_on_top); self.click_through.setChecked(c.click_through)
        self.startup.setChecked(c.start_with_windows)
        self.start_minimized.setChecked(c.start_minimized and c.start_with_windows)
        self.start_minimized_container.setVisible(c.start_with_windows)
        self.lifetime.setCurrentText(str(c.message_lifetime)); self.maximum.setCurrentText(str(c.maximum_messages))
        self.hide_commands.setChecked(c.hide_commands)
        self.sound_enabled.setChecked(c.sound_enabled)
        sound_index = self.sound_name.findData(c.sound_name)
        self.sound_name.setCurrentIndex(max(0, sound_index))
        self.sound_volume.setValue(c.sound_volume)
        self.ignored_users.setText(", ".join(c.ignored_usernames)); self.ignored_words.setText(", ".join(c.ignored_words))
        self.text_color.setProperty("value", c.text_color); self.text_color.setStyleSheet(f"background: {c.text_color};")
        self.opacity.setValue(c.background_opacity); self.shadow.setChecked(c.shadow); self.spacing.setValue(c.message_spacing)
        self.width.setValue(c.overlay_width); self.height.setValue(c.overlay_height)
        self.twitch_enabled.setChecked(c.twitch_enabled); self.twitch_channel.setText(c.twitch_channel)
        self.twitch_token.setText(c.twitch_oauth_token)
        self.youtube_enabled.setChecked(c.youtube_enabled); self.youtube_key.setText(c.youtube_api_key); self.youtube_channel.setText(c.youtube_channel)
        self.hotkey_overlay.setText(c.hotkey_overlay); self.hotkey_lock.setText(c.hotkey_lock); self.hotkey_settings.setText(c.hotkey_settings)

    def values(self) -> AppConfig:
        split = lambda text: [item.strip() for item in text.split(",") if item.strip()]
        return replace(
            self._config,
            always_on_top=self.always_on_top.isChecked(), click_through=self.click_through.isChecked(),
            start_minimized=self.startup.isChecked() and self.start_minimized.isChecked(), start_with_windows=self.startup.isChecked(),
            message_lifetime=int(self.lifetime.currentText()), maximum_messages=int(self.maximum.currentText()),
            sound_enabled=self.sound_enabled.isChecked(), sound_name=str(self.sound_name.currentData()),
            sound_volume=self.sound_volume.value(),
            hide_commands=self.hide_commands.isChecked(), ignored_usernames=split(self.ignored_users.text()), ignored_words=split(self.ignored_words.text()),
            text_color=self.text_color.property("value") or "#F4F4F5",
            background_opacity=self.opacity.value(), shadow=self.shadow.isChecked(), message_spacing=self.spacing.value(),
            overlay_width=self.width.value(), overlay_height=self.height.value(),
            twitch_enabled=self.twitch_enabled.isChecked(), twitch_channel=self.twitch_channel.text().strip(),
            twitch_oauth_token=self.twitch_token.text().strip(),
            youtube_enabled=self.youtube_enabled.isChecked(), youtube_api_key=self.youtube_key.text().strip(),
            youtube_channel=self.youtube_channel.text().strip(), hotkey_overlay=self.hotkey_overlay.text().strip(),
            hotkey_lock=self.hotkey_lock.text().strip(), hotkey_settings=self.hotkey_settings.text().strip(),
        )

    def _apply(self) -> None:
        self._config = self.values()
        self.applied.emit(self._config)

    def _save(self) -> None:
        self._apply()
        self.hide()

    def _reset_appearance(self) -> None:
        defaults = AppConfig()
        self.opacity.setValue(defaults.background_opacity)
        self.shadow.setChecked(defaults.shadow); self.spacing.setValue(defaults.message_spacing)
        self.width.setValue(defaults.overlay_width); self.height.setValue(defaults.overlay_height)
        self.text_color.setProperty("value", defaults.text_color); self.text_color.setStyleSheet(f"background: {defaults.text_color};")
