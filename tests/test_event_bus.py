import pytest

from app.core.event_bus import EventBus
from app.core.models import ChatMessage, Platform


@pytest.mark.asyncio
async def test_full_bus_drops_oldest() -> None:
    bus = EventBus(2)
    for text in ("one", "two", "three"):
        bus.publish_nowait(ChatMessage(Platform.TWITCH, "u", "U", text))
    assert (await bus.next()).message == "two"
    assert (await bus.next()).message == "three"

