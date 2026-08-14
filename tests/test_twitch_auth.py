import pytest

from app.core.config import AppConfig
from app.core.event_bus import EventBus
from app.twitch.client import TwitchClient


class FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self, content_type=None):
        return {"login": "TestUser", "scopes": ["chat:read"]}


class FakeSession:
    def __init__(self, captured: dict) -> None:
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def get(self, url: str, headers: dict[str, str]):
        self.captured.update(url=url, headers=headers)
        return FakeResponse()


@pytest.mark.asyncio
async def test_twitch_username_is_resolved_from_token(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "app.twitch.client.aiohttp.ClientSession",
        lambda timeout: FakeSession(captured),
    )
    client = TwitchClient(
        AppConfig(twitch_channel="channel", twitch_oauth_token="oauth:secret"),
        EventBus(),
        lambda status, detail: None,
    )

    username, token = await client._validate_token()

    assert username == "testuser"
    assert token == "secret"
    assert captured["headers"] == {"Authorization": "OAuth secret"}
