"""Desktop GUI for CD ripping (CustomTkinter, cross-platform)."""

from __future__ import annotations

import queue
import threading
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

# Token definitions for format builder: (id, display label, format string value)
FILENAME_TOKENS: list[tuple[str, str, str]] = [
    ("track_number_02d", "Track # (01)", "%(track_number)2.2d"),
    ("track_number_s", "Track #", "%(track_number)s"),
    ("track_name", "Track name", "%(track_name)s"),
    ("artist_name", "Artist", "%(artist_name)s"),
    ("album_name", "Album", "%(album_name)s"),
    ("year", "Year", "%(year)s"),
    ("suffix", "Extension", "%(suffix)s"),
    ("sep_dash", " — ", " - "),
    ("sep_space", " (space) ", " "),
]
FOLDER_TOKENS: list[tuple[str, str, str]] = [
    ("artist_name", "Artist", "%(artist_name)s"),
    ("album_name", "Album", "%(album_name)s"),
    ("year", "Year", "%(year)s"),
    ("track_number_02d", "Track # (01)", "%(track_number)2.2d"),
    ("track_number_s", "Track #", "%(track_number)s"),
    ("track_name", "Track name", "%(track_name)s"),
    ("sep_slash", " / ", " / "),
    ("sep_space", " (space) ", " "),
]


class FormatBuilderFrame(ctk.CTkFrame):
    """Format builder: each position is a dropdown; user can add or remove slots."""

    def __init__(
        self,
        parent: Any,
        tokens: list[tuple[str, str, str]],
        default_ids: list[str],
        title: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._tokens = {tid: (label, value) for tid, label, value in tokens}
        self._token_list = tokens
        self._labels = [label for _, label, _ in tokens]
        self._label_to_tid_value: dict[str, tuple[str, str]] = {
            label: (tid, value) for tid, label, value in tokens
        }
        self._sequence: list[tuple[str, str]] = []  # (id, value) per slot
        self._container_frame: ctk.CTkFrame | None = None
        self._slot_widgets: list[tuple[ctk.CTkOptionMenu, ctk.CTkButton]] = []

        for tid in default_ids:
            if tid in self._tokens:
                label, value = self._tokens[tid]
                self._sequence.append((tid, value))

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="Choose a token for each position; add or remove slots as needed.").pack(anchor="w", pady=(8, 2))

        self._container_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=6)
        self._container_frame.pack(fill="x", pady=(0, 4))

        self._preview_label = ctk.CTkLabel(self, text="", anchor="w", text_color=("gray40", "gray60"))
        self._preview_label.pack(anchor="w", pady=(0, 4))

        self._rebuild_slots()

    def _rebuild_slots(self) -> None:
        if self._container_frame is None:
            return
        for w in self._container_frame.winfo_children():
            w.destroy()
        self._slot_widgets.clear()

        inner = ctk.CTkFrame(self._container_frame, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=8)

        for i in range(len(self._sequence)):
            tid, value = self._sequence[i]
            current_label = self._tokens.get(tid, (value, value))[0]
            menu = ctk.CTkOptionMenu(
                inner,
                values=self._labels,
                command=lambda choice, idx=i: self._on_slot_change(idx, choice),
                width=140,
            )
            menu.set(current_label)
            menu.pack(side="left", padx=(0, 2), pady=2)
            remove_btn = ctk.CTkButton(
                inner, text="×", width=28, height=28, fg_color="transparent",
                command=lambda idx=i: self._remove_at(idx),
            )
            remove_btn.pack(side="left", padx=(0, 6), pady=2)
            self._slot_widgets.append((menu, remove_btn))

        add_btn = ctk.CTkButton(inner, text="+ Add", width=70, height=28, fg_color=("gray70", "gray35"), command=self._add_slot)
        add_btn.pack(side="left", padx=(4, 0), pady=2)

        self._preview_label.configure(text=f"Result: {self.get_format_string() or '(empty)'}")

    def _on_slot_change(self, index: int, chosen_label: str) -> None:
        if 0 <= index < len(self._sequence) and chosen_label in self._label_to_tid_value:
            tid, value = self._label_to_tid_value[chosen_label]
            self._sequence[index] = (tid, value)
            self._preview_label.configure(text=f"Result: {self.get_format_string() or '(empty)'}")

    def _remove_at(self, index: int) -> None:
        if 0 <= index < len(self._sequence):
            self._sequence.pop(index)
            self._rebuild_slots()

    def _add_slot(self) -> None:
        if self._token_list:
            tid, label, value = self._token_list[0]
            self._sequence.append((tid, value))
        else:
            self._sequence.append(("", ""))
        self._rebuild_slots()

    def get_format_string(self) -> str:
        return "".join(value for _, value in self._sequence)

    def set_format_string(self, s: str) -> None:
        """Parse a format string into tokens where possible; rebuild slots."""
        self._sequence.clear()
        if not s:
            self._rebuild_slots()
            return
        remaining = s
        while remaining:
            found = False
            for tid, _, value in self._token_list:
                if remaining.startswith(value):
                    self._sequence.append((tid, value))
                    remaining = remaining[len(value):]
                    found = True
                    break
            if not found:
                for tid, _, value in self._token_list:
                    if value in remaining:
                        idx = remaining.index(value)
                        if idx > 0:
                            lit = remaining[:idx]
                            self._sequence.append((None, lit))
                        self._sequence.append((tid, value))
                        remaining = remaining[idx + len(value):]
                        found = True
                        break
            if not found:
                self._sequence.append((None, remaining[0]))
                remaining = remaining[1:]
        self._rebuild_slots()


