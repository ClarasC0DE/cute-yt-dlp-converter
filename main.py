"""yt-dlp GUI Downloader

A small, modern desktop GUI around yt-dlp for downloading videos/audio.
"""
from __future__ import annotations

import os
import queue
import random
import sys
import threading
from pathlib import Path
from tkinter import Canvas, filedialog, messagebox

import customtkinter as ctk

from downloader import AUDIO_ONLY_LABEL, FORMAT_PRESETS, DownloadOptions, GuiLogger, download, ffmpeg_available
from mascot import MascotOverlay
from player import MEDIA_EXTENSIONS, VIDEO_EXTENSIONS, PlayerWidget

ctk.set_appearance_mode("dark")


def resource_path(relative_path: str) -> str:
    """Resolve a bundled asset both when run from source and from a PyInstaller exe."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# ---------------------------------------------------------------- Theme
# Deep-night / indie color palette: near-black navy base, a violet-blue
# accent, and a soft gradient + stars in the hero banner.

BG_DEEP = "#0A0C22"
BG_CARD = "#151935"
BG_CARD_BORDER = "#262B54"
ACCENT = "#7C6FFF"
ACCENT_HOVER = "#9184FF"
HERO_TOP = "#0A0C22"
HERO_BOTTOM = "#332764"
TEXT_PRIMARY = "#F5F6FA"
TEXT_SECONDARY = "#9DA3C4"

DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads" / "yt-dlp-gui")


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _lerp_color(color_a: str, color_b: str, t: float) -> str:
    ar, ag, ab = _hex_to_rgb(color_a)
    br, bg, bb = _hex_to_rgb(color_b)
    return "#{:02x}{:02x}{:02x}".format(
        int(ar + (br - ar) * t), int(ag + (bg - ag) * t), int(ab + (bb - ab) * t)
    )


class HeroBanner(Canvas):
    """A small gradient 'night sky' banner with a title, subtitle, stars and a
    library shortcut button."""

    def __init__(self, master, on_library_click, height: int = 150) -> None:
        super().__init__(master, height=height, highlightthickness=0, bg=HERO_TOP)
        self._height = height
        self._last_width = -1
        self._stars = [
            (random.uniform(0.04, 0.7), random.uniform(0.15, 0.85), random.uniform(1.0, 2.3))
            for _ in range(24)
        ]

        self._library_button = ctk.CTkButton(
            self,
            text="📁 Downloads  ›",
            height=32,
            corner_radius=16,
            fg_color="#1E2350",
            hover_color="#332764",
            text_color=TEXT_PRIMARY,
            font=("Segoe UI", 12),
            command=on_library_click,
        )
        self._button_window = self.create_window(0, 0, anchor="ne", window=self._library_button)

        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event) -> None:
        if event.width == self._last_width:
            return
        self._last_width = event.width
        self._redraw(event.width)

    def _redraw(self, width: int) -> None:
        self.delete("bg")
        steps = 48
        for i in range(steps):
            t = i / (steps - 1)
            color = _lerp_color(HERO_TOP, HERO_BOTTOM, t)
            y0 = int(self._height * i / steps)
            y1 = int(self._height * (i + 1) / steps) + 1
            self.create_rectangle(0, y0, width, y1, fill=color, outline="", tags="bg")

        for rel_x, rel_y, radius in self._stars:
            x, y = rel_x * width, rel_y * self._height
            self.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#CFE0FF", outline="", tags="bg")

        self.create_text(
            28,
            self._height * 0.40,
            text="yt-dlp Downloader",
            anchor="w",
            fill=TEXT_PRIMARY,
            font=("Segoe UI Semibold", 23),
            tags="bg",
        )
        self.create_text(
            28,
            self._height * 0.40 + 28,
            text="Video- oder Playlist-URL einfügen und herunterladen.",
            anchor="w",
            fill="#C7CBEE",
            font=("Segoe UI", 12),
            tags="bg",
        )

        self.coords(self._button_window, width - 20, 22)
        self.tag_lower("bg")


class Card(ctk.CTkFrame):
    """A rounded, slightly-lighter panel used to group related controls."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BG_CARD_BORDER,
            **kwargs,
        )


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("yt-dlp GUI Downloader")
        self.geometry("900x680")
        self.minsize(820, 620)
        self.configure(fg_color=BG_DEEP)

        icon_path = resource_path("assets/icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self._event_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._download_active = False

        self._build_layout()
        self.after(100, self._drain_event_queue)

        if not ffmpeg_available():
            self._append_log(
                "Hinweis: ffmpeg wurde nicht gefunden. Für Audio-Extraktion und das "
                "Zusammenführen mancher Formate wird ffmpeg benötigt (auf PATH installieren)."
            )

    # ------------------------------------------------------------------ UI

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        hero = HeroBanner(self, on_library_click=self._show_library)
        hero.grid(row=0, column=0, sticky="ew")

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=1, column=0, padx=24, pady=20, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.download_view = ctk.CTkFrame(container, fg_color="transparent")
        self.download_view.grid(row=0, column=0, sticky="nsew")
        self.download_view.grid_columnconfigure(0, weight=1)

        self.library_view = ctk.CTkFrame(container, fg_color="transparent")
        self.library_view.grid(row=0, column=0, sticky="nsew")

        self._build_download_view(self.download_view)
        self._build_library_view(self.library_view)

        self.mascot = MascotOverlay(
            container,
            exhausted_path=resource_path("assets/cat_exhausted.png"),
            happy_path=resource_path("assets/cat_happy.png"),
            sound_path=resource_path("assets/sparkle.mp3"),
            bg_color=BG_DEEP,
        )

        self.download_view.tkraise()

    def _build_download_view(self, body: ctk.CTkFrame) -> None:
        entry_style = dict(
            fg_color=BG_DEEP,
            border_color=BG_CARD_BORDER,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_SECONDARY,
            height=38,
            corner_radius=10,
        )

        # URL card
        url_card = Card(body)
        url_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        url_card.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_card, placeholder_text="https://www.youtube.com/watch?v=...", **entry_style
        )
        self.url_entry.grid(row=0, column=0, padx=14, pady=14, sticky="ew")

        # Output dir card
        output_card = Card(body)
        output_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        output_card.grid_columnconfigure(0, weight=1)

        self.output_entry = ctk.CTkEntry(output_card, **entry_style)
        self.output_entry.insert(0, DEFAULT_OUTPUT_DIR)
        self.output_entry.grid(row=0, column=0, padx=(14, 8), pady=14, sticky="ew")

        browse_button = ctk.CTkButton(
            output_card,
            text="Ordner wählen",
            width=120,
            height=38,
            corner_radius=10,
            fg_color=BG_CARD_BORDER,
            hover_color=ACCENT,
            text_color=TEXT_PRIMARY,
            command=self._browse_output_dir,
        )
        browse_button.grid(row=0, column=1, padx=(0, 14), pady=14)

        # Options card
        options_card = Card(body)
        options_card.grid(row=2, column=0, sticky="ew", pady=(0, 20))

        self.format_menu = ctk.CTkOptionMenu(
            options_card,
            values=list(FORMAT_PRESETS.keys()),
            height=36,
            corner_radius=10,
            fg_color=BG_CARD_BORDER,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            dropdown_fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
        )
        self.format_menu.set("Beste Qualität (Video+Audio)")
        self.format_menu.grid(row=0, column=0, padx=14, pady=14, sticky="w")

        self.playlist_var = ctk.BooleanVar(value=False)
        playlist_check = ctk.CTkCheckBox(
            options_card,
            text="Ganze Playlist herunterladen",
            variable=self.playlist_var,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
        )
        playlist_check.grid(row=0, column=1, padx=(20, 14), pady=14, sticky="w")

        # Download button
        self.download_button = ctk.CTkButton(
            body,
            text="Herunterladen",
            height=46,
            corner_radius=23,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#0A0C22",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=15, weight="bold"),
            command=self._start_download,
        )
        self.download_button.grid(row=3, column=0, sticky="ew", pady=(0, 18))

        # Progress
        progress_frame = ctk.CTkFrame(body, fg_color="transparent")
        progress_frame.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame, progress_color=ACCENT, fg_color=BG_CARD_BORDER, height=8, corner_radius=4
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        self.progress_label = ctk.CTkLabel(progress_frame, text="0%", width=44, text_color=TEXT_SECONDARY)
        self.progress_label.grid(row=0, column=1, padx=(8, 0))

        self.status_label = ctk.CTkLabel(body, text="Bereit.", text_color=TEXT_SECONDARY, anchor="w")
        self.status_label.grid(row=5, column=0, sticky="ew", pady=(4, 12))

        # Log
        self.log_box = ctk.CTkTextbox(
            body,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BG_CARD_BORDER,
            corner_radius=14,
            text_color=TEXT_SECONDARY,
            font=("Consolas", 11),
            state="disabled",
        )
        self.log_box.grid(row=6, column=0, sticky="nsew")
        body.grid_rowconfigure(6, weight=1)

    def _build_library_view(self, view: ctk.CTkFrame) -> None:
        view.grid_columnconfigure(0, weight=0)
        view.grid_columnconfigure(1, weight=1)
        view.grid_rowconfigure(1, weight=1)

        top_row = ctk.CTkFrame(view, fg_color="transparent")
        top_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        top_row.grid_columnconfigure(1, weight=1)

        back_button = ctk.CTkButton(
            top_row,
            text="‹ Zurück",
            width=90,
            height=34,
            corner_radius=10,
            fg_color=BG_CARD_BORDER,
            hover_color=ACCENT,
            text_color=TEXT_PRIMARY,
            command=self._show_downloader,
        )
        back_button.grid(row=0, column=0, sticky="w")

        self.library_path_label = ctk.CTkLabel(top_row, text=DEFAULT_OUTPUT_DIR, text_color=TEXT_SECONDARY)
        self.library_path_label.grid(row=0, column=1, padx=14, sticky="w")

        refresh_button = ctk.CTkButton(
            top_row,
            text="⟳",
            width=36,
            height=34,
            corner_radius=10,
            fg_color=BG_CARD_BORDER,
            hover_color=ACCENT,
            text_color=TEXT_PRIMARY,
            command=self._refresh_library,
        )
        refresh_button.grid(row=0, column=2, sticky="e")

        list_card = Card(view, width=240)
        list_card.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        list_card.grid_propagate(False)

        self.file_list_frame = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        self.file_list_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.player_widget = PlayerWidget(
            view,
            accent=ACCENT,
            card_color=BG_CARD,
            border_color=BG_CARD_BORDER,
            text_color=TEXT_PRIMARY,
            muted_color=TEXT_SECONDARY,
        )
        self.player_widget.grid(row=1, column=1, sticky="nsew")

        if not self.player_widget.available:
            self._append_log(
                "Hinweis: VLC wurde nicht gefunden. Installiere VLC Media Player, um Dateien "
                "direkt in der App abzuspielen."
            )

    # ------------------------------------------------------------ Actions

    def _browse_output_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_entry.get() or str(Path.home()))
        if chosen:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, chosen)

    def _start_download(self) -> None:
        if self._download_active:
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Keine URL", "Bitte zuerst eine Video- oder Playlist-URL eingeben.")
            return

        output_dir = self.output_entry.get().strip() or DEFAULT_OUTPUT_DIR
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Ordnerfehler", f"Zielordner konnte nicht erstellt werden:\n{exc}")
            return

        options = DownloadOptions(
            url=url,
            output_dir=output_dir,
            format_label=self.format_menu.get(),
            playlist=self.playlist_var.get(),
        )

        self._set_download_active(True)
        self._clear_log()
        self.progress_bar.set(0)
        self.progress_label.configure(text="0%")
        self.status_label.configure(text="Starte Download...")
        self.mascot.show_exhausted()

        thread = threading.Thread(target=self._run_download, args=(options,), daemon=True)
        thread.start()

    def _run_download(self, options: DownloadOptions) -> None:
        logger = GuiLogger(lambda msg: self._event_queue.put(("log", msg)))

        def hook(d: dict) -> None:
            self._event_queue.put(("progress", d))

        try:
            download(options, hook, logger)
            self._event_queue.put(("done", None))
        except Exception as exc:  # noqa: BLE001 - surface any yt-dlp failure to the GUI
            self._event_queue.put(("error", str(exc)))

    # -------------------------------------------------------------- Queue

    def _drain_event_queue(self) -> None:
        try:
            while True:
                kind, payload = self._event_queue.get_nowait()
                if kind == "progress":
                    self._handle_progress(payload)
                elif kind == "log":
                    self._append_log(payload)
                elif kind == "done":
                    self._on_download_finished()
                elif kind == "error":
                    self._on_download_error(payload)
        except queue.Empty:
            pass
        self.after(100, self._drain_event_queue)

    def _handle_progress(self, d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            filename = os.path.basename(d.get("filename") or "")
            if total:
                fraction = min(downloaded / total, 1.0)
                self.progress_bar.set(fraction)
                self.progress_label.configure(text=f"{fraction * 100:.0f}%")
            self.status_label.configure(text=f"Lade herunter: {filename}")
        elif status == "finished":
            self.progress_bar.set(1.0)
            self.progress_label.configure(text="100%")
            self.status_label.configure(text="Verarbeite (Konvertierung / Zusammenführen)...")

    def _on_download_finished(self) -> None:
        self._set_download_active(False)
        self.status_label.configure(text="Fertig!")
        self._append_log("Download abgeschlossen.")
        self._refresh_library()
        self.mascot.celebrate_and_hide()

    def _on_download_error(self, message: str) -> None:
        self._set_download_active(False)
        self.status_label.configure(text="Fehler beim Download.")
        self._append_log(f"FEHLER: {message}")
        self.mascot.hide_immediately()
        messagebox.showerror("Download fehlgeschlagen", message)

    def _set_download_active(self, active: bool) -> None:
        self._download_active = active
        self.download_button.configure(
            state="disabled" if active else "normal",
            text="Läuft..." if active else "Herunterladen",
        )

    # ---------------------------------------------------------- Library

    def _show_library(self) -> None:
        self._refresh_library()
        self.library_view.tkraise()

    def _show_downloader(self) -> None:
        self.player_widget.stop()
        self.download_view.tkraise()

    def _refresh_library(self) -> None:
        output_dir = self.output_entry.get().strip() or DEFAULT_OUTPUT_DIR
        self.library_path_label.configure(text=output_dir)

        for child in self.file_list_frame.winfo_children():
            child.destroy()

        try:
            entries = sorted(Path(output_dir).iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            entries = []

        media_files = [p for p in entries if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS]

        if not media_files:
            empty_label = ctk.CTkLabel(self.file_list_frame, text="Keine Dateien gefunden.", text_color=TEXT_SECONDARY)
            empty_label.pack(pady=12)
            return

        for path in media_files:
            icon = "🎬" if path.suffix.lower() in VIDEO_EXTENSIONS else "🎵"
            row = ctk.CTkButton(
                self.file_list_frame,
                text=f"{icon}  {path.name}",
                anchor="w",
                fg_color="transparent",
                hover_color=BG_CARD_BORDER,
                text_color=TEXT_PRIMARY,
                command=lambda p=path: self._play_file(p),
            )
            row.pack(fill="x", pady=2)

    def _play_file(self, path: Path) -> None:
        if not self.player_widget.available:
            messagebox.showwarning(
                "Player nicht verfügbar",
                "VLC wurde nicht gefunden. Bitte installiere VLC Media Player, um Dateien "
                "direkt in der App abzuspielen.",
            )
            return
        self.player_widget.load_and_play(str(path))

    # -------------------------------------------------------------- Log

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
