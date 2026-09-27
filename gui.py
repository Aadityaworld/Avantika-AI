"""Modern dark-themed CustomTkinter GUI with Tabbed Chat & Workspace Dashboard."""

import datetime
import os
import queue
import tkinter as tk
from typing import Callable, Dict, Optional

import customtkinter as ctk
import psutil

from db import TaskDatabase

# ── Global theme ──────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Palette ───────────────────────────────────────────────────────────────────
_BG_MAIN       = "#0f172a"
_BG_CARD       = "#1e293b"
_BG_USER       = "#1d4ed8"
_BG_ASSIST     = "#1e293b"
_BG_SYS        = "#0f172a"
_BG_HEADER     = "#0d1526"
_BG_INPUT_BAR  = "#0d1526"
_BG_CHIP       = "#1e293b"
_CHIP_HOVER    = "#334155"
_ACCENT_BLUE   = "#3b82f6"
_TEXT_PRIMARY  = "#f1f5f9"
_TEXT_MUTED    = "#64748b"
_TEXT_SYS      = "#475569"
_BADGE_IDLE    = ("#1e3a5f", "#93c5fd")   # (bg, fg)
_BADGE_LISTEN  = ("#14532d", "#4ade80")
_BADGE_THINK   = ("#713f12", "#fcd34d")
_BADGE_SPEAK   = ("#312e81", "#a5b4fc")
_BADGE_ERROR   = ("#7f1d1d", "#fca5a5")
_BADGE_OFFLINE = ("#44403c", "#a8a29e")

_CATEGORY_COLORS = {
    "Dev":      ("#1e3a8a", "#93c5fd"),
    "Work":     ("#14532d", "#4ade80"),
    "Research": ("#581c87", "#c084fc"),
    "Personal": ("#78350f", "#fde047"),
    "General":  ("#334155", "#cbd5e1"),
}

_STATUS_MAP = {
    "listening":    ("● Listening...",  _BADGE_LISTEN),
    "processing":   ("⚡ Thinking...",   _BADGE_THINK),
    "thinking":     ("⚡ Thinking...",   _BADGE_THINK),
    "speaking":     ("🔊 Speaking...",   _BADGE_SPEAK),
    "disconnected": ("⚠ Disconnected",  _BADGE_ERROR),
    "offline":      ("⚠ Offline",       _BADGE_OFFLINE),
    "error":        ("⚠ Error",         _BADGE_ERROR),
    "reconnecting": ("⟳ Reconnecting",  _BADGE_ERROR),
    "deterministic":("◎ Offline Mode",  _BADGE_OFFLINE),
}


def _resolve_status(text: str) -> tuple[str, tuple[str, str]]:
    """Map raw status text to display label + (bg, fg) badge colours."""
    lower = text.lower()
    for key, val in _STATUS_MAP.items():
        if key in lower:
            return val
    return f"● {text}", _BADGE_IDLE


