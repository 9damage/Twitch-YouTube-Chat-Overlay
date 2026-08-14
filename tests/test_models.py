from datetime import datetime

from app.core.models import ChatMessage, Platform


def test_chat_message_normalizes_values() -> None:
    message = ChatMessage("TWITCH", " user ", "", " hello\x00 ", datetime(2026, 1, 1))
    assert message.platform is Platform.TWITCH
    assert message.username == "user"
    assert message.display_name == "user"
    assert message.message == "hello"
    assert message.timestamp.tzinfo is not None

