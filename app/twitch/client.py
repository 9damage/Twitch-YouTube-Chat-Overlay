from __future__ import annotations

import asyncio
import logging
import ssl
from collections.abc import Callable

import aiohttp

from app.core.config import AppConfig
from app.core.event_bus import EventBus
from app.core.models import ConnectionStatus
from app.twitch.parser import parse_irc_message


StatusCallback = Callable[[ConnectionStatus, str], None]


class TwitchClient:
    HOST = "irc.chat.twitch.tv"
    PORT = 6697
    VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
    BACKOFF = (1, 2, 5, 10, 30)

    def __init__(self, config: AppConfig, bus: EventBus, on_status: StatusCallback) -> None:
        self.config = config
        self.bus = bus
        self.on_status = on_status
        self._stopping = False
        self._writer: asyncio.StreamWriter | None = None
        self._logger = logging.getLogger(__name__)

    async def run(self) -> None:
        attempt = 0
        while not self._stopping:
            if not self.config.twitch_configured:
                self.on_status(ConnectionStatus.DISCONNECTED, "Не настроено")
                return
            try:
                self.on_status(ConnectionStatus.CONNECTING, "Подключение")
                await self._connect_and_read()
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.warning("Twitch connection failed: %s", exc)
                self.on_status(ConnectionStatus.ERROR, str(exc))
            if not self._stopping:
                delay = self.BACKOFF[min(attempt, len(self.BACKOFF) - 1)]
                attempt += 1
                await asyncio.sleep(delay)

    async def _connect_and_read(self) -> None:
        username, token = await self._validate_token()
        validated_at = asyncio.get_running_loop().time()
        ssl_context = ssl.create_default_context()
        reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.HOST, self.PORT, ssl=ssl_context), timeout=15
        )
        await self._send(f"PASS oauth:{token}")
        await self._send(f"NICK {username}")
        await self._send("CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership")
        await self._send(f"JOIN #{self.config.twitch_channel.lstrip('#').lower()}")
        self.on_status(ConnectionStatus.CONNECTED, f"Подключено как {username}")
        while not self._stopping:
            raw = await asyncio.wait_for(reader.readline(), timeout=330)
            if not raw:
                raise ConnectionError("Twitch закрыл соединение")
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("PING"):
                await self._send("PONG" + line[4:])
            elif " RECONNECT" in line:
                raise ConnectionError("Twitch запросил переподключение")
            else:
                message = parse_irc_message(line)
                if message:
                    self.bus.publish_nowait(message)
            if asyncio.get_running_loop().time() - validated_at >= 3600:
                validated_username, _ = await self._validate_token()
                if validated_username != username:
                    raise RuntimeError("Владелец токена Twitch изменился")
                validated_at = asyncio.get_running_loop().time()

    async def _validate_token(self) -> tuple[str, str]:
        token = self.config.twitch_oauth_token.strip()
        if token.lower().startswith("oauth:"):
            token = token[6:]
        if not token:
            raise RuntimeError("Не указан OAuth-токен Twitch")
        timeout = aiohttp.ClientTimeout(total=15, connect=10)
        headers = {"Authorization": f"OAuth {token}"}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.VALIDATE_URL, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise RuntimeError("OAuth-токен Twitch недействителен")
        username = str(data.get("login", "")).strip().lower()
        scopes = set(data.get("scopes", []))
        if not username:
            raise RuntimeError("Не удалось определить пользователя Twitch по токену")
        if "chat:read" not in scopes:
            raise RuntimeError("Токен Twitch не имеет разрешения chat:read")
        return username, token

    async def _send(self, line: str) -> None:
        if not self._writer:
            return
        self._writer.write((line + "\r\n").encode("utf-8"))
        await asyncio.wait_for(self._writer.drain(), timeout=10)

    async def stop(self) -> None:
        self._stopping = True
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError as exc:
                self._logger.debug("Twitch socket close error: %s", exc)
        self.on_status(ConnectionStatus.DISCONNECTED, "Отключено")
