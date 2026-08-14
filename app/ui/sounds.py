from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from app.core.config import AppConfig
from app.utils.helpers import resource_path


SOUND_FILES = {
    "soft": "sound-soft.wav",
    "chime": "sound-chime.wav",
    "pop": "sound-pop.wav",
}


class NotificationSound:
    def __init__(self, config: AppConfig) -> None:
        self._effect = QSoundEffect()
        self._enabled = True
        self._name = ""
        self.apply_config(config)

    def apply_config(self, config: AppConfig) -> None:
        self._enabled = config.sound_enabled
        name = config.sound_name if config.sound_name in SOUND_FILES else "soft"
        if name != self._name:
            self._name = name
            path = resource_path(f"assets/{SOUND_FILES[name]}")
            self._effect.setSource(QUrl.fromLocalFile(str(path)))
        self._effect.setVolume(max(0.0, min(1.0, config.sound_volume / 100)))

    def play(self) -> None:
        if self._enabled:
            self._effect.play()

    def preview(self, config: AppConfig) -> None:
        self.apply_config(config)
        self._effect.play()

