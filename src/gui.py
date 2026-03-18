"""Desktop GUI for CD ripping (CustomTkinter, cross-platform)."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
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
        ctk.CTkLabel(
            self,
            text="Choose a token for each position; add or remove slots as needed.",
        ).pack(anchor="w", pady=(8, 2))

        self._container_frame = ctk.CTkFrame(
            self, fg_color=("gray90", "gray20"), corner_radius=6
        )
        self._container_frame.pack(fill="x", pady=(0, 4))

        self._preview_label = ctk.CTkLabel(
            self, text="", anchor="w", text_color=("gray40", "gray60")
        )
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
                inner,
                text="×",
                width=28,
                height=28,
                fg_color="transparent",
                command=lambda idx=i: self._remove_at(idx),
            )
            remove_btn.pack(side="left", padx=(0, 6), pady=2)
            self._slot_widgets.append((menu, remove_btn))

        add_btn = ctk.CTkButton(
            inner,
            text="+ Add",
            width=70,
            height=28,
            fg_color=("gray70", "gray35"),
            command=self._add_slot,
        )
        add_btn.pack(side="left", padx=(4, 0), pady=2)

        self._preview_label.configure(
            text=f"Result: {self.get_format_string() or '(empty)'}"
        )

    def _on_slot_change(self, index: int, chosen_label: str) -> None:
        if (
            0 <= index < len(self._sequence)
            and chosen_label in self._label_to_tid_value
        ):
            tid, value = self._label_to_tid_value[chosen_label]
            self._sequence[index] = (tid, value)
            self._preview_label.configure(
                text=f"Result: {self.get_format_string() or '(empty)'}"
            )

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
                    remaining = remaining[len(value) :]
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
                        remaining = remaining[idx + len(value) :]
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


def _run_edit_worker(
    input_paths: list[str],
    settings: Any,
    log_queue: queue.Queue[tuple[str, bool] | None],
) -> None:
    """Edit files in background; send log entries to log_queue."""

    try:
        from src.audio_edit import run_batch_edit

        def log_cb(msg: str, err: bool) -> None:
            log_queue.put((msg, err))

        run_batch_edit(input_paths, settings, log_callback=log_cb)
        log_queue.put(("Edit batch complete.", False))
        log_queue.put(None)
    except Exception as e:
        log_queue.put((f"Edit failed: {e}", True))
        log_queue.put(None)


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
        self._list_queue: queue.Queue[tuple[list[str] | None, str | None]] = (
            queue.Queue()
        )
        self._edit_thread: threading.Thread | None = None
        self._edit_queue: queue.Queue[tuple[str, bool] | None] = queue.Queue()
        self._edit_files: list[Path] = []

        self._build_ui()
        self._poll_log_queue()
        self._poll_list_queue()
        self._poll_edit_queue()

    def _build_ui(self) -> None:
        from src.cd import get_default_device

        default_device = get_default_device()

        # Notebook-style: two tabs
        self.tabview = ctk.CTkTabview(self, width=780)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabview.add("List CD")
        self.tabview.add("Rip CD")
        self.tabview.add("Edit")

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
        self.list_btn = ctk.CTkButton(
            list_dev_frame, text="Browse…", width=80, command=self._browse_cue_list
        )
        self.list_btn.pack(side="left", padx=(0, 8))
        self.list_go_btn = ctk.CTkButton(
            list_dev_frame, text="List tracks", command=self._on_list_cd
        )
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
        self.rip_browse_btn = ctk.CTkButton(
            rip_dev_frame, text="Browse…", width=80, command=self._browse_cue_rip
        )
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
        self.rip_flac_dir = ctk.CTkEntry(
            flac_dir_frame, placeholder_text="(current directory if empty)"
        )
        self.rip_flac_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            flac_dir_frame,
            text="Browse…",
            width=80,
            command=lambda: self._browse_output_dir("flac"),
        ).pack(side="left")
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
        self.rip_mp3_dir = ctk.CTkEntry(
            mp3_dir_frame, placeholder_text="(current directory if empty)"
        )
        self.rip_mp3_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            mp3_dir_frame,
            text="Browse…",
            width=80,
            command=lambda: self._browse_output_dir("mp3"),
        ).pack(side="left")
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
        self.rip_wav_dir = ctk.CTkEntry(
            wav_dir_frame, placeholder_text="(current directory if empty)"
        )
        self.rip_wav_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            wav_dir_frame,
            text="Browse…",
            width=80,
            command=lambda: self._browse_output_dir("wav"),
        ).pack(side="left")

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
        self.no_interactive = ctk.CTkCheckBox(
            opt_frame, text="Use first metadata match (no prompt)"
        )
        self.no_interactive.pack(side="left", padx=(0, 16))
        self.no_interactive.select()
        self.verify_ar = ctk.CTkCheckBox(opt_frame, text="Show AccurateRip status")
        self.verify_ar.pack(side="left")
        self.verify_ar.select()

        config_btn_frame = ctk.CTkFrame(rip_scroll, fg_color="transparent")
        config_btn_frame.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            config_btn_frame,
            text="Export settings…",
            width=120,
            command=self._on_export_settings,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            config_btn_frame,
            text="Import settings…",
            width=120,
            command=self._on_import_settings,
        ).pack(side="left")

        self.rip_go_btn = ctk.CTkButton(
            rip_scroll,
            text="Start rip",
            command=self._on_rip,
            fg_color="green",
            hover_color="darkgreen",
        )
        self.rip_go_btn.pack(anchor="w", pady=(12, 8))

        ctk.CTkLabel(rip_scroll, text="Log:").pack(anchor="w")
        self.rip_log = ctk.CTkTextbox(rip_scroll, height=200, state="normal")
        self.rip_log.pack(fill="both", expand=True, pady=(4, 0))

        # --- Edit tab ---
        edit_tab = self.tabview.tab("Edit")
        self._build_edit_tab(edit_tab)

    def _build_edit_tab(self, edit_tab: Any) -> None:
        """Build the batch audio editing UI."""

        from src.audio_edit import available_export_formats

        edit_scroll = ctk.CTkScrollableFrame(edit_tab, fg_color="transparent")
        edit_scroll.pack(fill="both", expand=True)

        def make_entry(
            parent: Any,
            label: str,
            placeholder: str = "",
            default: str = "",
        ) -> ctk.CTkEntry:
            ctk.CTkLabel(parent, text=label).pack(anchor="w")
            entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
            if default:
                entry.insert(0, default)
            entry.pack(fill="x", pady=(0, 4))
            return entry

        ctk.CTkLabel(edit_scroll, text="Files to edit:").pack(anchor="w")
        file_btn_frame = ctk.CTkFrame(edit_scroll, fg_color="transparent")
        file_btn_frame.pack(fill="x", pady=(0, 4))
        ctk.CTkButton(
            file_btn_frame,
            text="Add files…",
            width=100,
            command=self._browse_edit_files,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            file_btn_frame,
            text="Add folder…",
            width=100,
            command=self._browse_edit_folder,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            file_btn_frame,
            text="Clear",
            width=80,
            command=self._clear_edit_files,
        ).pack(side="left")
        self.edit_files_text = ctk.CTkTextbox(edit_scroll, height=100, state="disabled")
        self.edit_files_text.pack(fill="both", expand=False, pady=(0, 8))

        ctk.CTkLabel(edit_scroll, text="Export settings:").pack(anchor="w")
        export_frame = ctk.CTkFrame(edit_scroll, fg_color="transparent")
        export_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(export_frame, text="Output directory:").pack(anchor="w")
        output_dir_row = ctk.CTkFrame(export_frame, fg_color="transparent")
        output_dir_row.pack(fill="x", pady=(0, 4))
        self.edit_output_dir = ctk.CTkEntry(
            output_dir_row,
            placeholder_text="(same as source folder if empty)",
        )
        self.edit_output_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            output_dir_row,
            text="Browse…",
            width=80,
            command=self._browse_edit_output_dir,
        ).pack(side="left")

        ctk.CTkLabel(export_frame, text="Output format:").pack(anchor="w")
        format_row = ctk.CTkFrame(export_frame, fg_color="transparent")
        format_row.pack(fill="x", pady=(0, 4))
        self.edit_output_format = ctk.CTkOptionMenu(
            format_row,
            values=list(available_export_formats()),
        )
        self.edit_output_format.set("mp3")
        self.edit_output_format.pack(side="left", padx=(0, 8))

        self.edit_filename_suffix = make_entry(
            export_frame,
            "Filename suffix:",
            placeholder="_edited",
            default="_edited",
        )
        self.edit_bitrate = make_entry(
            export_frame,
            "Bitrate (for compressed export):",
            placeholder="192k",
            default="192k",
        )

        ctk.CTkLabel(edit_scroll, text="Core edits:").pack(anchor="w")
        core_frame = ctk.CTkFrame(edit_scroll, fg_color="transparent")
        core_frame.pack(fill="x", pady=(0, 8))

        self.edit_gain_db = make_entry(
            core_frame,
            "Gain (dB):",
            placeholder="blank = no gain",
        )
        self.edit_pan = make_entry(
            core_frame,
            "Pan (-1.0 to 1.0):",
            placeholder="blank = no pan",
        )
        self.edit_channels = ctk.CTkOptionMenu(
            core_frame,
            values=["Auto", "Mono", "Stereo"],
        )
        self.edit_channels.set("Auto")
        self.edit_channels.pack(anchor="w", pady=(0, 4))
        self.edit_sample_width = ctk.CTkOptionMenu(
            core_frame,
            values=["Auto", "1", "2", "4"],
        )
        self.edit_sample_width.set("Auto")
        self.edit_sample_width.pack(anchor="w", pady=(0, 4))
        self.edit_frame_rate = make_entry(
            core_frame,
            "Frame rate (Hz):",
            placeholder="blank = no change",
        )
        self.edit_normalize = ctk.CTkCheckBox(core_frame, text="Normalize peak volume")
        self.edit_normalize.pack(anchor="w", pady=(0, 2))
        self.edit_remove_dc = ctk.CTkCheckBox(core_frame, text="Remove DC offset")
        self.edit_remove_dc.pack(anchor="w", pady=(0, 2))
        self.edit_reverse = ctk.CTkCheckBox(core_frame, text="Reverse playback")
        self.edit_reverse.pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(edit_scroll, text="Trim and fade:").pack(anchor="w")
        trim_frame = ctk.CTkFrame(edit_scroll, fg_color="transparent")
        trim_frame.pack(fill="x", pady=(0, 8))
        self.edit_trim_start_ms = make_entry(
            trim_frame,
            "Trim from start (ms):",
            placeholder="0",
            default="0",
        )
        self.edit_trim_end_ms = make_entry(
            trim_frame,
            "Trim from end (ms):",
            placeholder="0",
            default="0",
        )
        self.edit_trim_silence = ctk.CTkCheckBox(
            trim_frame,
            text="Trim leading and trailing silence",
        )
        self.edit_trim_silence.pack(anchor="w", pady=(0, 2))
        self.edit_silence_thresh = make_entry(
            trim_frame,
            "Silence threshold (dBFS):",
            placeholder="-50",
            default="-50",
        )
        self.edit_silence_chunk = make_entry(
            trim_frame,
            "Silence chunk size (ms):",
            placeholder="10",
            default="10",
        )
        self.edit_fade_in_ms = make_entry(
            trim_frame,
            "Fade in (ms):",
            placeholder="0",
            default="0",
        )
        self.edit_fade_out_ms = make_entry(
            trim_frame,
            "Fade out (ms):",
            placeholder="0",
            default="0",
        )

        ctk.CTkLabel(edit_scroll, text="Composition:").pack(anchor="w")
        comp_frame = ctk.CTkFrame(edit_scroll, fg_color="transparent")
        comp_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(comp_frame, text="Append file:").pack(anchor="w")
        append_row = ctk.CTkFrame(comp_frame, fg_color="transparent")
        append_row.pack(fill="x", pady=(0, 4))
        self.edit_append_path = ctk.CTkEntry(
            append_row,
            placeholder_text="Optional companion file to append",
        )
        self.edit_append_path.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            append_row,
            text="Browse…",
            width=80,
            command=self._browse_edit_append_file,
        ).pack(side="left")
        self.edit_append_crossfade_ms = make_entry(
            comp_frame,
            "Append crossfade (ms):",
            placeholder="0",
            default="0",
        )

        ctk.CTkLabel(comp_frame, text="Overlay file:").pack(anchor="w")
        overlay_row = ctk.CTkFrame(comp_frame, fg_color="transparent")
        overlay_row.pack(fill="x", pady=(0, 4))
        self.edit_overlay_path = ctk.CTkEntry(
            overlay_row,
            placeholder_text="Optional companion file to overlay",
        )
        self.edit_overlay_path.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            overlay_row,
            text="Browse…",
            width=80,
            command=self._browse_edit_overlay_file,
        ).pack(side="left")
        self.edit_overlay_position_ms = make_entry(
            comp_frame,
            "Overlay position (ms):",
            placeholder="0",
            default="0",
        )
        self.edit_overlay_gain_db = make_entry(
            comp_frame,
            "Overlay gain during overlay (dB):",
            placeholder="0",
            default="0",
        )
        self.edit_overlay_loop = ctk.CTkCheckBox(
            comp_frame, text="Loop overlay until the source ends"
        )
        self.edit_overlay_loop.pack(anchor="w", pady=(0, 2))
        self.edit_overlay_times = make_entry(
            comp_frame,
            "Overlay times:",
            placeholder="1",
            default="1",
        )

        self.edit_go_btn = ctk.CTkButton(
            edit_scroll,
            text="Start edit batch",
            command=self._on_edit,
            fg_color="green",
            hover_color="darkgreen",
        )
        self.edit_go_btn.pack(anchor="w", pady=(12, 8))

        ctk.CTkLabel(edit_scroll, text="Log:").pack(anchor="w")
        self.edit_log = ctk.CTkTextbox(edit_scroll, height=200, state="normal")
        self.edit_log.pack(fill="both", expand=True, pady=(4, 0))
        self._refresh_edit_files_text()

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

    def _set_entry_text(self, entry: Any, value: str) -> None:
        """Replace the text in a CTkEntry widget."""

        entry.delete(0, "end")
        entry.insert(0, value)

    def _normalize_edit_path(self, path: str | Path) -> Path:
        """Return a normalized path for edit-file deduplication."""

        return Path(path).expanduser().resolve(strict=False)

    def _refresh_edit_files_text(self) -> None:
        """Refresh the selected-file display."""

        self.edit_files_text.configure(state="normal")
        self.edit_files_text.delete("1.0", "end")
        if self._edit_files:
            self.edit_files_text.insert(
                "end",
                "\n".join(str(path) for path in self._edit_files) + "\n",
            )
        else:
            self.edit_files_text.insert("end", "(no files selected)\n")
        self.edit_files_text.configure(state="disabled")

    def _add_edit_files(self, paths: list[str | Path]) -> None:
        """Add audio files to the current edit selection."""

        existing = {str(path).lower() for path in self._edit_files}
        for path in paths:
            normalized = self._normalize_edit_path(path)
            key = str(normalized).lower()
            if key not in existing:
                self._edit_files.append(normalized)
                existing.add(key)
        self._refresh_edit_files_text()

    def _clear_edit_files(self) -> None:
        """Clear the selected edit files."""

        self._edit_files.clear()
        self._refresh_edit_files_text()

    def _browse_edit_files(self) -> None:
        """Browse for one or more audio files to edit."""

        paths = filedialog.askopenfilenames(
            title="Select audio files",
            filetypes=[
                (
                    "Audio files",
                    "*.aac *.aif *.aiff *.flac *.m4a *.mp3 *.mp4 *.ogg *.opus *.wav *.wma *.webm",
                ),
                ("All files", "*.*"),
            ],
        )
        if paths:
            self._add_edit_files(list(paths))

    def _browse_edit_folder(self) -> None:
        """Browse for a folder and add supported audio files from it."""

        path = filedialog.askdirectory(title="Select folder of audio files")
        if not path:
            return
        try:
            from src.audio_edit import discover_audio_files

            files = discover_audio_files(path)
            if files:
                self._add_edit_files(files)
            else:
                self._append_edit_log(
                    f"Edit folder scan: no audio files found in {path}\n", err=True
                )
        except Exception as exc:
            self._append_edit_log(f"Edit folder scan failed: {exc}\n", err=True)

    def _browse_edit_output_dir(self) -> None:
        """Browse for the edit output directory."""

        path = filedialog.askdirectory(title="Select edit output directory")
        if path:
            self._set_entry_text(self.edit_output_dir, path)

    def _browse_edit_append_file(self) -> None:
        """Browse for a companion file to append."""

        path = filedialog.askopenfilename(
            title="Select file to append",
            filetypes=[
                (
                    "Audio files",
                    "*.aac *.aif *.aiff *.flac *.m4a *.mp3 *.mp4 *.ogg *.opus *.wav *.wma *.webm",
                ),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._set_entry_text(self.edit_append_path, path)

    def _browse_edit_overlay_file(self) -> None:
        """Browse for a companion file to overlay."""

        path = filedialog.askopenfilename(
            title="Select file to overlay",
            filetypes=[
                (
                    "Audio files",
                    "*.aac *.aif *.aiff *.flac *.m4a *.mp3 *.mp4 *.ogg *.opus *.wav *.wma *.webm",
                ),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._set_entry_text(self.edit_overlay_path, path)

    def _get_edit_options(self) -> Any:
        """Build AudioEditSettings from the edit tab widgets."""

        from src.audio_edit import AudioEditSettings

        def parse_int(entry: Any, label: str, default: int | None = None) -> int | None:
            text = entry.get().strip()
            if not text:
                return default
            try:
                return int(text)
            except ValueError as exc:
                raise ValueError(f"{label} must be an integer.") from exc

        def parse_float(
            entry: Any,
            label: str,
            default: float | None = None,
        ) -> float | None:
            text = entry.get().strip()
            if not text:
                return default
            try:
                return float(text)
            except ValueError as exc:
                raise ValueError(f"{label} must be a number.") from exc

        output_dir_text = self.edit_output_dir.get().strip()
        output_dir = Path(output_dir_text) if output_dir_text else None
        output_format = self.edit_output_format.get().strip().lower()
        suffix = self.edit_filename_suffix.get().strip()
        bitrate = self.edit_bitrate.get().strip() or None

        channels_choice = self.edit_channels.get()
        channels = None
        if channels_choice == "Mono":
            channels = 1
        elif channels_choice == "Stereo":
            channels = 2

        sample_width_choice = self.edit_sample_width.get()
        sample_width = None
        if sample_width_choice != "Auto":
            sample_width = int(sample_width_choice)

        append_path_text = self.edit_append_path.get().strip()
        overlay_path_text = self.edit_overlay_path.get().strip()

        return AudioEditSettings(
            output_dir=output_dir,
            output_format=output_format,
            filename_suffix=suffix,
            bitrate=bitrate,
            append_path=Path(append_path_text) if append_path_text else None,
            append_crossfade_ms=parse_int(
                self.edit_append_crossfade_ms,
                "Append crossfade",
                0,
            )
            or 0,
            overlay_path=Path(overlay_path_text) if overlay_path_text else None,
            overlay_position_ms=parse_int(
                self.edit_overlay_position_ms,
                "Overlay position",
                0,
            )
            or 0,
            overlay_gain_during_overlay_db=parse_float(
                self.edit_overlay_gain_db,
                "Overlay gain during overlay",
                0.0,
            )
            or 0.0,
            overlay_loop=self.edit_overlay_loop.get(),
            overlay_times=parse_int(self.edit_overlay_times, "Overlay times", 1) or 1,
            sample_width=sample_width,
            frame_rate=parse_int(self.edit_frame_rate, "Frame rate", None),
            channels=channels,
            normalize_audio=self.edit_normalize.get(),
            gain_db=parse_float(self.edit_gain_db, "Gain", None),
            pan=parse_float(self.edit_pan, "Pan", None),
            remove_dc_offset=self.edit_remove_dc.get(),
            trim_start_ms=parse_int(self.edit_trim_start_ms, "Trim from start", 0) or 0,
            trim_end_ms=parse_int(self.edit_trim_end_ms, "Trim from end", 0) or 0,
            trim_silence=self.edit_trim_silence.get(),
            silence_thresh=parse_float(
                self.edit_silence_thresh,
                "Silence threshold",
                -50.0,
            )
            or -50.0,
            silence_chunk_size=parse_int(
                self.edit_silence_chunk,
                "Silence chunk size",
                10,
            )
            or 10,
            reverse=self.edit_reverse.get(),
            fade_in_ms=parse_int(self.edit_fade_in_ms, "Fade in", 0) or 0,
            fade_out_ms=parse_int(self.edit_fade_out_ms, "Fade out", 0) or 0,
        )

    def _on_edit(self) -> None:
        """Start the background batch-edit job."""

        if self._edit_thread and self._edit_thread.is_alive():
            return
        try:
            settings = self._get_edit_options()
            from src.audio_edit import (
                build_operation_summary,
                describe_ffmpeg_requirement,
                edit_requires_ffmpeg,
                ffmpeg_available,
                validate_edit_settings,
            )

            validate_edit_settings(settings)
            summary = ", ".join(build_operation_summary(settings))
            if not self._edit_files:
                raise ValueError("Select at least one audio file.")
            if (
                edit_requires_ffmpeg(self._edit_files, settings)
                and not ffmpeg_available()
            ):
                raise RuntimeError(
                    describe_ffmpeg_requirement(self._edit_files, settings)
                    + (
                        " Install ffmpeg/ffprobe or use a build that includes "
                        "them, then restart the app."
                    )
                )
        except Exception as exc:
            self._append_edit_log(f"Edit setup error: {exc}\n", err=True)
            return

        self.edit_log.delete("1.0", "end")
        self._append_edit_log(f"Starting edit batch: {summary}\n", err=False)
        self.edit_go_btn.configure(state="disabled")
        self._edit_queue = queue.Queue()
        self._edit_thread = threading.Thread(
            target=_run_edit_worker,
            args=(
                [str(path) for path in self._edit_files],
                settings,
                self._edit_queue,
            ),
            daemon=True,
        )
        self._edit_thread.start()

    def _append_edit_log(self, text: str, err: bool = False) -> None:
        """Append a message to the edit log."""

        self.edit_log.insert("end", text)
        self.edit_log.see("end")

    def _poll_edit_queue(self) -> None:
        """Drain the edit queue and update the UI."""

        try:
            while True:
                item = self._edit_queue.get_nowait()
                if item is None:
                    self.edit_go_btn.configure(state="normal")
                    break
                msg, err = item
                self._append_edit_log(msg + "\n", err=err)
        except queue.Empty:
            pass
        self.after(150, self._poll_edit_queue)

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
        name_fmt = (
            self.name_format_builder.get_format_string().strip()
            or "%(track_number)2.2d - %(track_name)s"
        )
        folder_fmt = (
            self.folder_format_builder.get_format_string().strip() or "%(album_name)s"
        )
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
        self.name_format_builder.set_format_string(
            cfg.get("name_format") or "%(track_number)2.2d - %(track_name)s"
        )
        self.folder_format_builder.set_format_string(
            cfg.get("folder_format") or "%(album_name)s"
        )
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
                self._append_log(
                    f"Imported settings from {path} (current settings overwritten).\n",
                    err=False,
                )
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

        name_fmt = (
            self.name_format_builder.get_format_string().strip()
            or "%(track_number)2.2d - %(track_name)s"
        )
        folder_fmt = (
            self.folder_format_builder.get_format_string().strip() or "%(album_name)s"
        )

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
                self._append_log(
                    f"Unsupported bitrate '{val}' for {fmt}. Supported: {supported}\n",
                    err=True,
                )
                return
        if not formats:
            self._append_log(
                "Select at least one format (FLAC, MP3, or WAV).\n", err=True
            )
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
