from app.core.models import Platform
from app.core.colors import twitch_username_color
from app.twitch.parser import parse_irc_message, parse_tags


def test_parse_privmsg() -> None:
    line = "@badge-info=subscriber/12;badges=subscriber/12;color=#FF0000;display-name=User :user!user@user.tmi.twitch.tv PRIVMSG #channel :Hello world"
    result = parse_irc_message(line)
    assert result is not None
    assert result.display_name == "User"
    assert result.message == "Hello world"
    assert result.platform is Platform.TWITCH
    assert result.is_subscriber


def test_parse_tags_unescapes_twitch_values() -> None:
    assert parse_tags(r"display-name=Hello\sWorld;reply=one\:two")["display-name"] == "Hello World"
    assert parse_tags(r"display-name=Hello\sWorld;reply=one\:two")["reply"] == "one;two"


def test_non_privmsg_is_ignored() -> None:
    assert parse_irc_message("PING :tmi.twitch.tv") is None


def test_missing_twitch_color_gets_stable_fallback() -> None:
    line = "@display-name=Viewer;color= :viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #channel :Hello"
    result = parse_irc_message(line)
    assert result is not None
    assert result.user_color == twitch_username_color("viewer")
    assert twitch_username_color("viewer") == twitch_username_color("Viewer")
