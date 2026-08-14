from __future__ import annotations

from datetime import UTC, datetime

from app.core.colors import twitch_username_color
from app.core.models import ChatMessage, Emote, Platform


_ESCAPES = {"s": " ", ":": ";", "\\": "\\", "r": "\r", "n": "\n"}


def _unescape(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            index += 1
            result.append(_ESCAPES.get(value[index], value[index]))
        else:
            result.append(value[index])
        index += 1
    return "".join(result)


def parse_tags(raw: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in raw.split(";"):
        key, separator, value = item.partition("=")
        tags[key] = _unescape(value) if separator else ""
    return tags


def parse_emotes(raw: str) -> list[Emote]:
    result: list[Emote] = []
    if not raw:
        return result
    for group in raw.split("/"):
        emote_id, separator, positions = group.partition(":")
        if not separator:
            continue
        for position in positions.split(","):
            try:
                start, end = (int(value) for value in position.split("-", 1))
                result.append(Emote(emote_id, start, end))
            except (ValueError, TypeError):
                continue
    return result


def parse_irc_message(line: str) -> ChatMessage | None:
    if " PRIVMSG " not in line:
        return None
    tags: dict[str, str] = {}
    rest = line.rstrip("\r\n")
    if rest.startswith("@"):
        tag_text, _, rest = rest[1:].partition(" ")
        tags = parse_tags(tag_text)
    prefix, _, trailing = rest.partition(" PRIVMSG ")
    if not trailing:
        return None
    user = prefix.lstrip(":").split("!", 1)[0]
    _, separator, message = trailing.partition(" :")
    if not separator:
        return None
    badges = [badge for badge in tags.get("badges", "").split(",") if badge]
    badge_names = {badge.split("/", 1)[0] for badge in badges}
    timestamp = datetime.now(UTC)
    if tags.get("tmi-sent-ts"):
        try:
            timestamp = datetime.fromtimestamp(int(tags["tmi-sent-ts"]) / 1000, UTC)
        except ValueError:
            timestamp = datetime.now(UTC)
    bits = int(tags["bits"]) if tags.get("bits", "").isdigit() else None
    return ChatMessage(
        platform=Platform.TWITCH,
        username=user,
        display_name=tags.get("display-name") or user,
        message=message,
        timestamp=timestamp,
        user_color=tags.get("color") or twitch_username_color(user),
        badges=badges,
        is_subscriber=tags.get("subscriber") == "1" or "subscriber" in badge_names,
        is_moderator=tags.get("mod") == "1" or "moderator" in badge_names,
        is_owner="broadcaster" in badge_names,
        message_id=tags.get("id") or None,
        emotes=parse_emotes(tags.get("emotes", "")),
        bits=bits,
        reply_to=tags.get("reply-parent-msg-id") or None,
    )
