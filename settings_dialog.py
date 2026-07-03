"""A small modal settings dialog: sound volume, bug reports, support link, exit."""
from __future__ import annotations

import webbrowser
from typing import Callable

import customtkinter as ctk

GITHUB_ISSUES_URL = "https://github.com/ClarasC0DE/cute-yt-dlp-converter/issues"
KOFI_URL = "https://ko-fi.com/extrafirmtofu"


class SettingsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        bg: str,
        card_color: str,
        border_color: str,
        accent: str,
        accent_hover: str,
        text_primary: str,
        text_secondary: str,
        initial_volume: int,
        on_volume_change: Callable[[int], None],
        on_exit_app: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("Settings")
        self.geometry("380x420")
        self.resizable(False, False)
        self.configure(fg_color=bg)
        self.transient(master)

        self._on_volume_change = on_volume_change

        header = ctk.CTkLabel(
            self, text="Settings", font=ctk.CTkFont(family="Poppins SemiBold", size=20), text_color=text_primary
        )
        header.pack(padx=24, pady=(24, 16), anchor="w")

        # Volume card
        volume_card = ctk.CTkFrame(self, fg_color=card_color, corner_radius=14, border_width=1, border_color=border_color)
        volume_card.pack(padx=24, pady=(0, 14), fill="x")

        volume_label = ctk.CTkLabel(volume_card, text="Sound effect volume", text_color=text_primary)
        volume_label.pack(padx=16, pady=(14, 6), anchor="w")

        slider_row = ctk.CTkFrame(volume_card, fg_color="transparent")
        slider_row.pack(padx=16, pady=(0, 14), fill="x")
        slider_row.grid_columnconfigure(0, weight=1)

        self._volume_value_label = ctk.CTkLabel(slider_row, text=f"{initial_volume}%", text_color=text_secondary, width=40)

        self.volume_slider = ctk.CTkSlider(
            slider_row,
            from_=0,
            to=100,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent_hover,
            command=self._handle_volume_change,
        )
        self.volume_slider.set(initial_volume)
        self.volume_slider.grid(row=0, column=0, sticky="ew")
        self._volume_value_label.grid(row=0, column=1, padx=(10, 0))

        # Support card
        support_card = ctk.CTkFrame(self, fg_color=card_color, corner_radius=14, border_width=1, border_color=border_color)
        support_card.pack(padx=24, pady=(0, 14), fill="x")

        support_label = ctk.CTkLabel(
            support_card,
            text="Enjoying the app?",
            text_color=text_primary,
        )
        support_label.pack(padx=16, pady=(14, 6), anchor="w")

        kofi_button = ctk.CTkButton(
            support_card,
            text="☕ Buy me a coffee",
            fg_color="#FF5E5B",
            hover_color="#E5514E",
            text_color="#FFFFFF",
            command=lambda: webbrowser.open(KOFI_URL),
        )
        kofi_button.pack(padx=16, pady=(0, 14), fill="x")

        # Bug report card
        bug_card = ctk.CTkFrame(self, fg_color=card_color, corner_radius=14, border_width=1, border_color=border_color)
        bug_card.pack(padx=24, pady=(0, 14), fill="x")

        bug_label = ctk.CTkLabel(
            bug_card,
            text="Found a bug? Please report it so it can get fixed.",
            text_color=text_primary,
            wraplength=300,
            justify="left",
        )
        bug_label.pack(padx=16, pady=(14, 6), anchor="w")

        bug_button = ctk.CTkButton(
            bug_card,
            text="Report a bug on GitHub",
            fg_color=border_color,
            hover_color=accent,
            text_color=text_primary,
            command=lambda: webbrowser.open(GITHUB_ISSUES_URL),
        )
        bug_button.pack(padx=16, pady=(0, 14), fill="x")

        # Exit button
        exit_button = ctk.CTkButton(
            self,
            text="Exit App",
            fg_color="transparent",
            hover_color=card_color,
            border_width=1,
            border_color=border_color,
            text_color=text_secondary,
            command=on_exit_app,
        )
        exit_button.pack(padx=24, pady=(6, 24), fill="x")

        self.after(10, self._center_over_master)
        self.after(50, self.grab_set)

    def _handle_volume_change(self, value: float) -> None:
        volume = int(value)
        self._volume_value_label.configure(text=f"{volume}%")
        self._on_volume_change(volume)

    def _center_over_master(self) -> None:
        self.update_idletasks()
        master = self.master
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
