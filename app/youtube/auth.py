from __future__ import annotations

import re
from urllib.parse import unquote, urlparse


_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")


def normalize_video_id(value: str) -> str:
    value = value.strip()
    for marker in ("v=", "youtu.be/"):
        if marker in value:
            value = value.split(marker, 1)[1].split("&", 1)[0].split("?", 1)[0].split("/", 1)[0]
    return value if _VIDEO_ID.fullmatch(value) else ""


def parse_channel_reference(value: str) -> tuple[str, str]:
    """Return a YouTube channel reference as (id|handle|username|video, value)."""
    value = value.strip()
    if not value:
        return "", ""
    if value.lower().startswith(("youtube.com/", "www.youtube.com/", "m.youtube.com/", "youtu.be/")):
        value = f"https://{value}"
    if _CHANNEL_ID.fullmatch(value):
        return "id", value
    video_id = normalize_video_id(value)
    if video_id and ("youtu" in value.lower() or _VIDEO_ID.fullmatch(value)):
        return "video", video_id

    candidate = value
    if "://" in value:
        parsed = urlparse(value)
        host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
        if host not in {"youtube.com", "youtu.be"}:
            return "", ""
        parts = [unquote(part) for part in parsed.path.split("/") if part]
        if not parts:
            return "", ""
        if parts[0] == "channel" and len(parts) > 1 and _CHANNEL_ID.fullmatch(parts[1]):
            return "id", parts[1]
        if parts[0] == "user" and len(parts) > 1:
            return "username", parts[1]
        if parts[0].startswith("@"):
            return "handle", parts[0]
        if parts[0] == "c" and len(parts) > 1:
            return "handle", parts[1]
        return "", ""

    candidate = candidate.split("/", 1)[0].strip()
    return ("handle", candidate) if candidate else ("", "")
