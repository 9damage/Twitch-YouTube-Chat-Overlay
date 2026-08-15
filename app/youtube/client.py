from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import aiohttp

from app.core.config import AppConfig
from app.core.event_bus import EventBus
from app.core.colors import YOUTUBE_USERNAME_COLOR
from app.core.models import ChatMessage, ConnectionStatus, Platform
from app.youtube.auth import parse_channel_reference


StatusCallback = Callable[[ConnectionStatus, str], None]


class YouTubeClient:
    API = "https://www.googleapis.com/youtube/v3"
    CHANNEL_CHECK_INTERVAL = 60

    def __init__(self, config: AppConfig, bus: EventBus, on_status: StatusCallback) -> None:
        self.config = config
        self.bus = bus
        self.on_status = on_status
        self._stopping = False
        self._session: aiohttp.ClientSession | None = None
        self._logger = logging.getLogger(__name__)

    async def run(self) -> None:
        if not self.config.youtube_configured:
            self.on_status(ConnectionStatus.DISCONNECTED, "Не настроено")
            return
        timeout = aiohttp.ClientTimeout(total=20, connect=10)
        self._session = aiohttp.ClientSession(timeout=timeout)
        try:
            channel_name = ""
            uploads_playlist = ""
            backoff = 2
            while not self._stopping:
                try:
                    if not uploads_playlist:
                        self.on_status(ConnectionStatus.CONNECTING, "Определение YouTube-канала")
                        channel_name, uploads_playlist = await self._resolve_channel()
                    live = await self._find_active_stream(uploads_playlist)
                    backoff = 2
                    if live is None:
                        self.on_status(
                            ConnectionStatus.WAITING,
                            f"На канале {channel_name} нет активного эфира · повторная проверка через минуту",
                        )
                        await asyncio.sleep(self.CHANNEL_CHECK_INTERVAL)
                        continue
                    chat_id, title = live
                    await self._poll(chat_id, title)
                    if not self._stopping:
                        await asyncio.sleep(15)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._logger.warning("YouTube channel check failed: %s", exc)
                    self.on_status(ConnectionStatus.ERROR, str(exc))
                    await asyncio.sleep(min(backoff, 60))
                    backoff = min(backoff * 2, 60)
        except asyncio.CancelledError:
            raise
        finally:
            await self.stop()

    async def _request(self, endpoint: str, params: dict[str, str]) -> dict:
        assert self._session
        params["key"] = self.config.youtube_api_key
        async with self._session.get(f"{self.API}/{endpoint}", params=params) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                reason = data.get("error", {}).get("message", f"HTTP {response.status}")
                raise RuntimeError(reason)
            return data

    async def _resolve_channel(self) -> tuple[str, str]:
        kind, value = parse_channel_reference(self.config.youtube_channel)
        if not kind:
            raise RuntimeError("Неверная ссылка на YouTube-канал")
        if kind == "video":
            video = await self._request("videos", {"part": "snippet", "id": value})
            video_items = video.get("items", [])
            if not video_items:
                raise RuntimeError("Видео YouTube не найдено")
            value = video_items[0].get("snippet", {}).get("channelId", "")
            kind = "id"

        filters = {
            "id": {"id": value},
            "handle": {"forHandle": value},
            "username": {"forUsername": value},
        }
        data = await self._request(
            "channels",
            {"part": "snippet,contentDetails", **filters[kind]},
        )
        items = data.get("items", [])
        if not items:
            raise RuntimeError("YouTube-канал не найден")
        item = items[0]
        title = item.get("snippet", {}).get("title") or value
        uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            raise RuntimeError("Не удалось получить список видео YouTube-канала")
        return str(title), str(uploads)

    async def _find_active_stream(self, uploads_playlist: str) -> tuple[str, str] | None:
        playlist = await self._request(
            "playlistItems",
            {"part": "contentDetails", "playlistId": uploads_playlist, "maxResults": "50"},
        )
        video_ids = [
            item.get("contentDetails", {}).get("videoId", "")
            for item in playlist.get("items", [])
        ]
        video_ids = [video_id for video_id in video_ids if video_id]
        if not video_ids:
            return None
        videos = await self._request(
            "videos",
            {"part": "snippet,liveStreamingDetails", "id": ",".join(video_ids)},
        )
        candidates: list[tuple[str, str, str]] = []
        for item in videos.get("items", []):
            details = item.get("liveStreamingDetails", {})
            chat_id = details.get("activeLiveChatId")
            if not chat_id:
                continue
            timestamp = details.get("actualStartTime") or details.get("scheduledStartTime") or ""
            title = item.get("snippet", {}).get("title") or "Прямой эфир YouTube"
            candidates.append((str(timestamp), str(chat_id), str(title)))
        if not candidates:
            return None
        _, chat_id, title = max(candidates, key=lambda item: item[0])
        return chat_id, title

    async def _poll(self, chat_id: str, title: str) -> None:
        page_token = ""
        self.on_status(ConnectionStatus.CONNECTED, f"Подключено · {title}")
        backoff = 1
        while not self._stopping:
            try:
                params = {"part": "snippet,authorDetails", "liveChatId": chat_id, "maxResults": "200"}
                if page_token:
                    params["pageToken"] = page_token
                data = await self._request("liveChat/messages", params)
                for item in data.get("items", []):
                    message = self._parse_item(item)
                    if message:
                        self.bus.publish_nowait(message)
                page_token = data.get("nextPageToken", page_token)
                interval = max(1.0, int(data.get("pollingIntervalMillis", 5000)) / 1000)
                backoff = 1
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                text = str(exc)
                if "liveChatEnded" in text or "live chat is no longer live" in text.lower():
                    self.on_status(ConnectionStatus.LIVE_ENDED, "Трансляция завершена")
                    return
                self.on_status(ConnectionStatus.WAITING, text)
                await asyncio.sleep(min(backoff, 30))
                backoff *= 2

    @staticmethod
    def _parse_item(item: dict) -> ChatMessage | None:
        snippet = item.get("snippet", {})
        author = item.get("authorDetails", {})
        text = snippet.get("displayMessage", "")
        if not text:
            return None
        published = snippet.get("publishedAt", "")
        try:
            timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            timestamp = datetime.now(UTC)
        details = snippet.get("superChatDetails") or snippet.get("superStickerDetails") or {}
        return ChatMessage(
            platform=Platform.YOUTUBE,
            username=author.get("channelId", "unknown"),
            display_name=author.get("displayName", "Пользователь YouTube"),
            message=text,
            timestamp=timestamp,
            user_color=YOUTUBE_USERNAME_COLOR,
            avatar_url=author.get("profileImageUrl"),
            is_subscriber=author.get("isChatSponsor", False),
            is_moderator=author.get("isChatModerator", False),
            is_owner=author.get("isChatOwner", False),
            is_verified=author.get("isVerified", False),
            message_id=item.get("id"),
            donation_amount=details.get("amountDisplayString"),
            membership="подписчик" if author.get("isChatSponsor") else None,
        )

    async def stop(self) -> None:
        self._stopping = True
        if self._session and not self._session.closed:
            try:
                await asyncio.wait_for(self._session.close(), timeout=2.0)
            except TimeoutError:
                self._logger.debug("YouTube session close timed out")
            finally:
                self._session = None
        self.on_status(ConnectionStatus.DISCONNECTED, "Отключено")
