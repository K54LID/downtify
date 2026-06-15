from __future__ import annotations
import re

TIKTOK_RE = re.compile(r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/\S+", re.I)
INSTAGRAM_RE = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv|reels)/\S+", re.I)
YOUTUBE_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)\S+",
    re.I,
)


def detect_platform(text: str) -> str | None:
    if TIKTOK_RE.search(text):
        return "tiktok"
    if INSTAGRAM_RE.search(text):
        return "instagram"
    if YOUTUBE_RE.search(text):
        return "youtube"
    return None


def extract_url(text: str) -> str | None:
    for rx in (TIKTOK_RE, INSTAGRAM_RE, YOUTUBE_RE):
        m = rx.search(text)
        if m:
            return m.group(0)
    return None


def looks_like_music_search(text: str) -> bool:
    t = text.strip()
    if not t or len(t) < 3 or len(t) > 120:
        return False
    if t.startswith("/"):
        return False
    if detect_platform(t):
        return False
    # plain words / "Artist - Title" style
    return bool(re.match(r"^[\w\s\-\u00C0-\uFFFF'’.,!&()]+$", t, re.UNICODE))
