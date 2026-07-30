from __future__ import annotations
import asyncio
import os
import shutil
import tempfile
import subprocess
from dataclasses import dataclass
from typing import Literal
from yt_dlp import YoutubeDL

from app.config import settings

Kind = Literal["video", "audio"]


@dataclass
class DownloadResult:
    filepath: str
    title: str
    duration: int | None
    thumbnail: str | None
    artist: str | None
    kind: Kind
    workdir: str
    width: int | None = None
    height: int | None = None

    def cleanup(self) -> None:
        try:
            shutil.rmtree(self.workdir, ignore_errors=True)
        except Exception:
            pass


def _base_opts(workdir: str) -> dict:
    opts = {
        "outtmpl": os.path.join(workdir, "%(id).40s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "max_filesize": settings.DOWNLOAD_MAX_FILESIZE_MB * 1024 * 1024,
        "retries": 3,
        "concurrent_fragment_downloads": 4,
        # Use the web player client — less likely to be blocked by YouTube
        # on datacenter IPs compared to the default Android/iOS clients.
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"],
            }
        },
    }

    # Optional cookies file — set YTDLP_COOKIES_FILE=/app/cookies.txt in .env
    # to bypass "Sign in to confirm you're not a bot" errors on YouTube.
    # Export cookies from a logged-in browser using the cookies.txt extension.
    cookies_path = os.environ.get("YTDLP_COOKIES_FILE", "")
    if cookies_path and os.path.isfile(cookies_path):
        opts["cookiefile"] = cookies_path

    return opts


# Codecs that all Telegram clients (iOS / Android / Desktop / Web) play
# natively inside an MP4 container, without needing server-side transcoding.
_TG_COMPATIBLE_VIDEO_CODECS = {"h264", "avc1"}
_TG_COMPATIBLE_AUDIO_CODECS = {"aac", "mp3"}


def _build_opts(kind: Kind, quality: str | None) -> dict:
    if kind == "audio":
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",  # best quality VBR
                },
                {"key": "FFmpegMetadata"},
            ],
        }

    if quality and quality.isdigit():
        h = int(quality)
        fmt = f"bv*[height<={h}]+ba/b[height<={h}]/b"
    else:
        fmt = "bv*+ba/b"

    return {
        "format": fmt,
        "merge_output_format": "mp4",
        "postprocessors": [
            {"key": "FFmpegMetadata"},
        ],
    }


