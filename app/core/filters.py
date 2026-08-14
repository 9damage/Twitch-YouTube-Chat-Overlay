from __future__ import annotations

from dataclasses import dataclass, field

from app.core.models import ChatMessage


@dataclass(slots=True)
class MessageFilter:
    hide_commands: bool = False
    ignored_usernames: set[str] = field(default_factory=set)
    ignored_words: set[str] = field(default_factory=set)

    def should_display(self, message: ChatMessage) -> bool:
        text = message.message.casefold()
        if self.hide_commands and message.message.lstrip().startswith("!"):
            return False
        if message.username.casefold() in {x.casefold() for x in self.ignored_usernames}:
            return False
        return not any(word.casefold() in text for word in self.ignored_words if word)

