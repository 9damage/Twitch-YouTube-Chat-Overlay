from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Platform(StrEnum):
    TWITCH = "twitch"
    YOUTUBE = "youtube"


class ConnectionStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    WAITING = "waiting"
    LIVE_ENDED = "live ended"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class Emote:
    emote_id: str
    start: int
    end: int


@dataclass(slots=True)
class ChatMessage:
    platform: Platform
    username: str
    display_name: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    user_color: str | None = None
    badges: list[str] = field(default_factory=list)
    avatar_url: str | None = None
    is_subscriber: bool = False
    is_moderator: bool = False
    is_owner: bool = False
    is_verified: bool = False
    message_id: str | None = None
    emotes: list[Emote] = field(default_factory=list)
    donation_amount: str | None = None
    bits: int | None = None
    membership: str | None = None
    reply_to: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.platform, str):
            self.platform = Platform(self.platform.lower())
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=UTC)
        self.username = self.username.strip()
        self.display_name = self.display_name.strip() or self.username
        self.message = self.message.replace("\x00", "").strip()

