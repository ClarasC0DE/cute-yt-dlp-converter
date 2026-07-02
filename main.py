"""yt-dlp GUI Downloader

A small, modern desktop GUI around yt-dlp for downloading videos/audio.
"""
from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from downloader import AUDIO_ONLY_LABEL, FORMAT_PRESETS, DownloadOptions, GuiLogger, download, ffmpeg_available

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads" / "yt-dlp-gui")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("yt-dlp GUI Downloader")
        self.geometry("720x600")
        self.minsize(640, 560)

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

        header = ctk.CTkLabel(
            self, text="yt-dlp Downloader", font=ctk.CTkFont(size=24, weight="bold")
        )
        header.grid(row=0, column=0, padx=24, pady=(24, 8), sticky="w")

        subtitle = ctk.CTkLabel(
            self,
            text="Video- oder Playlist-URL einfügen und herunterladen.",
            text_color="gray60",
        )
        subtitle.grid(row=1, column=0, padx=24, pady=(0, 16), sticky="w")

        # URL row
        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.grid(row=2, column=0, padx=24, pady=4, sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="https://www.youtube.com/watch?v=...", height=40
        )
        self.url_entry.grid(row=0, column=0, sticky="ew")

        # Output dir row
        output_frame = ctk.CTkFrame(self, fg_color="transparent")
        output_frame.grid(row=3, column=0, padx=24, pady=4, sticky="ew")
        output_frame.grid_columnconfigure(0, weight=1)

        self.output_entry = ctk.CTkEntry(output_frame, height=40)
        self.output_entry.insert(0, DEFAULT_OUTPUT_DIR)
        self.output_entry.grid(row=0, column=0, sticky="ew")

        browse_button = ctk.CTkButton(
            output_frame, text="Ordner wählen", width=120, height=40, command=self._browse_output_dir
        )
        browse_button.grid(row=0, column=1, padx=(8, 0))

        # Format + playlist row
        options_frame = ctk.CTkFrame(self, fg_color="transparent")
        options_frame.grid(row=4, column=0, padx=24, pady=(12, 4), sticky="ew")

        self.format_menu = ctk.CTkOptionMenu(options_frame, values=list(FORMAT_PRESETS.keys()), height=36)
        self.format_menu.set("Beste Qualität (Video+Audio)")
        self.format_menu.grid(row=0, column=0, sticky="w")

        self.playlist_var = ctk.BooleanVar(value=False)
        playlist_check = ctk.CTkCheckBox(
            options_frame, text="Ganze Playlist herunterladen", variable=self.playlist_var
        )
        playlist_check.grid(row=0, column=1, padx=(20, 0), sticky="w")

        # Download button
        self.download_button = ctk.CTkButton(
            self,
            text="Herunterladen",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_download,
        )
        self.download_button.grid(row=5, column=0, padx=24, pady=(16, 8), sticky="ew")

        # Progress
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=6, column=0, padx=24, pady=(4, 4), sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        self.progress_label = ctk.CTkLabel(progress_frame, text="0%", width=48)
        self.progress_label.grid(row=0, column=1, padx=(8, 0))

        self.status_label = ctk.CTkLabel(self, text="Bereit.", text_color="gray60", anchor="w")
        self.status_label.grid(row=7, column=0, padx=24, pady=(4, 8), sticky="ew")

        # Log
        self.log_box = ctk.CTkTextbox(self, height=200, state="disabled")
        self.log_box.grid(row=8, column=0, padx=24, pady=(0, 24), sticky="nsew")
        self.grid_rowconfigure(8, weight=1)

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

    def _on_download_error(self, message: str) -> None:
        self._set_download_active(False)
        self.status_label.configure(text="Fehler beim Download.")
        self._append_log(f"FEHLER: {message}")
        messagebox.showerror("Download fehlgeschlagen", message)

    def _set_download_active(self, active: bool) -> None:
        self._download_active = active
        self.download_button.configure(
            state="disabled" if active else "normal",
            text="Läuft..." if active else "Herunterladen",
        )

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