# Default appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _run_rip_worker(
    device_path: str,
    formats: list[str],
    format_to_dir: dict[str, str],
    name_format: str,
    folder_format: str,
    no_lookup: bool,
    no_interactive: bool,
    verify_accuraterip: bool,
    quality_map: dict[str, str],
    bitrate_map: dict[str, str],
    log_queue: queue.Queue[str | None],
) -> None:
    """Run rip in background; send log lines to log_queue (None = done)."""
    try:
        from src.bitrates import is_bitrate_supported, format_supported_list
        from src.cd import get_default_device, open_cd
        from src.encode import run_rip
        from src.metadata import resolve_metadata

        path = (device_path or get_default_device()).strip()

        def log_cb(msg: str, err: bool) -> None:
            log_queue.put(msg)

        with open_cd(path) as (reader, track_lengths):
            cue_toc = getattr(reader, "cue_toc", None)
            cue_leadout = getattr(reader, "cue_leadout", None)
            metadata_list = resolve_metadata(
                path,
                track_lengths,
                cue_toc=cue_toc,
                cue_leadout=cue_leadout,
                lookup=not no_lookup,
                interactive=not no_interactive,
            )
            run_rip(
                reader=reader,
                track_lengths=track_lengths,
                metadata_list=metadata_list,
                formats=formats,
                format_to_dir=format_to_dir,
                name_format=name_format,
                folder_format=folder_format or "%(album_name)s",
                quality_map=quality_map,
                bitrate_map=bitrate_map,
                verify_accuraterip=verify_accuraterip,
                log_callback=log_cb,
            )
        log_queue.put(None)
    except Exception as e:
        log_queue.put(f"Error: {e}")
        log_queue.put(None)