class AssistantGUI:
    """Sleek, responsive AI assistant with chat, tasks dashboard, and telemetry."""

    def __init__(
        self,
        event_queue: queue.Queue,
        on_send_callback: Callable[[str], None],
        on_speak_callback: Callable[[], None],
    ) -> None:
        self.queue = event_queue
        self._on_send = on_send_callback
        self._on_speak = on_speak_callback

        # SQLite Database for tasks
        self.db = TaskDatabase()

        # Settings state
        self._settings_open: bool = False
        self._speech_rate: float = 175.0
        self._speech_volume: float = 0.9

        self.root = ctk.CTk()
        self.root.title("Avantika — Local AI Desktop Companion")
        self.root.geometry("880x720")
        self.root.minsize(680, 540)
        self.root.configure(fg_color=_BG_MAIN)

        # Attach window / taskbar icon safely
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
            if os.path.isfile(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        self._build_layout()
        self._refresh_task_list()

        # Rehydrate recent chat history
        recent_messages = self.db.get_recent_messages(limit=30)
        for msg in recent_messages:
            # Map database roles to GUI display names
            display_role = "Avantika" if msg["role"].lower() in ("assistant", "system") else "You"
            if msg["role"].lower() == "system":
                display_role = "System"
            self.append_message(display_role, msg["content"], persist=False)

        # Barge-in / Interrupt Binding
        self.root.bind("<Escape>", lambda e: self._handle_escape_stop())

        self.root.after(100, self.process_queue)
        self.root.after(500, self._update_telemetry)

    def _handle_escape_stop(self) -> None:
        """Instantly halt TTS playback and reset UI."""
        import audio
        audio.stop_playback()
        self.update_status("■ Stopped")
        self._update_audio_meter(0.0)

    # ── Layout Construction ───────────────────────────────────────────────────

    def _build_layout(self) -> None:
        """Compose header, tabview (Chat & Workspace), and overlay settings drawer."""
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self._build_header(row=0)
        self._build_tabview(row=1)
        self._build_settings_drawer()

    def _build_header(self, row: int) -> None:
        hf = ctk.CTkFrame(self.root, fg_color=_BG_HEADER, corner_radius=0)
        hf.grid(row=row, column=0, sticky="ew", padx=0, pady=0)
        hf.grid_columnconfigure(0, weight=1)

        # ── Top strip (title + badges + settings button) ──
        top_strip = ctk.CTkFrame(hf, fg_color="transparent", height=48)
        top_strip.pack(fill=tk.X)
        top_strip.grid_columnconfigure(0, weight=1)
        top_strip.grid_propagate(False)

        title_frame = ctk.CTkFrame(top_strip, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w", padx=16, pady=6)
        
        ctk.CTkLabel(
            title_frame,
            text="AVANTIKA",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold", letter_spacing=2),
            text_color=_TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w", pady=(0, 0))
        
        ctk.CTkLabel(
            title_frame,
            text="Local Workspace Intelligence",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(0, 0))

        right = ctk.CTkFrame(top_strip, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=12, pady=8)

        ctk.CTkLabel(
            right,
            text="🔒 Local & Offline",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#14532d",
            text_color="#4ade80",
            corner_radius=10,
            padx=10,
            pady=3,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self._status_pill = ctk.CTkLabel(
            right,
            text="● Idle",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=_BADGE_IDLE[0],
            text_color=_BADGE_IDLE[1],
            corner_radius=10,
            padx=12,
            pady=3,
        )
        self._status_pill.pack(side=tk.LEFT, padx=(0, 8))

        # Settings gear toggle
        self._settings_btn = ctk.CTkButton(
            right,
            text="⚙",
            width=32,
            height=28,
            corner_radius=8,
            font=ctk.CTkFont(size=14),
            fg_color="#1e293b",
            hover_color="#334155",
            command=self._toggle_settings,
        )
        self._settings_btn.pack(side=tk.LEFT)

        # ── Audio level meter (thin canvas bar under header) ──
        self._meter_canvas = tk.Canvas(
            hf,
            height=3,
            bg=_BG_HEADER,
            highlightthickness=0,
        )
        self._meter_canvas.pack(fill=tk.X)
        self._meter_bar = self._meter_canvas.create_rectangle(0, 0, 0, 3, fill="#3b82f6", width=0)
        self._meter_level: float = 0.0

    def _build_tabview(self, row: int) -> None:
        """Create tabview separating Assistant Chat from Workspace Dashboard."""
        self.tabview = ctk.CTkTabview(
            self.root,
            corner_radius=8,
            fg_color=_BG_MAIN,
            segmented_button_fg_color="#0d1526",
            segmented_button_selected_color="#1d4ed8",
            segmented_button_selected_hover_color="#2563eb",
            segmented_button_unselected_color="#1e293b",
            segmented_button_unselected_hover_color="#334155",
        )
        self.tabview.grid(row=row, column=0, sticky="nsew", padx=10, pady=(4, 8))

        # Add tabs
        self.tab_chat = self.tabview.add("💬 Assistant Chat")
        self.tab_workspace = self.tabview.add("📊 Workspace & Tasks")

        # Build Chat Tab content
        self._build_chat_tab()

        # Build Workspace Tab content
        self._build_workspace_tab()

    def _build_chat_tab(self) -> None:
        """Construct the chat canvas, quick actions, and input bar inside Chat Tab."""
        self.tab_chat.grid_columnconfigure(0, weight=1)
        self.tab_chat.grid_rowconfigure(0, weight=1)

        # Chat scrollable frame
        self._chat_frame = ctk.CTkScrollableFrame(
            self.tab_chat,
            fg_color=_BG_MAIN,
            corner_radius=6,
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569",
        )
        self._chat_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=(2, 4))
        self._chat_frame.grid_columnconfigure(0, weight=1)

        # Quick actions dock
        self._build_quick_dock(parent=self.tab_chat, row=1)

        # Input dock
        self._build_input_dock(parent=self.tab_chat, row=2)

    def _build_quick_dock(self, parent: ctk.CTkFrame, row: int) -> None:
        dock = ctk.CTkFrame(parent, fg_color=_BG_HEADER, corner_radius=6, height=44)
        dock.grid(row=row, column=0, sticky="ew", padx=4, pady=(2, 4))
        dock.grid_propagate(False)

        chips = [
            ("🕒 Time",       "What time is it right now?"),
            ("😂 Joke",       "Tell me a programming joke"),
            ("🔍 Who is...",  None),
            ("🎵 Play...",    None),
        ]

        inner = ctk.CTkFrame(dock, fg_color="transparent")
        inner.pack(side=tk.LEFT, padx=8, pady=6)

        for label, cmd in chips:
            if cmd:
                cb = lambda c=cmd: self._on_send(c)
            elif "Who" in label:
                cb = lambda: self._prefill("Who is ")
            else:
                cb = lambda: self._prefill("Play ")

            ctk.CTkButton(
                inner,
                text=label,
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color=_BG_CHIP,
                hover_color=_CHIP_HOVER,
                text_color="#cbd5e1",
                corner_radius=13,
                command=cb,
            ).pack(side=tk.LEFT, padx=3)

    def _build_input_dock(self, parent: ctk.CTkFrame, row: int) -> None:
        bar = ctk.CTkFrame(parent, fg_color=_BG_INPUT_BAR, corner_radius=6, height=58)
        bar.grid(row=row, column=0, sticky="ew", padx=4, pady=(2, 4))
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill=tk.X, padx=10, pady=9)
        inner.grid_columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(
            inner,
            placeholder_text="Ask anything or run a command...",
            font=ctk.CTkFont(size=13),
            height=36,
            corner_radius=18,
            fg_color="#1e293b",
            border_color="#334155",
            text_color=_TEXT_PRIMARY,
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry.bind("<Return>", lambda _e: self._handle_send())

        ctk.CTkButton(
            inner,
            text="Send",
            width=68,
            height=36,
            corner_radius=18,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=_ACCENT_BLUE,
            hover_color="#2563eb",
            command=self._handle_send,
        ).grid(row=0, column=1, padx=(0, 6))

        ctk.CTkButton(
            inner,
            text="🎤 Speak",
            width=84,
            height=36,
            corner_radius=18,
            font=ctk.CTkFont(size=12),
            fg_color="#15803d",
            hover_color="#166534",
            command=self._on_speak,
        ).grid(row=0, column=2)

    # ── Workspace & Task Dashboard Tab ────────────────────────────────────────

    def _build_workspace_tab(self) -> None:
        """Construct hardware resource gauges and SQLite task manager inside Workspace Tab."""
        self.tab_workspace.grid_columnconfigure(0, weight=1)
        self.tab_workspace.grid_rowconfigure(1, weight=1)

        # 1. Telemetry card
        telem_card = ctk.CTkFrame(self.tab_workspace, fg_color=_BG_CARD, corner_radius=8)
        telem_card.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 8))
        telem_card.grid_columnconfigure((0, 1), weight=1)

        # CPU Metric
        cpu_box = ctk.CTkFrame(telem_card, fg_color="transparent")
        cpu_box.grid(row=0, column=0, sticky="ew", padx=16, pady=12)

        self._cpu_label = ctk.CTkLabel(
            cpu_box,
            text="CPU Usage: 0.0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_TEXT_PRIMARY,
            anchor="w",
        )
        self._cpu_label.pack(fill=tk.X, pady=(0, 4))

        self._cpu_bar = ctk.CTkProgressBar(
            cpu_box,
            height=8,
            corner_radius=4,
            progress_color="#3b82f6",
            fg_color="#0f172a",
        )
        self._cpu_bar.set(0.0)
        self._cpu_bar.pack(fill=tk.X)

        # RAM Metric
        ram_box = ctk.CTkFrame(telem_card, fg_color="transparent")
        ram_box.grid(row=0, column=1, sticky="ew", padx=16, pady=12)

        self._ram_label = ctk.CTkLabel(
            ram_box,
            text="RAM Usage: 0.0% (0.0 GB / 0.0 GB)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_TEXT_PRIMARY,
            anchor="w",
        )
        self._ram_label.pack(fill=tk.X, pady=(0, 4))

        self._ram_bar = ctk.CTkProgressBar(
            ram_box,
            height=8,
            corner_radius=4,
            progress_color="#8b5cf6",
            fg_color="#0f172a",
        )
        self._ram_bar.set(0.0)
        self._ram_bar.pack(fill=tk.X)

        # 2. Task Management Container
        task_container = ctk.CTkFrame(self.tab_workspace, fg_color=_BG_CARD, corner_radius=8)
        task_container.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        task_container.grid_columnconfigure(0, weight=1)
        task_container.grid_rowconfigure(2, weight=1)

        # Top Task Summary Header
        task_hdr = ctk.CTkFrame(task_container, fg_color="transparent")
        task_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))

        self._task_summary_lbl = ctk.CTkLabel(
            task_hdr,
            text="Active Tasks (0 total | 0 pending)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=_TEXT_PRIMARY,
        )
        self._task_summary_lbl.pack(side=tk.LEFT)

        ctk.CTkButton(
            task_hdr,
            text="⟳ Refresh",
            width=70,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._refresh_task_list,
        ).pack(side=tk.RIGHT)

        # Task Input Row
        input_row = ctk.CTkFrame(task_container, fg_color="transparent")
        input_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        input_row.grid_columnconfigure(0, weight=1)

        self._task_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Enter new task or goal...",
            font=ctk.CTkFont(size=12),
            height=32,
            fg_color="#0f172a",
            border_color="#334155",
            text_color=_TEXT_PRIMARY,
        )
        self._task_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._task_entry.bind("<Return>", lambda _e: self._handle_add_task())

        self._cat_menu = ctk.CTkOptionMenu(
            input_row,
            values=["General", "Work", "Dev", "Research", "Personal"],
            width=100,
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            button_color="#475569",
            button_hover_color="#64748b",
        )
        self._cat_menu.set("General")
        self._cat_menu.grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            input_row,
            text="+ Add Task",
            width=85,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1d4ed8",
            hover_color="#2563eb",
            command=self._handle_add_task,
        ).grid(row=0, column=2)

        # Task List Scrollable Canvas
        self._task_scroll = ctk.CTkScrollableFrame(
            task_container,
            fg_color="#0f172a",
            corner_radius=6,
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569",
        )
        self._task_scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self._task_scroll.grid_columnconfigure(0, weight=1)

    # ── Task Database Actions ─────────────────────────────────────────────────

    def _refresh_task_list(self) -> None:
        """Fetch tasks from SQLite and re-render list."""
        for widget in self._task_scroll.winfo_children():
            widget.destroy()

        tasks = self.db.get_all_tasks()
        pending = sum(1 for t in tasks if t.get("is_done") == 0)
        self._task_summary_lbl.configure(
            text=f"Active Tasks ({len(tasks)} total | {pending} pending)"
        )

        if not tasks:
            ctk.CTkLabel(
                self._task_scroll,
                text="No tasks yet. Add a new task above or ask the assistant!",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color=_TEXT_MUTED,
            ).pack(pady=20)
            return

        for task in tasks:
            self._render_task_item(task)

    def _render_task_item(self, task: Dict) -> None:
        """Render individual task card with status checkbox, category pill, and delete button."""
        task_id = task["id"]
        title = task["title"]
        category = task.get("category", "General")
        is_done = task.get("is_done", 0) == 1

        card = ctk.CTkFrame(
            self._task_scroll,
            fg_color="#1e293b" if not is_done else "#0f172a",
            corner_radius=6,
            border_width=1,
            border_color="#334155" if not is_done else "#1e293b",
        )
        card.pack(fill=tk.X, padx=4, pady=3)
        card.grid_columnconfigure(1, weight=1)

        # Checkbox
        chk_var = tk.BooleanVar(value=is_done)
        chk = ctk.CTkCheckBox(
            card,
            text="",
            variable=chk_var,
            width=20,
            checkbox_width=18,
            checkbox_height=18,
            command=lambda tid=task_id, cur=task.get("is_done", 0): self._handle_toggle_task(tid, cur),
        )
        chk.grid(row=0, column=0, padx=(10, 6), pady=8)

        # Title Label
        title_lbl = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=12, overstrike=is_done),
            text_color=_TEXT_PRIMARY if not is_done else _TEXT_MUTED,
            anchor="w",
            justify="left",
        )
        title_lbl.grid(row=0, column=1, sticky="w", padx=4, pady=8)

        # Category Pill
        cat_bg, cat_fg = _CATEGORY_COLORS.get(category, _CATEGORY_COLORS["General"])
        ctk.CTkLabel(
            card,
            text=category,
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=cat_bg,
            text_color=cat_fg,
            corner_radius=8,
            padx=8,
            pady=2,
        ).grid(row=0, column=2, padx=6, pady=8)

        # Delete Action Button
        ctk.CTkButton(
            card,
            text="✕",
            width=24,
            height=24,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=lambda tid=task_id: self._handle_delete_task(tid),
        ).grid(row=0, column=3, padx=(4, 10), pady=8)

    def _handle_add_task(self) -> None:
        """Add task from input row to database."""
        text = self._task_entry.get().strip()
        cat = self._cat_menu.get()
        if text:
            self.db.add_task(text, cat)
            self._task_entry.delete(0, tk.END)
            self._refresh_task_list()

    def _handle_toggle_task(self, task_id: int, current_status: int) -> None:
        """Toggle task status in DB and refresh."""
        self.db.toggle_task(task_id, current_status)
        self._refresh_task_list()

    def _handle_delete_task(self, task_id: int) -> None:
        """Delete task from DB and refresh."""
        self.db.delete_task(task_id)
        self._refresh_task_list()

    # ── Live Telemetry Updates ────────────────────────────────────────────────

    def _update_telemetry(self) -> None:
        """Query CPU & RAM metrics and update progress bars smoothly without blocking."""
        try:
            cpu = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()

            used_gb = vm.used / (1024 ** 3)
            total_gb = vm.total / (1024 ** 3)
            ram_pct = vm.percent

            self._cpu_label.configure(text=f"CPU Usage: {cpu:.1f}%")
            self._cpu_bar.set(cpu / 100.0)

            # Dynamic color alert on CPU
            if cpu > 80.0:
                self._cpu_bar.configure(progress_color="#ef4444")
            elif cpu > 50.0:
                self._cpu_bar.configure(progress_color="#f59e0b")
            else:
                self._cpu_bar.configure(progress_color="#3b82f6")

            self._ram_label.configure(
                text=f"RAM Usage: {ram_pct:.1f}% ({used_gb:.1f} GB / {total_gb:.1f} GB)"
            )
            self._ram_bar.set(ram_pct / 100.0)

            if ram_pct > 85.0:
                self._ram_bar.configure(progress_color="#ef4444")
            else:
                self._ram_bar.configure(progress_color="#8b5cf6")

        except Exception:
            pass
        finally:
            self.root.after(1000, self._update_telemetry)

    # ── Settings Drawer Controls ──────────────────────────────────────────────

    def _build_settings_drawer(self) -> None:
        """Build hidden settings panel (overlaid on right, toggled open/close)."""
        self._drawer = ctk.CTkFrame(
            self.root,
            fg_color="#0d1526",
            corner_radius=12,
            border_color="#334155",
            border_width=1,
        )
        self._drawer_visible = False

        ctk.CTkLabel(
            self._drawer,
            text="Settings",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(14, 6))

        # Speech Rate slider
        ctk.CTkLabel(
            self._drawer,
            text="Speech Rate (WPM)",
            font=ctk.CTkFont(size=11),
            text_color=_TEXT_MUTED,
        ).pack(anchor="w", padx=16, pady=(8, 0))

        self._rate_slider = ctk.CTkSlider(
            self._drawer,
            from_=80,
            to=300,
            number_of_steps=44,
            command=self._on_rate_change,
        )
        self._rate_slider.set(self._speech_rate)
        self._rate_slider.pack(fill=tk.X, padx=16, pady=(4, 0))

        self._rate_label = ctk.CTkLabel(
            self._drawer,
            text=f"{int(self._speech_rate)} WPM",
            font=ctk.CTkFont(size=10),
            text_color=_TEXT_MUTED,
        )
        self._rate_label.pack(anchor="e", padx=16, pady=(0, 6))

        # Volume slider
        ctk.CTkLabel(
            self._drawer,
            text="TTS Volume",
            font=ctk.CTkFont(size=11),
            text_color=_TEXT_MUTED,
        ).pack(anchor="w", padx=16, pady=(8, 0))

        self._vol_slider = ctk.CTkSlider(
            self._drawer,
            from_=0.0,
            to=1.0,
            number_of_steps=20,
            command=self._on_volume_change,
        )
        self._vol_slider.set(self._speech_volume)
        self._vol_slider.pack(fill=tk.X, padx=16, pady=(4, 0))

        self._vol_label = ctk.CTkLabel(
            self._drawer,
            text=f"{self._speech_volume:.2f}",
            font=ctk.CTkFont(size=10),
            text_color=_TEXT_MUTED,
        )
        self._vol_label.pack(anchor="e", padx=16, pady=(0, 6))

        # Clear Chat button
        ctk.CTkButton(
            self._drawer,
            text="🗑 Clear Chat",
            height=32,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            corner_radius=8,
            font=ctk.CTkFont(size=11),
            command=self._clear_chat,
        ).pack(fill=tk.X, padx=16, pady=(12, 16))

    def _toggle_settings(self) -> None:
        """Show or hide the settings drawer."""
        self._drawer_visible = not self._drawer_visible
        if self._drawer_visible:
            self._drawer.place(relx=1.0, rely=0.0, anchor="ne", relwidth=0.32, relheight=0.65)
            self._settings_btn.configure(fg_color="#3b82f6")
        else:
            self._drawer.place_forget()
            self._settings_btn.configure(fg_color="#1e293b")

    def _on_rate_change(self, val: float) -> None:
        self._speech_rate = float(val)
        self._rate_label.configure(text=f"{int(self._speech_rate)} WPM")
        self.queue.put(("SETTINGS_CHANGE", {"speech_rate": self._speech_rate}))

    def _on_volume_change(self, val: float) -> None:
        self._speech_volume = float(val)
        self._vol_label.configure(text=f"{self._speech_volume:.2f}")
        self.queue.put(("SETTINGS_CHANGE", {"speech_volume": self._speech_volume}))

    def _clear_chat(self) -> None:
        """Destroy all child widgets inside the scrollable chat frame and notify engine."""
        for widget in self._chat_frame.winfo_children():
            widget.destroy()
        self.db.clear_chat_history()
        self.queue.put(("CHAT_CLEAR", None))
        self.queue.put(("SYSTEM", "Chat history and memory cleared."))

    # ── Audio Level Meter ─────────────────────────────────────────────────────

    def _update_audio_meter(self, level: float) -> None:
        """Resize the thin canvas bar to represent audio level (0.0–1.0)."""
        level = max(0.0, min(1.0, level))
        self._meter_level = level
        try:
            w = self._meter_canvas.winfo_width()
            bar_w = int(w * level)
            lower = self._status_pill.cget("text").lower()
            colour = "#4ade80" if "listen" in lower else "#3b82f6"
            self._meter_canvas.itemconfigure(self._meter_bar, fill=colour)
            self._meter_canvas.coords(self._meter_bar, 0, 0, bar_w, 3)
        except Exception:
            pass

    # ── Chat Helpers ──────────────────────────────────────────────────────────

    def _prefill(self, text: str) -> None:
        self.tabview.set("💬 Assistant Chat")
        self._entry.delete(0, tk.END)
        self._entry.insert(0, text)
        self._entry.focus()

    def _handle_send(self) -> None:
        cmd = self._entry.get().strip()
        if cmd:
            self._entry.delete(0, tk.END)
            self._on_send(cmd)

    def _make_message_card(self, sender: str, message: str) -> None:
        """Render a styled message bubble with timestamp into the chat canvas."""
        lower_sender = sender.lower()
        is_user    = lower_sender in {"you", "user"}
        is_assist  = lower_sender in {"assistant", "avantika", "alexa"}

        row = ctk.CTkFrame(self._chat_frame, fg_color="transparent")
        row.grid(sticky="ew", padx=10, pady=3)
        row.grid_columnconfigure(0, weight=1)

        if is_user:
            anchor, col_idx, bg = "e", 1, _BG_USER
            sender_color = "#bfdbfe"
        elif is_assist:
            anchor, col_idx, bg = "w", 0, _BG_ASSIST
            sender_color = "#38bdf8"
        else:
            anchor, col_idx, bg = "", 0, _BG_SYS
            sender_color = _TEXT_SYS

        card = ctk.CTkFrame(row, fg_color=bg, corner_radius=14)
        if not is_user and not is_assist:
            card.pack(anchor="center", padx=40, pady=0)
        else:
            card.grid(row=0, column=col_idx, sticky=anchor)

        # Header row: sender + timestamp
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill=tk.X, padx=12, pady=(7, 0))

        ctk.CTkLabel(
            hdr,
            text=sender,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=sender_color,
        ).pack(side=tk.LEFT)

        ts = datetime.datetime.now().strftime("%I:%M %p").lstrip("0") or datetime.datetime.now().strftime("%I:%M %p")
        ctk.CTkLabel(
            hdr,
            text=ts,
            font=ctk.CTkFont(size=8),
            text_color=_TEXT_MUTED,
        ).pack(side=tk.RIGHT)

        # Message body
        body_lbl = ctk.CTkLabel(
            card,
            text=message,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=_TEXT_PRIMARY if not (lower_sender == "system") else _TEXT_SYS,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        body_lbl.pack(anchor="w", padx=14, pady=(2, 10))

        # Auto-scroll on new bubble
        try:
            self._chat_frame.update_idletasks()
            self._chat_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass
            
        return body_lbl

    # ── Public Interface (API parity with main.py) ────────────────────────────

    def append_message(self, sender: str, message: str, persist: bool = True) -> None:
        """Render a message card. Call only from main thread (via process_queue)."""
        clean_msg = message.strip()
        
        # Deduplicate final full message from stream
        if sender == "Avantika" and getattr(self, "_last_stream_content", None) == clean_msg:
            self._last_stream_content = None
            return
            
        self._make_message_card(sender, clean_msg)
        if persist:
            # Map GUI sender display to DB role
            role = "user" if sender.lower() in ("you", "user") else "assistant"
            if sender.lower() == "system":
                role = "system"
            self.db.add_message(role, clean_msg)

    def _start_stream(self) -> None:
        self._stream_label = self._make_message_card("Avantika", "")
        self._stream_text = ""
        self._last_stream_content = None

    def _stream_chunk(self, text: str) -> None:
        if getattr(self, "_stream_label", None) is None:
            self._start_stream()
        self._stream_text += text
        self._stream_label.configure(text=self._stream_text)
        try:
            self._chat_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _end_stream(self) -> None:
        clean = getattr(self, "_stream_text", "").strip()
        self._last_stream_content = clean
        if clean:
            self.db.add_message("assistant", clean)
        self._stream_label = None

    def append_chat(self, sender: str, message: str) -> None:
        """Alias for append_message — maintains backward compatibility."""
        self.append_message(sender, message)

    def update_status(self, text: str) -> None:
        """Update the status pill colour and label. Main thread only."""
        if text == "STREAM_START":
            self._start_stream()
            return
        elif text.startswith("STREAM_CHUNK:"):
            self._stream_chunk(text[13:])
            return
        elif text == "STREAM_END":
            self._end_stream()
            return
            
        display, (bg, fg) = _resolve_status(text)
        self._status_pill.configure(text=display, fg_color=bg, text_color=fg)

    def set_status(self, text: str) -> None:
        """Alias for update_status — maintains backward compatibility."""
        self.update_status(text)

    def bring_to_front(self) -> None:
        """Restore window and force it to the foreground."""
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.root.focus_force()
        self.root.after(50, lambda: self.root.attributes('-topmost', False))

    def process_queue(self) -> None:
        """Drain the inter-thread queue and apply UI mutations on the main thread."""
        try:
            events_processed = 0
            while events_processed < 30:
                event_type, payload = self.queue.get_nowait()
                if event_type == "USER":
                    self.append_message("You", payload)
                elif event_type == "ASSISTANT":
                    self.append_message("Avantika", payload)
                elif event_type == "SYSTEM":
                    self.append_message("System", payload)
                elif event_type == "STATUS":
                    self.update_status(payload)
                elif event_type == "AUDIO_LEVEL":
                    self._update_audio_meter(float(payload))
                elif event_type in ("SETTINGS_CHANGE", "CHAT_CLEAR"):
                    pass
                self.queue.task_done()
                events_processed += 1
        except queue.Empty:
            pass
        finally:
            self.root.after(25, self.process_queue)

    def start(self) -> None:
        """Enter the CustomTkinter main event loop."""
        self.root.mainloop()

    def destroy(self) -> None:
        """Safely destroy the root window."""
        try:
            self.root.destroy()
        except Exception:
            pass

