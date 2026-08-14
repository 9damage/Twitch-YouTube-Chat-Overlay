from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.core.secrets import SecretStore


def _bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class AppConfig:
    config_version: int = 2
    twitch_enabled: bool = True
    twitch_channel: str = ""
    twitch_oauth_token: str = ""
    youtube_enabled: bool = True
    youtube_api_key: str = ""
    youtube_channel: str = ""
    always_on_top: bool = True
    click_through: bool = False
    start_minimized: bool = False
    start_with_windows: bool = False
    text_color: str = "#F4F4F5"
    background_opacity: int = 52
    shadow: bool = True
    message_spacing: int = 8
    overlay_x: int | None = None
    overlay_y: int | None = None
    overlay_width: int = 420
    overlay_height: int = 600
    maximum_messages: int = 30
    message_lifetime: int = 30
    sound_enabled: bool = True
    sound_name: str = "soft"
    sound_volume: int = 65
    hide_commands: bool = False
    ignored_usernames: list[str] = field(default_factory=list)
    ignored_words: list[str] = field(default_factory=list)
    hotkey_overlay: str = "Ctrl+Shift+O"
    hotkey_lock: str = "Ctrl+Shift+L"
    hotkey_settings: str = "Ctrl+Shift+S"

    @property
    def twitch_configured(self) -> bool:
        return self.twitch_enabled and bool(self.twitch_channel and self.twitch_oauth_token)

    @property
    def youtube_configured(self) -> bool:
        return self.youtube_enabled and bool(self.youtube_api_key and self.youtube_channel)


class ConfigManager:
    def __init__(self, path: Path | None = None) -> None:
        env_path = (
            Path(sys.executable).resolve().parent / ".env"
            if getattr(sys, "frozen", False)
            else Path.cwd() / ".env"
        )
        load_dotenv(env_path)
        base = Path(os.getenv("APPDATA", Path.home())) / "ChatOverlay"
        self.path = path or base / "config.json"
        self.secrets = SecretStore(self.path.with_name("credentials.dat"))
        self.config = AppConfig()

    def load(self) -> AppConfig:
        data: dict[str, Any] = {}
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        try:
            config_version = int(data.get("config_version", 1))
        except (TypeError, ValueError):
            config_version = 1
        if config_version < 2:
            # Version 2 raises the former 15-second default to 30 seconds while
            # preserving any explicitly chosen non-default value.
            if data.get("message_lifetime", 15) == 15:
                data["message_lifetime"] = 30
            data["config_version"] = 2
        if not data.get("youtube_channel") and data.get("youtube_video_id"):
            # A previous version stored a video link. The YouTube client can
            # resolve it to its owner channel once, then follow future streams.
            data["youtube_channel"] = data["youtube_video_id"]
        valid = {item.name for item in fields(AppConfig)}
        self.config = AppConfig(**{k: v for k, v in data.items() if k in valid})
        try:
            saved_secrets = self.secrets.load()
        except (OSError, ValueError, json.JSONDecodeError):
            saved_secrets = {}
        env = os.environ
        for name in ("TWITCH_CHANNEL", "TWITCH_OAUTH_TOKEN", "YOUTUBE_API_KEY", "YOUTUBE_CHANNEL"):
            if env.get(name):
                setattr(self.config, name.lower(), env[name].strip())
        if not self.config.youtube_channel and env.get("YOUTUBE_VIDEO_ID"):
            self.config.youtube_channel = env["YOUTUBE_VIDEO_ID"].strip()
        if "TWITCH_ENABLED" in env:
            self.config.twitch_enabled = _bool(env["TWITCH_ENABLED"], True)
        if "YOUTUBE_ENABLED" in env:
            self.config.youtube_enabled = _bool(env["YOUTUBE_ENABLED"], True)
        # Values explicitly saved in the UI take precedence over legacy .env.
        if "twitch_oauth_token" in saved_secrets:
            self.config.twitch_oauth_token = saved_secrets["twitch_oauth_token"]
        if "youtube_api_key" in saved_secrets:
            self.config.youtube_api_key = saved_secrets["youtube_api_key"]
        return self.config

    def save(self, config: AppConfig | None = None) -> None:
        self.config = config or self.config
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        data = asdict(self.config)
        # Credentials belong in .env (or the process environment), never config.json.
        data.pop("twitch_oauth_token", None)
        data.pop("youtube_api_key", None)
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)
        self.secrets.save({
            "twitch_oauth_token": self.config.twitch_oauth_token,
            "youtube_api_key": self.config.youtube_api_key,
        })

    @staticmethod
    def executable_path() -> str:
        return str(Path(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]).resolve())
