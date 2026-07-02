"""Embedded media playback for the downloads library, backed by libVLC."""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import Frame
from typing import Optional

import customtkinter as ctk

try:
    import vlc

    VLC_AVAILABLE = True
except Exception:  # noqa: BLE001 - libvlc may simply not be installed
    vlc = None  # type: ignore[assignment]
    VLC_AVAILABLE = False

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".opus", ".wav", ".flac", ".ogg", ".aac"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def _format_time(ms: int) -> str:
    total_seconds = max(0, ms) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class PlayerWidget(ctk.CTkFrame):
    """A minimal embedded video/audio player with play/pause, seek and volume."""

    def __init__(self, master, accent: str, card_color: str, border_color: str, text_color: str, muted_color: str) -> None:
        super().__init__(master, fg_color="transparent")

        self._accent = accent
        self._muted_color = muted_color
        self._seeking = False
        self._current_path: Optional[str] = None

        self._instance = vlc.Instance("--quiet") if VLC_AVAILABLE else None
        self._player = self._instance.media_player_new() if self._instance else None

        self.grid_columnconfigure(0, weight=1)

        self.video_surface = Frame(self, bg="black")
        self.video_surface.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)

        self.placeholder_label = ctk.CTkLabel(
            self.video_surface,
            text="Wähle links eine Datei aus, um sie abzuspielen.",
            text_color="#6B7094",
            bg_color="black",
        )
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")

        controls = ctk.CTkFrame(self, fg_color=card_color, corner_radius=14, border_width=1, border_color=border_color)
        controls.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        controls.grid_columnconfigure(1, weight=1)

        self.play_button = ctk.CTkButton(
            controls,
            text="▶",
            width=40,
            height=32,
            corner_radius=16,
            fg_color=accent,
            hover_color=accent,
            text_color="#0A0C22",
            command=self.toggle_play_pause,
            state="disabled",
        )
        self.play_button.grid(row=0, column=0, padx=(12, 10), pady=12)

        self.seek_slider = ctk.CTkSlider(
            controls,
            from_=0,
            to=1000,
            number_of_steps=1000,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent,
            command=self._on_seek_drag,
        )
        self.seek_slider.set(0)
        self.seek_slider.bind("<ButtonPress-1>", self._on_seek_start)
        self.seek_slider.bind("<ButtonRelease-1>", self._on_seek_end)
        self.seek_slider.grid(row=0, column=1, sticky="ew", pady=12)
        self.seek_slider.configure(state="disabled")

        self.time_label = ctk.CTkLabel(controls, text="0:00 / 0:00", text_color=muted_color, width=90)
        self.time_label.grid(row=0, column=2, padx=(10, 12), pady=12)

        self.volume_slider = ctk.CTkSlider(
            controls,
            from_=0,
            to=100,
            width=90,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent,
            command=self._on_volume_change,
        )
        self.volume_slider.set(80)
        self.volume_slider.grid(row=0, column=3, padx=(0, 14), pady=12)

        if self._player:
            self._player.audio_set_volume(80)
            self.after(200, self._embed_video_surface)
            self.after(300, self._update_loop)

    # ------------------------------------------------------------ Public

    @property
    def available(self) -> bool:
        return VLC_AVAILABLE and self._player is not None

    def load_and_play(self, path: str) -> None:
        if not self.available:
            return
        self._current_path = path
        media = self._instance.media_new(path)
        self._player.set_media(media)
        self.placeholder_label.place_forget()
        self._player.play()
        self.play_button.configure(state="normal", text="⏸")
        self.seek_slider.configure(state="normal")

    def toggle_play_pause(self) -> None:
        if not self.available or not self._current_path:
            return
        if self._player.is_playing():
            self._player.pause()
            self.play_button.configure(text="▶")
        else:
            self._player.play()
            self.play_button.configure(text="⏸")

    def stop(self) -> None:
        if self.available:
            self._player.stop()

    # ----------------------------------------------------------- Private

    def _embed_video_surface(self) -> None:
        self.video_surface.update_idletasks()
        handle = self.video_surface.winfo_id()
        if sys.platform.startswith("win"):
            self._player.set_hwnd(handle)
        elif sys.platform == "darwin":
            self._player.set_nsobject(handle)
        else:
            self._player.set_xwindow(handle)

    def _on_seek_start(self, _event) -> None:
        self._seeking = True

    def _on_seek_end(self, _event) -> None:
        self._seeking = False
        if self.available and self._current_path:
            length = self._player.get_length()
            if length > 0:
                target_ms = int(self.seek_slider.get() / 1000 * length)
                self._player.set_time(target_ms)

    def _on_seek_drag(self, _value) -> None:
        pass  # actual seek happens on release; this just moves the handle

    def _on_volume_change(self, value: float) -> None:
        if self.available:
            self._player.audio_set_volume(int(value))

    def _update_loop(self) -> None:
        if self.available and self._current_path and not self._seeking:
            length = self._player.get_length()
            position = self._player.get_time()
            if length > 0:
                self.seek_slider.set(max(0, min(1000, position / length * 1000)))
                self.time_label.configure(text=f"{_format_time(position)} / {_format_time(length)}")
            if not self._player.is_playing() and self._player.get_state() == vlc.State.Ended:
                self.play_button.configure(text="▶")
        self.after(300, self._update_loop)
