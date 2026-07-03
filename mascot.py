"""A centered cat pop-up overlay: dims/blurs a live capture of whatever is
currently behind it (so it never shows a mismatched solid-color box), shows
the "exhausted" cat while downloading, then crossfades to a "happy" pose
(with a sound cue and a warm glow) once the download finishes, and fades
back out. The cat gently bobs in place the whole time it's visible."""
from __future__ import annotations

import math
import time
import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageFilter, ImageGrab, ImageTk

from player import play_sound_effect


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _capture_looks_blank(image: Image.Image) -> bool:
    """True if a screen capture came back suspiciously close to solid black —
    which happens occasionally if the window was occluded or hadn't finished
    painting yet when ImageGrab fired."""
    small = image.convert("L").resize((24, 24))
    pixels = small.getdata()
    average = sum(pixels) / len(pixels)
    return average < 8


class MascotOverlay:
    """Manages a single floating label that renders the whole pop-up frame."""

    POP_STEPS = 14
    POP_INTERVAL_MS = 16
    CROSSFADE_STEPS = 18
    CROSSFADE_INTERVAL_MS = 22
    HOLD_MS = 2200
    DIM_STRENGTH = 0.55
    BLUR_RADIUS = 6

    BOB_INTERVAL_MS = 40
    BOB_AMPLITUDE_PX = 6
    BOB_PERIOD_S = 2.4
    GLOW_COLOR = (255, 210, 110)
    GLOW_BLUR_RADIUS = 18
    GLOW_PADDING = 42

    def __init__(
        self,
        master: tk.Widget,
        exhausted_path: str,
        happy_path: str,
        sound_path: str,
        volume_getter: Callable[[], int] = lambda: 100,
        fallback_bg: str = "#0A0C22",
    ) -> None:
        self._master = master
        self._sound_path = sound_path
        self._volume_getter = volume_getter
        self._fallback_bg = fallback_bg
        self._after_id: Optional[str] = None
        self._bob_after_id: Optional[str] = None
        self._bob_start = 0.0
        self._label: Optional[tk.Label] = None
        self._photo = None  # keep a reference so Tk doesn't garbage-collect it

        self._exhausted = Image.open(exhausted_path).convert("RGBA")
        self._happy = Image.open(happy_path).convert("RGBA")
        self._cat_size = self._exhausted.size

        self._backdrop_clean: Optional[Image.Image] = None
        self._backdrop_dim: Optional[Image.Image] = None

        # The "current frame" parameters, kept up to date by whichever
        # discrete animation (pop-in, crossfade, pop-out) is running, and
        # re-rendered continuously (with a fresh bob offset) by the idle loop.
        self._current_cat_image: Optional[Image.Image] = None
        self._current_dim_t = 0.0
        self._current_scale_t = 0.0
        self._current_glow = 0.0

    def _ensure_label(self) -> tk.Label:
        if self._label is None:
            self._label = tk.Label(self._master, bd=0, highlightthickness=0)
        return self._label

    def _capture_backdrop(self) -> None:
        # Bring the window to the front first -- a big source of the
        # occasional black capture was ImageGrab photographing whatever
        # occluded window happened to be on top of us at that instant.
        toplevel = self._master.winfo_toplevel()
        toplevel.lift()
        self._master.update_idletasks()

        x = self._master.winfo_rootx()
        y = self._master.winfo_rooty()
        w = max(1, self._master.winfo_width())
        h = max(1, self._master.winfo_height())

        shot = None
        for attempt in range(6):
            candidate = ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert("RGBA")
            if not _capture_looks_blank(candidate):
                shot = candidate
                break
            time.sleep(0.08)
            toplevel.lift()
            self._master.update_idletasks()

        if shot is None:
            # The screen grab kept coming back blank even after several
            # retries and re-raising the window -- fall back to a plain
            # themed backdrop instead of showing a broken black popup. This
            # should be exceedingly rare in practice.
            shot = Image.new("RGBA", (w, h), _hex_to_rgb(self._fallback_bg) + (255,))

        self._backdrop_clean = shot
        dark = Image.new("RGBA", shot.size, (5, 6, 20, 255))
        blurred = shot.filter(ImageFilter.GaussianBlur(self.BLUR_RADIUS))
        self._backdrop_dim = Image.blend(blurred, dark, self.DIM_STRENGTH)

    def _make_glow(self, scaled_cat: Image.Image, strength: float) -> Image.Image:
        pad = self.GLOW_PADDING
        size = (scaled_cat.width + pad * 2, scaled_cat.height + pad * 2)

        def layer(alpha_mult: float, blur_radius: float) -> Image.Image:
            silhouette = Image.new("RGBA", scaled_cat.size, self.GLOW_COLOR + (0,))
            alpha = scaled_cat.getchannel("A").point(lambda a: min(255, int(a * strength * alpha_mult)))
            silhouette.putalpha(alpha)
            layer_canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            layer_canvas.paste(silhouette, (pad, pad), silhouette)
            return layer_canvas.filter(ImageFilter.GaussianBlur(blur_radius))

        # A wide soft outer halo plus a brighter, tighter inner glow reads as
        # a much punchier effect than a single blur pass.
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas = Image.alpha_composite(canvas, layer(1.7, self.GLOW_BLUR_RADIUS))
        canvas = Image.alpha_composite(canvas, layer(2.3, self.GLOW_BLUR_RADIUS * 0.4))
        return canvas

    def _compose(self, cat_image: Image.Image, dim_t: float, scale_t: float, glow_strength: float, bob_y: float) -> Image.Image:
        frame = Image.blend(self._backdrop_clean, self._backdrop_dim, dim_t)

        cw, ch = self._cat_size
        scale = 0.85 + 0.15 * scale_t
        scaled = cat_image.resize((max(1, int(cw * scale)), max(1, int(ch * scale))), Image.LANCZOS)
        if scale_t < 1.0:
            alpha = scaled.getchannel("A").point(lambda a: int(a * scale_t))
            scaled.putalpha(alpha)

        fw, fh = frame.size
        pos_x = (fw - scaled.width) // 2
        pos_y = (fh - scaled.height) // 2 + int(bob_y)

        if glow_strength > 0.01:
            glow = self._make_glow(scaled, glow_strength)
            glow_pos = (pos_x - self.GLOW_PADDING, pos_y - self.GLOW_PADDING)
            frame.paste(glow, glow_pos, glow)

        frame.paste(scaled, (pos_x, pos_y), scaled)
        return frame.convert("RGB")

    def _set_frame(self, pil_image: Image.Image) -> None:
        self._photo = ImageTk.PhotoImage(pil_image)
        label = self._ensure_label()
        label.configure(image=self._photo)
        if not label.winfo_ismapped():
            label.place(relx=0, rely=0, relwidth=1, relheight=1)
        label.lift()

    def _update_current(self, cat_image: Image.Image, dim_t: float, scale_t: float, glow: float) -> None:
        self._current_cat_image = cat_image
        self._current_dim_t = dim_t
        self._current_scale_t = scale_t
        self._current_glow = glow

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            self._master.after_cancel(self._after_id)
            self._after_id = None

    # -------------------------------------------------------------- Bob

    def _start_bob_loop(self) -> None:
        if self._bob_after_id is None:
            self._bob_start = time.time()
            self._bob_tick()

    def _stop_bob_loop(self) -> None:
        if self._bob_after_id is not None:
            self._master.after_cancel(self._bob_after_id)
            self._bob_after_id = None

    def _bob_tick(self) -> None:
        if self._current_cat_image is not None:
            elapsed = time.time() - self._bob_start
            bob_y = math.sin(elapsed / self.BOB_PERIOD_S * 2 * math.pi) * self.BOB_AMPLITUDE_PX
            self._set_frame(
                self._compose(
                    self._current_cat_image, self._current_dim_t, self._current_scale_t, self._current_glow, bob_y
                )
            )
        self._bob_after_id = self._master.after(self.BOB_INTERVAL_MS, self._bob_tick)

    def _current_bob(self) -> float:
        if self._bob_after_id is None:
            return 0.0
        elapsed = time.time() - self._bob_start
        return math.sin(elapsed / self.BOB_PERIOD_S * 2 * math.pi) * self.BOB_AMPLITUDE_PX

    # ------------------------------------------------------------ Public

    def show_exhausted(self) -> None:
        self._cancel_pending()
        self._capture_backdrop()
        self._start_bob_loop()
        self._animate_pop(0, self._exhausted, growing=True, on_done=None)

    def celebrate_and_hide(self) -> None:
        self._cancel_pending()
        play_sound_effect(self._sound_path, self._volume_getter())
        self._crossfade(self._exhausted, self._happy, 0, self._schedule_hide)

    def hide_immediately(self) -> None:
        self._cancel_pending()
        self._stop_bob_loop()
        self._current_cat_image = None
        if self._label is not None:
            self._label.place_forget()

    # ----------------------------------------------------------- Private

    def _animate_pop(
        self, step: int, cat_image: Image.Image, growing: bool, on_done: Optional[Callable[[], None]]
    ) -> None:
        raw_t = step / self.POP_STEPS
        t = _ease_out_cubic(raw_t) if growing else 1 - _ease_out_cubic(raw_t)
        glow = 0.0 if growing else self._current_glow * t
        self._update_current(cat_image, t, t, glow)
        self._set_frame(self._compose(cat_image, t, t, glow, self._current_bob()))
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
        self._current_glow = 1.0
        self._animate_pop(0, self._happy, growing=False, on_done=self.hide_immediately)

    def _crossfade(self, start: Image.Image, end: Image.Image, step: int, on_done: Callable[[], None]) -> None:
        t = step / self.CROSSFADE_STEPS
        blended = Image.blend(start, end, t)
        self._update_current(blended, 1.0, 1.0, t)
        self._set_frame(self._compose(blended, 1.0, 1.0, t, self._current_bob()))
        if step >= self.CROSSFADE_STEPS:
            on_done()
            return
        self._after_id = self._master.after(
            self.CROSSFADE_INTERVAL_MS, lambda: self._crossfade(start, end, step + 1, on_done)
        )
