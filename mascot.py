"""A centered, floating cat overlay: shows while downloading, then crossfades
to a happy pose (with a sound cue) once the download finishes."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageTk

from player import play_sound_effect


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


class MascotOverlay:
    """Manages a single floating label that shows the exhausted/happy cat art."""

    FADE_STEPS = 18
    FADE_INTERVAL_MS = 22
    HOLD_MS = 2500

    def __init__(
        self,
        master: tk.Widget,
        exhausted_path: str,
        happy_path: str,
        sound_path: str,
        bg_color: str,
    ) -> None:
        self._master = master
        self._sound_path = sound_path
        self._bg_color = bg_color
        self._after_id: Optional[str] = None
        self._label: Optional[tk.Label] = None
        self._photo = None  # keep a reference so Tk doesn't garbage-collect it

        self._exhausted = self._load(exhausted_path)
        self._happy = self._load(happy_path)
        self._blank = Image.new("RGB", self._exhausted.size, _hex_to_rgb(bg_color))

    def _load(self, path: str) -> Image.Image:
        img = Image.open(path).convert("RGBA")
        flat = Image.new("RGBA", img.size, _hex_to_rgb(self._bg_color) + (255,))
        flat.paste(img, (0, 0), img)
        return flat.convert("RGB")

    def _ensure_label(self) -> tk.Label:
        if self._label is None:
            self._label = tk.Label(self._master, bg=self._bg_color, bd=0, highlightthickness=0)
        return self._label

    def _set_image(self, pil_image: Image.Image) -> None:
        self._photo = ImageTk.PhotoImage(pil_image)
        label = self._ensure_label()
        label.configure(image=self._photo)
        if not label.winfo_ismapped():
            label.place(relx=0.5, rely=0.5, anchor="center")
        label.lift()

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            self._master.after_cancel(self._after_id)
            self._after_id = None

    # ------------------------------------------------------------ Public

    def show_exhausted(self) -> None:
        self._cancel_pending()
        self._set_image(self._exhausted)

    def celebrate_and_hide(self) -> None:
        self._cancel_pending()
        play_sound_effect(self._sound_path)
        self._crossfade(self._exhausted, self._happy, 0, self._schedule_hide)

    def hide_immediately(self) -> None:
        self._cancel_pending()
        if self._label is not None:
            self._label.place_forget()

    # ----------------------------------------------------------- Private

    def _schedule_hide(self) -> None:
        self._after_id = self._master.after(self.HOLD_MS, self._fade_out)

    def _fade_out(self) -> None:
        self._after_id = None
        self._crossfade(self._happy, self._blank, 0, self.hide_immediately)

    def _crossfade(self, start: Image.Image, end: Image.Image, step: int, on_done: Callable[[], None]) -> None:
        frame = Image.blend(start, end, step / self.FADE_STEPS)
        self._set_image(frame)
        if step >= self.FADE_STEPS:
            on_done()
            return
        self._after_id = self._master.after(
            self.FADE_INTERVAL_MS, lambda: self._crossfade(start, end, step + 1, on_done)
        )
