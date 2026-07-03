"""A centered cat pop-up overlay: dims/blurs a live capture of whatever is
currently behind it (so it never shows a mismatched solid-color box), shows
the "exhausted" cat while downloading, then crossfades to a "happy" pose
(with a sound cue) once the download finishes, and fades back out."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageFilter, ImageGrab, ImageTk

from player import play_sound_effect


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


class MascotOverlay:
    """Manages a single floating label that renders the whole pop-up frame."""

    POP_STEPS = 14
    POP_INTERVAL_MS = 16
    CROSSFADE_STEPS = 18
    CROSSFADE_INTERVAL_MS = 22
    HOLD_MS = 2200
    DIM_STRENGTH = 0.55
    BLUR_RADIUS = 6

    def __init__(
        self,
        master: tk.Widget,
        exhausted_path: str,
        happy_path: str,
        sound_path: str,
        volume_getter: Callable[[], int] = lambda: 100,
    ) -> None:
        self._master = master
        self._sound_path = sound_path
        self._volume_getter = volume_getter
        self._after_id: Optional[str] = None
        self._label: Optional[tk.Label] = None
        self._photo = None  # keep a reference so Tk doesn't garbage-collect it

        self._exhausted = Image.open(exhausted_path).convert("RGBA")
        self._happy = Image.open(happy_path).convert("RGBA")
        self._cat_size = self._exhausted.size

        self._backdrop_clean: Optional[Image.Image] = None
        self._backdrop_dim: Optional[Image.Image] = None

    def _ensure_label(self) -> tk.Label:
        if self._label is None:
            self._label = tk.Label(self._master, bd=0, highlightthickness=0)
        return self._label

    def _capture_backdrop(self) -> None:
        self._master.update_idletasks()
        x = self._master.winfo_rootx()
        y = self._master.winfo_rooty()
        w = max(1, self._master.winfo_width())
        h = max(1, self._master.winfo_height())
        shot = ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert("RGBA")
        self._backdrop_clean = shot
        dark = Image.new("RGBA", shot.size, (5, 6, 20, 255))
        blurred = shot.filter(ImageFilter.GaussianBlur(self.BLUR_RADIUS))
        self._backdrop_dim = Image.blend(blurred, dark, self.DIM_STRENGTH)

    def _compose(self, cat_image: Image.Image, dim_t: float, scale_t: float) -> Image.Image:
        frame = Image.blend(self._backdrop_clean, self._backdrop_dim, dim_t)

        cw, ch = self._cat_size
        scale = 0.85 + 0.15 * scale_t
        scaled = cat_image.resize((max(1, int(cw * scale)), max(1, int(ch * scale))), Image.LANCZOS)
        if scale_t < 1.0:
            alpha = scaled.getchannel("A").point(lambda a: int(a * scale_t))
            scaled.putalpha(alpha)

        fw, fh = frame.size
        pos = ((fw - scaled.width) // 2, (fh - scaled.height) // 2)
        frame.paste(scaled, pos, scaled)
        return frame.convert("RGB")

    def _set_frame(self, pil_image: Image.Image) -> None:
        self._photo = ImageTk.PhotoImage(pil_image)
        label = self._ensure_label()
        label.configure(image=self._photo)
        if not label.winfo_ismapped():
            label.place(relx=0, rely=0, relwidth=1, relheight=1)
        label.lift()

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            self._master.after_cancel(self._after_id)
            self._after_id = None

    # ------------------------------------------------------------ Public

    def show_exhausted(self) -> None:
        self._cancel_pending()
        self._capture_backdrop()
        self._animate_pop(0, self._exhausted, growing=True, on_done=None)

    def celebrate_and_hide(self) -> None:
        self._cancel_pending()
        play_sound_effect(self._sound_path, self._volume_getter())
        self._crossfade(self._exhausted, self._happy, 0, self._schedule_hide)

    def hide_immediately(self) -> None:
        self._cancel_pending()
        if self._label is not None:
            self._label.place_forget()

    # ----------------------------------------------------------- Private

    def _animate_pop(
        self, step: int, cat_image: Image.Image, growing: bool, on_done: Optional[Callable[[], None]]
    ) -> None:
        raw_t = step / self.POP_STEPS
        t = _ease_out_cubic(raw_t) if growing else 1 - _ease_out_cubic(raw_t)
        self._set_frame(self._compose(cat_image, t, t))
        if step >= self.POP_STEPS:
            if on_done:
                on_done()
            return
        self._after_id = self._master.after(
            self.POP_INTERVAL_MS, lambda: self._animate_pop(step + 1, cat_image, growing, on_done)
        )

    def _schedule_hide(self) -> None:
        self._after_id = self._master.after(self.HOLD_MS, self._start_pop_out)

    def _start_pop_out(self) -> None:
        self._animate_pop(0, self._happy, growing=False, on_done=self.hide_immediately)

    def _crossfade(self, start: Image.Image, end: Image.Image, step: int, on_done: Callable[[], None]) -> None:
        blended = Image.blend(start, end, step / self.CROSSFADE_STEPS)
        self._set_frame(self._compose(blended, 1.0, 1.0))
        if step >= self.CROSSFADE_STEPS:
            on_done()
            return
        self._after_id = self._master.after(
            self.CROSSFADE_INTERVAL_MS, lambda: self._crossfade(start, end, step + 1, on_done)
        )
