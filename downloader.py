"""Thin wrapper around yt-dlp so the GUI never has to touch its API directly."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Callable

import yt_dlp
from yt_dlp.utils import DownloadCancelled  # re-exported for the GUI's cancel hook

from paths import resource_path

FORMAT_PRESETS = {
    "Best Quality (Video+Audio)": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "Audio Only (MP3)": "bestaudio/best",
}

AUDIO_ONLY_LABEL = "Audio Only (MP3)"


@dataclass
class DownloadOptions:
    url: str
    output_dir: str
    format_label: str
    playlist: bool = False


class GuiLogger:
    """Routes yt-dlp's internal log lines into a callback the GUI can display."""

    def __init__(self, on_message: Callable[[str], None]):
        self._on_message = on_message

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            return
        self._on_message(msg)

    def info(self, msg: str) -> None:
        self._on_message(msg)

    def warning(self, msg: str) -> None:
        self._on_message(f"WARNING: {msg}")

    def error(self, msg: str) -> None:
        self._on_message(f"ERROR: {msg}")


def _bundled_ffmpeg_dir() -> str:
    return resource_path("assets/ffmpeg")


def ffmpeg_available() -> bool:
    bundled = os.path.join(_bundled_ffmpeg_dir(), "ffmpeg.exe")
    if os.path.exists(bundled):
        return True
    return shutil.which("ffmpeg") is not None


def build_ydl_opts(options: DownloadOptions, progress_hook: Callable, logger: GuiLogger) -> dict:
    opts: dict = {
        "format": FORMAT_PRESETS[options.format_label],
        # Include the video ID so two different videos that happen to share
        # the same title/caption (very common on TikTok) don't collide on
        # the same filename and silently overwrite or "skip" each other.
        "outtmpl": os.path.join(options.output_dir, "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": not options.playlist,
        "progress_hooks": [progress_hook],
        "logger": logger,
        "merge_output_format": "mp4",
        # Prefer H.264 video and AAC audio over HEVC/AV1/VP9 and Opus/Vorbis
        # so downloads play back everywhere (e.g. Windows' built-in player)
        # without needing extra OS codec packs.
        "format_sort": ["vcodec:h264", "acodec:aac"],
    }

    bundled_dir = _bundled_ffmpeg_dir()
    if os.path.exists(os.path.join(bundled_dir, "ffmpeg.exe")):
        opts["ffmpeg_location"] = bundled_dir

    if options.format_label == AUDIO_ONLY_LABEL:
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    return opts


def download(options: DownloadOptions, progress_hook: Callable, logger: GuiLogger) -> None:
    opts = build_ydl_opts(options, progress_hook, logger)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([options.url])