def _run_list_worker(
    device_path: str,
    result_queue: queue.Queue[tuple[list[str] | None, str | None]],
) -> None:
    """List CD tracks in background; put (lines, error) then (None, None)."""
    try:
        from src.cd import get_default_device, open_cd
        from src.metadata import resolve_metadata

        path = (device_path or get_default_device()).strip()
        lines: list[str] = []
        with open_cd(path) as (reader, track_lengths):
            n = len(track_lengths)
            lines.append(f"Tracks: {n}")
            for i, length in enumerate(track_lengths, 1):
                lines.append(f"  Track {i}: {length} PCM frames")
            cue_toc = getattr(reader, "cue_toc", None)
            cue_leadout = getattr(reader, "cue_leadout", None)
            metadata_list = resolve_metadata(
                path,
                track_lengths,
                cue_toc=cue_toc,
                cue_leadout=cue_leadout,
                lookup=True,
                interactive=False,
            )
            if metadata_list:
                for i, meta in enumerate(metadata_list, 1):
                    artist = getattr(meta, "artist_name", None) or ""
                    title = getattr(meta, "track_name", None) or ""
                    lines.append(f"  {i}. {artist} - {title}")
        result_queue.put((lines, None))
        result_queue.put((None, None))
    except Exception as e:
        result_queue.put((None, str(e)))
        result_queue.put((None, None))


