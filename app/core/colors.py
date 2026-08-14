from __future__ import annotations

import hashlib


YOUTUBE_USERNAME_COLOR = "#F4E6B2"

_TWITCH_FALLBACK_COLORS = (
    "#FF6B6B",
    "#60A5FA",
    "#34D399",
    "#FBBF24",
    "#F472B6",
    "#A78BFA",
    "#22D3EE",
    "#FB923C",
    "#C084FC",
    "#4ADE80",
)


def twitch_username_color(username: str) -> str:
    """Return a stable readable fallback when Twitch sends no chat color."""
    normalized = username.strip().casefold().encode("utf-8")
    digest = hashlib.blake2b(normalized, digest_size=2).digest()
    index = int.from_bytes(digest, "big") % len(_TWITCH_FALLBACK_COLORS)
    return _TWITCH_FALLBACK_COLORS[index]