def _probe_streams(filepath: str) -> tuple[str | None, str | None]:
    """Return (video_codec, audio_codec) for a media file using ffprobe."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type,codec_name",
                "-of", "csv=p=0",
                filepath,
            ],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except Exception:
        return None, None

    video_codec = audio_codec = None
    for line in out.splitlines():
        parts = line.strip().split(",")
        if len(parts) != 2:
            continue
        codec_name, codec_type = parts[0].strip().lower(), parts[1].strip().lower()
        if codec_type == "video" and video_codec is None:
            video_codec = codec_name
        elif codec_type == "audio" and audio_codec is None:
            audio_codec = codec_name
    return video_codec, audio_codec


def _probe_dimensions(filepath: str) -> tuple[int | None, int | None]:
    """
    Return the *display* (width, height) of the video's first stream,
    accounting for any rotation metadata (common with mobile-recorded
    Instagram/TikTok videos and some YouTube Shorts).

    Telegram clients use the dimensions passed to send_video to size the
    player; if they're omitted (or wrong/swapped due to rotation), the
    player can render with an incorrect — often square — aspect ratio.
    """
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height:stream_side_data=rotation",
                "-of", "json",
                filepath,
            ],
            check=True, capture_output=True, text=True,
        ).stdout
    except Exception:
        return None, None

    try:
        import json
        data = json.loads(out)
        stream = data.get("streams", [{}])[0]
        width = stream.get("width")
        height = stream.get("height")
        rotation = 0
        for sd in stream.get("side_data_list", []) or []:
            if "rotation" in sd:
                rotation = int(sd["rotation"])
                break
        if width is None or height is None:
            return None, None
        # A +/-90 or +/-270 rotation means the displayed orientation is
        # swapped relative to the raw encoded dimensions.
        if abs(rotation) in (90, 270):
            width, height = height, width
        return int(width), int(height)
    except Exception:
        return None, None


def _ensure_telegram_compatible(filepath: str, workdir: str) -> str:
    """
    Make sure the video plays correctly across Telegram clients
    (iOS, Android, Desktop, Web) while minimizing quality loss.

    - Already MP4 + H.264 + AAC/MP3 -> returned untouched (no re-encode).
    - Compatible codecs but wrong container -> remux to MP4 (no re-encode).
    - Otherwise -> transcode only the incompatible stream(s).
    """
    video_codec, audio_codec = _probe_streams(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    video_ok = video_codec in _TG_COMPATIBLE_VIDEO_CODECS
    audio_ok = audio_codec is None or audio_codec in _TG_COMPATIBLE_AUDIO_CODECS

    if ext == ".mp4" and video_ok and audio_ok:
        return filepath

    out_path = os.path.join(workdir, "telegram.mp4")

    if video_ok and audio_ok:
        cmd = ["ffmpeg", "-y", "-i", filepath, "-c", "copy", "-movflags", "+faststart", out_path]
    else:
        cmd = ["ffmpeg", "-y", "-i", filepath]
        if video_ok:
            cmd += ["-c:v", "copy"]
        else:
            # Re-encoding the video stream anyway: bake any rotation
            # metadata into the actual pixels so every client (including
            # ones that ignore rotation tags) displays the correct
            # orientation/aspect ratio instead of a square/cropped frame.
            cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast"]
        cmd += ["-c:a", "copy"] if audio_ok else ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-movflags", "+faststart", out_path]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return filepath

    return out_path


def _sync_download(url: str, kind: Kind, quality: str | None) -> DownloadResult:
    workdir = tempfile.mkdtemp(prefix="mediahub_")
    opts = {**_base_opts(workdir), **_build_opts(kind, quality)}

    with YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            active_ydl = ydl
        except Exception:
            # Intelligent fallback: requested format/quality unavailable ->
            # retry with the most permissive selector.
            fallback_opts = {**opts, "format": "ba/b" if kind == "audio" else "bv*+ba/b/b"}
            with YoutubeDL(fallback_opts) as ydl2:
                info = ydl2.extract_info(url, download=True)
            active_ydl = ydl2

        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        filepath = active_ydl.prepare_filename(info)

        if kind == "audio":
            base, _ = os.path.splitext(filepath)
            filepath = base + ".mp3"

        if not os.path.exists(filepath):
            files = [os.path.join(workdir, f) for f in os.listdir(workdir)]
            files = [f for f in files if os.path.isfile(f)]

            if not files:
                raise FileNotFoundError("Downloaded file not found")

            filepath = max(files, key=os.path.getsize)

        # Ensure cross-client Telegram compatibility while minimizing
        # quality loss (remux when possible, transcode only if required).
        width = height = None
        if kind == "video":
            filepath = _ensure_telegram_compatible(filepath, workdir)
            width, height = _probe_dimensions(filepath)
            if width is None or height is None:
                # Fall back to whatever yt-dlp reported for the source.
                width = info.get("width")
                height = info.get("height")

        return DownloadResult(
            filepath=filepath,
            title=info.get("title") or "media",
            duration=int(info.get("duration") or 0),
            thumbnail=info.get("thumbnail"),
            artist=info.get("uploader") or info.get("artist"),
            kind=kind,
            workdir=workdir,
            width=width,
            height=height,
        )


async def download(url: str, kind: Kind = "video", quality: str | None = None) -> DownloadResult:
    return await asyncio.to_thread(_sync_download, url, kind, quality)


def _sync_search(query: str, limit: int = 8) -> list[dict]:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "default_search": f"ytsearch{limit}"}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query, download=False)
    items = info.get("entries", []) if isinstance(info, dict) else []
    results = []
    for it in items:
        if not it:
            continue
        results.append({
            "id": it.get("id"),
            "title": it.get("title"),
            "url": it.get("webpage_url") or it.get("url"),
            "duration": it.get("duration"),
            "uploader": it.get("uploader"),
        })
    return results


async def search_music(query: str, limit: int = 8) -> list[dict]:
    return await asyncio.to_thread(_sync_search, query, limit)
