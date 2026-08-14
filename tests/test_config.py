import json

from app.core.config import AppConfig, ConfigManager, _bool


def test_boolean_parser() -> None:
    assert _bool("YES")
    assert not _bool("off", True)


def test_default_message_lifetime_is_30_seconds() -> None:
    assert AppConfig().message_lifetime == 30


def test_twitch_requires_only_channel_and_token() -> None:
    assert AppConfig(twitch_channel="channel", twitch_oauth_token="oauth:secret").twitch_configured
    assert not AppConfig(twitch_channel="channel").twitch_configured


def test_youtube_requires_channel_and_api_key() -> None:
    assert AppConfig(youtube_api_key="key", youtube_channel="@channel").youtube_configured
    assert not AppConfig(youtube_api_key="key").youtube_configured


def test_old_youtube_video_setting_is_migrated(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YOUTUBE_CHANNEL", raising=False)
    monkeypatch.delenv("YOUTUBE_VIDEO_ID", raising=False)
    path = tmp_path / "config.json"
    path.write_text('{"youtube_video_id": "https://youtu.be/dQw4w9WgXcQ"}', encoding="utf-8")

    loaded = ConfigManager(path).load()

    assert loaded.youtube_channel == "https://youtu.be/dQw4w9WgXcQ"


def test_config_roundtrip_excludes_secrets(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    path = tmp_path / "config.json"
    manager = ConfigManager(path)
    config = AppConfig(twitch_channel="channel", twitch_oauth_token="oauth:secret", youtube_api_key="secret")
    manager.save(config)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "twitch_oauth_token" not in raw
    assert "youtube_api_key" not in raw
    loaded = ConfigManager(path).load()
    assert loaded.twitch_channel == "channel"
    assert loaded.twitch_oauth_token == "oauth:secret"
    assert loaded.youtube_api_key == "secret"
    encrypted = path.with_name("credentials.dat").read_bytes()
    assert b"oauth:secret" not in encrypted