class RippingApp(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("CD Ripper")
        self.geometry("800x700")
        self.minsize(600, 500)

        self._rip_thread: threading.Thread | None = None
        self._list_thread: threading.Thread | None = None
        self._log_queue: queue.Queue[str | None] = queue.Queue()
        self._list_queue: queue.Queue[tuple[list[str] | None, str | None]] = queue.Queue()

        self._build_ui()
        self._poll_log_queue()
        self._poll_list_queue()

    def _build_ui(self) -> None:
        from src.cd import get_default_device

        default_device = get_default_device()

        # Notebook-style: two tabs
        self.tabview = ctk.CTkTabview(self, width=780)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabview.add("List CD")
        self.tabview.add("Rip CD")

        # --- List CD tab ---
        list_tab = self.tabview.tab("List CD")
        list_frame = ctk.CTkFrame(list_tab, fg_color="transparent")
        list_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(list_frame, text="Device or .cue path:").pack(anchor="w")
        list_dev_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_dev_frame.pack(fill="x", pady=(0, 5))
        self.list_device = ctk.CTkEntry(
            list_dev_frame, placeholder_text=default_device, width=400
        )
        self.list_device.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.list_btn = ctk.CTkButton(list_dev_frame, text="Browse…", width=80, command=self._browse_cue_list)
        self.list_btn.pack(side="left", padx=(0, 8))
        self.list_go_btn = ctk.CTkButton(list_dev_frame, text="List tracks", command=self._on_list_cd)
        self.list_go_btn.pack(side="left")

        self.list_text = ctk.CTkTextbox(list_frame, height=300, state="disabled")
        self.list_text.pack(fill="both", expand=True, pady=(8, 0))

        # --- Rip CD tab ---
        rip_tab = self.tabview.tab("Rip CD")
        rip_scroll = ctk.CTkScrollableFrame(rip_tab, fg_color="transparent")
        rip_scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(rip_scroll, text="Device or .cue path:").pack(anchor="w")
        rip_dev_frame = ctk.CTkFrame(rip_scroll, fg_color="transparent")
        rip_dev_frame.pack(fill="x", pady=(0, 8))
        self.rip_device = ctk.CTkEntry(
            rip_dev_frame, placeholder_text=default_device, width=400
        )
        self.rip_device.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.rip_browse_btn = ctk.CTkButton(rip_dev_frame, text="Browse…", width=80, command=self._browse_cue_rip)
        self.rip_browse_btn.pack(side="left", padx=(0, 8))

        # Nested tabview: one tab per encoding format
        from src.bitrates import SUPPORTED_BITRATES

        self.rip_format_tabs = ctk.CTkTabview(rip_scroll, fg_color="transparent")
        self.rip_format_tabs.pack(fill="x", pady=(8, 0))
        self.rip_format_tabs.add("FLAC")
        self.rip_format_tabs.add("MP3")
        self.rip_format_tabs.add("WAV")

        # FLAC tab
        flac_tab = self.rip_format_tabs.tab("FLAC")
        self.rip_flac_enable = ctk.CTkCheckBox(flac_tab, text="Enable FLAC output")
        self.rip_flac_enable.pack(anchor="w")
        self.rip_flac_enable.select()
        ctk.CTkLabel(flac_tab, text="Output directory:").pack(anchor="w", pady=(8, 0))
        flac_dir_frame = ctk.CTkFrame(flac_tab, fg_color="transparent")
        flac_dir_frame.pack(fill="x", pady=(0, 4))
        self.rip_flac_dir = ctk.CTkEntry(flac_dir_frame, placeholder_text="(current directory if empty)")
        self.rip_flac_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(flac_dir_frame, text="Browse…", width=80, command=lambda: self._browse_output_dir("flac")).pack(side="left")
        ctk.CTkLabel(flac_tab, text="Compression level:").pack(anchor="w", pady=(8, 0))
        flac_opts = SUPPORTED_BITRATES.get("flac", [str(i) for i in range(9)])
        self.rip_flac_quality = ctk.CTkOptionMenu(flac_tab, values=flac_opts)
        self.rip_flac_quality.set("5")
        self.rip_flac_quality.pack(anchor="w", pady=(0, 4))

        # MP3 tab
        mp3_tab = self.rip_format_tabs.tab("MP3")
        self.rip_mp3_enable = ctk.CTkCheckBox(mp3_tab, text="Enable MP3 output")
        self.rip_mp3_enable.pack(anchor="w")
        ctk.CTkLabel(mp3_tab, text="Output directory:").pack(anchor="w", pady=(8, 0))
        mp3_dir_frame = ctk.CTkFrame(mp3_tab, fg_color="transparent")
        mp3_dir_frame.pack(fill="x", pady=(0, 4))
        self.rip_mp3_dir = ctk.CTkEntry(mp3_dir_frame, placeholder_text="(current directory if empty)")
        self.rip_mp3_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(mp3_dir_frame, text="Browse…", width=80, command=lambda: self._browse_output_dir("mp3")).pack(side="left")
        ctk.CTkLabel(mp3_tab, text="Bitrate (kbps):").pack(anchor="w", pady=(8, 0))
        mp3_opts = SUPPORTED_BITRATES.get("mp3", ["192", "320"])
        self.rip_mp3_bitrate = ctk.CTkOptionMenu(mp3_tab, values=mp3_opts)
        self.rip_mp3_bitrate.set("192")
        self.rip_mp3_bitrate.pack(anchor="w", pady=(0, 4))

        # WAV tab
        wav_tab = self.rip_format_tabs.tab("WAV")
        self.rip_wav_enable = ctk.CTkCheckBox(wav_tab, text="Enable WAV output")
        self.rip_wav_enable.pack(anchor="w")
        ctk.CTkLabel(wav_tab, text="Output directory:").pack(anchor="w", pady=(8, 0))
        wav_dir_frame = ctk.CTkFrame(wav_tab, fg_color="transparent")
        wav_dir_frame.pack(fill="x", pady=(0, 4))
        self.rip_wav_dir = ctk.CTkEntry(wav_dir_frame, placeholder_text="(current directory if empty)")
        self.rip_wav_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(wav_dir_frame, text="Browse…", width=80, command=lambda: self._browse_output_dir("wav")).pack(side="left")

        # Filename format: drag-and-drop token builder
        self.name_format_builder = FormatBuilderFrame(
            rip_scroll,
            tokens=FILENAME_TOKENS,
            default_ids=["track_number_02d", "sep_dash", "track_name"],
            title="Filename format",
        )
        self.name_format_builder.pack(fill="x", pady=(12, 8))

        # Folder format: drag-and-drop token builder
        self.folder_format_builder = FormatBuilderFrame(
            rip_scroll,
            tokens=FOLDER_TOKENS,
            default_ids=["album_name"],
            title="Folder structure under output dir",
        )
        self.folder_format_builder.pack(fill="x", pady=(4, 8))

        opt_frame = ctk.CTkFrame(rip_scroll, fg_color="transparent")
        opt_frame.pack(fill="x", pady=(8, 0))
        self.no_lookup = ctk.CTkCheckBox(opt_frame, text="Skip MusicBrainz lookup")
        self.no_lookup.pack(side="left", padx=(0, 16))
        self.no_interactive = ctk.CTkCheckBox(opt_frame, text="Use first metadata match (no prompt)")
        self.no_interactive.pack(side="left", padx=(0, 16))
        self.no_interactive.select()
        self.verify_ar = ctk.CTkCheckBox(opt_frame, text="Show AccurateRip status")
        self.verify_ar.pack(side="left")
        self.verify_ar.select()

        config_btn_frame = ctk.CTkFrame(rip_scroll, fg_color="transparent")
        config_btn_frame.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(config_btn_frame, text="Export settings…", width=120, command=self._on_export_settings).pack(side="left", padx=(0, 8))
        ctk.CTkButton(config_btn_frame, text="Import settings…", width=120, command=self._on_import_settings).pack(side="left")

        self.rip_go_btn = ctk.CTkButton(rip_scroll, text="Start rip", command=self._on_rip, fg_color="green", hover_color="darkgreen")
        self.rip_go_btn.pack(anchor="w", pady=(12, 8))

        ctk.CTkLabel(rip_scroll, text="Log:").pack(anchor="w")
        self.rip_log = ctk.CTkTextbox(rip_scroll, height=200, state="normal")
        self.rip_log.pack(fill="both", expand=True, pady=(4, 0))

    def _browse_cue_list(self) -> None:
        path = filedialog.askopenfilename(
            title="Select CUE file",
            filetypes=[("CUE sheets", "*.cue"), ("All files", "*.*")],
        )
        if path:
            self.list_device.delete(0, "end")
            self.list_device.insert(0, path)

    def _browse_cue_rip(self) -> None:
        path = filedialog.askopenfilename(
            title="Select CUE file",
            filetypes=[("CUE sheets", "*.cue"), ("All files", "*.*")],
        )
        if path:
            self.rip_device.delete(0, "end")
            self.rip_device.insert(0, path)

    def _browse_output_dir(self, fmt: str) -> None:
        path = filedialog.askdirectory(title=f"Output directory for {fmt.upper()}")
        if path:
            if fmt == "flac":
                self.rip_flac_dir.delete(0, "end")
                self.rip_flac_dir.insert(0, path)
            elif fmt == "mp3":
                self.rip_mp3_dir.delete(0, "end")
                self.rip_mp3_dir.insert(0, path)
            elif fmt == "wav":
                self.rip_wav_dir.delete(0, "end")
                self.rip_wav_dir.insert(0, path)

    def _get_config_from_ui(self) -> dict[str, Any]:
        """Build a config dict from current GUI state (same shape as config.DEFAULT_CONFIG)."""
        formats: list[str] = []
        if self.rip_flac_enable.get():
            formats.append("flac")
        if self.rip_mp3_enable.get():
            formats.append("mp3")
        if self.rip_wav_enable.get():
            formats.append("wav")
        if not formats:
            formats = ["flac"]
        output_dirs: dict[str, str] = {}
        for fmt in ("flac", "mp3", "wav"):
            if fmt == "flac":
                output_dirs[fmt] = self.rip_flac_dir.get().strip() or "."
            elif fmt == "mp3":
                output_dirs[fmt] = self.rip_mp3_dir.get().strip() or "."
            else:
                output_dirs[fmt] = self.rip_wav_dir.get().strip() or "."
        quality: dict[str, str] = {}
        bitrate: dict[str, str] = {}
        if "flac" in formats:
            quality["flac"] = self.rip_flac_quality.get()
        if "mp3" in formats:
            bitrate["mp3"] = self.rip_mp3_bitrate.get()
        name_fmt = self.name_format_builder.get_format_string().strip() or "%(track_number)2.2d - %(track_name)s"
        folder_fmt = self.folder_format_builder.get_format_string().strip() or "%(album_name)s"
        return {
            "formats": formats,
            "device": self.rip_device.get().strip() or "",
            "name_format": name_fmt,
            "folder_format": folder_fmt,
            "no_lookup": self.no_lookup.get(),
            "no_interactive": self.no_interactive.get(),
            "verify_accuraterip": self.verify_ar.get(),
            "output_dirs": output_dirs,
            "quality": quality,
            "bitrate": bitrate,
        }

    def _apply_config_to_ui(self, cfg: dict[str, Any]) -> None:
        """Overwrite current GUI settings with values from a config dict."""
        formats = cfg.get("formats", ["flac"])
        self.rip_flac_enable.deselect()
        self.rip_mp3_enable.deselect()
        self.rip_wav_enable.deselect()
        for f in formats:
            if f == "flac":
                self.rip_flac_enable.select()
            elif f == "mp3":
                self.rip_mp3_enable.select()
            elif f == "wav":
                self.rip_wav_enable.select()
        output_dirs = cfg.get("output_dirs") or {}
        self.rip_flac_dir.delete(0, "end")
        self.rip_flac_dir.insert(0, output_dirs.get("flac", ""))
        self.rip_mp3_dir.delete(0, "end")
        self.rip_mp3_dir.insert(0, output_dirs.get("mp3", ""))
        self.rip_wav_dir.delete(0, "end")
        self.rip_wav_dir.insert(0, output_dirs.get("wav", ""))
        quality = cfg.get("quality") or {}
        bitrate = cfg.get("bitrate") or {}
        if quality.get("flac"):
            self.rip_flac_quality.set(quality["flac"])
        if bitrate.get("mp3"):
            self.rip_mp3_bitrate.set(bitrate["mp3"])
        self.name_format_builder.set_format_string(cfg.get("name_format") or "%(track_number)2.2d - %(track_name)s")
        self.folder_format_builder.set_format_string(cfg.get("folder_format") or "%(album_name)s")
        self.rip_device.delete(0, "end")
        self.rip_device.insert(0, cfg.get("device") or "")
        if cfg.get("no_lookup"):
            self.no_lookup.select()
        else:
            self.no_lookup.deselect()
        if cfg.get("no_interactive"):
            self.no_interactive.select()
        else:
            self.no_interactive.deselect()
        if cfg.get("verify_accuraterip", True):
            self.verify_ar.select()
        else:
            self.verify_ar.deselect()

    def _on_export_settings(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export settings",
            defaultextension=".toml",
            filetypes=[("TOML files", "*.toml"), ("All files", "*.*")],
        )
        if path:
            try:
                from src.config import save_config

                save_config(path, self._get_config_from_ui())
                self._append_log(f"Exported settings to {path}\n", err=False)
            except Exception as e:
                self._append_log(f"Export failed: {e}\n", err=True)

    def _on_import_settings(self) -> None:
        path = filedialog.askopenfilename(
            title="Import settings",
            filetypes=[("TOML files", "*.toml"), ("All files", "*.*")],
        )
        if path:
            try:
                from src.config import load_config

                cfg = load_config(path)
                self._apply_config_to_ui(cfg)
                self._append_log(f"Imported settings from {path} (current settings overwritten).\n", err=False)
            except FileNotFoundError:
                self._append_log(f"File not found: {path}\n", err=True)
            except Exception as e:
                self._append_log(f"Import failed: {e}\n", err=True)

    def _get_rip_options(
        self,
    ) -> tuple[
        str,
        list[str],
        dict[str, str],
        str,
        str,
        bool,
        bool,
        bool,
        dict[str, str],
        dict[str, str],
    ]:
        device = self.rip_device.get().strip() or None
        formats: list[str] = []
        if self.rip_flac_enable.get():
            formats.append("flac")
        if self.rip_mp3_enable.get():
            formats.append("mp3")
        if self.rip_wav_enable.get():
            formats.append("wav")
        if not formats:
            formats = ["flac"]

        def dir_for(fmt: str) -> str:
            path = ""
            if fmt == "flac":
                path = self.rip_flac_dir.get().strip()
            elif fmt == "mp3":
                path = self.rip_mp3_dir.get().strip()
            elif fmt == "wav":
                path = self.rip_wav_dir.get().strip()
            return path or "."

        format_to_dir = {f: dir_for(f) for f in formats}

        name_fmt = self.name_format_builder.get_format_string().strip() or "%(track_number)2.2d - %(track_name)s"
        folder_fmt = self.folder_format_builder.get_format_string().strip() or "%(album_name)s"

        quality_map: dict[str, str] = {}
        bitrate_map: dict[str, str] = {}
        if "flac" in formats:
            quality_map["flac"] = self.rip_flac_quality.get()
        if "mp3" in formats:
            bitrate_map["mp3"] = self.rip_mp3_bitrate.get()

        return (
            device or "",
            formats,
            format_to_dir,
            name_fmt,
            folder_fmt,
            self.no_lookup.get(),
            self.no_interactive.get(),
            self.verify_ar.get(),
            quality_map,
            bitrate_map,
        )

    def _on_list_cd(self) -> None:
        if self._list_thread and self._list_thread.is_alive():
            return
        device = self.list_device.get().strip() or None
        self.list_text.configure(state="normal")
        self.list_text.delete("1.0", "end")
        self.list_text.insert("end", "Listing…\n")
        self.list_text.configure(state="disabled")
        self.list_go_btn.configure(state="disabled")
        self._list_queue = queue.Queue()
        self._list_thread = threading.Thread(
            target=_run_list_worker,
            args=(device, self._list_queue),
            daemon=True,
        )
        self._list_thread.start()

    def _poll_list_queue(self) -> None:
        try:
            while True:
                item = self._list_queue.get_nowait()
                if item == (None, None):
                    self.list_go_btn.configure(state="normal")
                    break
                lines, err = item
                self.list_text.configure(state="normal")
                self.list_text.delete("1.0", "end")
                if err:
                    self.list_text.insert("end", f"Error: {err}\n")
                elif lines:
                    self.list_text.insert("end", "\n".join(lines) + "\n")
                self.list_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self._poll_list_queue)

    def _on_rip(self) -> None:
        if self._rip_thread and self._rip_thread.is_alive():
            return
        (
            device,
            formats,
            format_to_dir,
            name_format,
            folder_format,
            no_lookup,
            no_interactive,
            verify_ar,
            quality_map,
            bitrate_map,
        ) = self._get_rip_options()

        from src.bitrates import is_bitrate_supported, format_supported_list

        for fmt, val in list(quality_map.items()) + list(bitrate_map.items()):
            if not is_bitrate_supported(fmt, val):
                supported = format_supported_list(fmt)
                self._append_log(f"Unsupported bitrate '{val}' for {fmt}. Supported: {supported}\n", err=True)
                return
        if not formats:
            self._append_log("Select at least one format (FLAC, MP3, or WAV).\n", err=True)
            return

        self.rip_log.delete("1.0", "end")
        self.rip_go_btn.configure(state="disabled")
        self._log_queue = queue.Queue()
        self._rip_thread = threading.Thread(
            target=_run_rip_worker,
            args=(
                device,
                formats,
                format_to_dir,
                name_format,
                folder_format,
                no_lookup,
                no_interactive,
                verify_ar,
                quality_map,
                bitrate_map,
                self._log_queue,
            ),
            daemon=True,
        )
        self._rip_thread.start()

    def _append_log(self, text: str, err: bool = False) -> None:
        self.rip_log.insert("end", text)
        self.rip_log.see("end")

    def _poll_log_queue(self) -> None:
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg is None:
                    self.rip_go_btn.configure(state="normal")
                    break
                self._append_log(msg + "\n", err=msg.startswith("Error"))
        except queue.Empty:
            pass
        self.after(150, self._poll_log_queue)

    def run(self) -> None:
        self.mainloop()


def main() -> None:
    app = RippingApp()
    app.run()


if __name__ == "__main__":
    main()
