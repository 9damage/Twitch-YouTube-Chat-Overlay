import pytest

from app.core.config import AppConfig
from app.core.event_bus import EventBus
from app.youtube.auth import parse_channel_reference
from app.youtube.client import YouTubeClient


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.youtube.com/@GoogleDevelopers", ("handle", "@GoogleDevelopers")),
        ("youtube.com/@GoogleDevelopers/live", ("handle", "@GoogleDevelopers")),
        ("@GoogleDevelopers", ("handle", "@GoogleDevelopers")),
        ("UC_x5XG1OV2P6uZZ5FSM9Ttw", ("id", "UC_x5XG1OV2P6uZZ5FSM9Ttw")),
        ("https://youtu.be/dQw4w9WgXcQ", ("video", "dQw4w9WgXcQ")),
    ],
)
def test_parse_channel_reference(value: str, expected: tuple[str, str]) -> None:
    assert parse_channel_reference(value) == expected


@pytest.mark.asyncio
async def test_find_newest_active_stream() -> None:
    client = YouTubeClient(
        AppConfig(youtube_api_key="key", youtube_channel="@channel"),
        EventBus(),
        lambda status, detail: None,
    )

    async def request(endpoint: str, params: dict[str, str]) -> dict:
        if endpoint == "playlistItems":
            return {
                "items": [
                    {"contentDetails": {"videoId": "older-video"}},
                    {"contentDetails": {"videoId": "newer-video"}},
                ]
            }
        return {
            "items": [
                {
                    "snippet": {"title": "Старый эфир"},
                    "liveStreamingDetails": {
                        "actualStartTime": "2026-08-13T10:00:00Z",
                        "activeLiveChatId": "old-chat",
                    },
                },
                {
                    "snippet": {"title": "Новый эфир"},
                    "liveStreamingDetails": {
                        "actualStartTime": "2026-08-14T10:00:00Z",
                        "activeLiveChatId": "new-chat",
                    },
                },
            ]
        }

    client._request = request
    assert await client._find_active_stream("uploads") == ("new-chat", "Новый эфир")
