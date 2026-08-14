from app.core.filters import MessageFilter
from app.core.models import ChatMessage, Platform


def msg(text: str, user: str = "viewer") -> ChatMessage:
    return ChatMessage(Platform.TWITCH, user, user, text)


def test_filter_commands_users_and_words() -> None:
    filtering = MessageFilter(True, {"bot"}, {"spoiler"})
    assert not filtering.should_display(msg("!command"))
    assert not filtering.should_display(msg("hello", "BOT"))
    assert not filtering.should_display(msg("A big SPOILER"))
    assert filtering.should_display(msg("good stream"))

