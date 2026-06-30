import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config import Config
    from hotkeys import HotkeyManager

# The single hidden tk.Tk() root owned by the main thread.
# Set via set_main_root() before any UI calls.
_main_root: Optional[tk.Tk] = None
_config_win: Optional["ConfigWindow"] = None
_config_win_lock = threading.Lock()


def set_main_root(root: tk.Tk) -> None:
    global _main_root
    _main_root = root


def _on_main_thread(fn) -> None:
    """Schedule fn() on the main tkinter thread."""
    if _main_root:
        _main_root.after(0, fn)


def show_error_popup(message: str) -> None:
    def _show():
        if _main_root:
            messagebox.showerror("VoiceDrop", message, parent=_main_root)
    _on_main_thread(_show)


def show_info_popup(message: str) -> None:
    def _show():
        if _main_root:
            messagebox.showinfo("VoiceDrop", message, parent=_main_root)
    _on_main_thread(_show)


def open_config_window(cfg: "Config", hotkey_mgr: "HotkeyManager") -> None:
    _on_main_thread(lambda: _open_config_on_main(cfg, hotkey_mgr))


def _open_config_on_main(cfg: "Config", hotkey_mgr: "HotkeyManager") -> None:
    global _config_win
    with _config_win_lock:
        if _config_win is not None and _config_win.is_open():
            _config_win.focus()
            return
        _config_win = ConfigWindow(_main_root, cfg, hotkey_mgr)
        _config_win.show()


def update_status_in_window(status: str, model_name: str = "") -> None:
    def _update():
        with _config_win_lock:
            if _config_win and _config_win.is_open():
                _config_win.update_status(status, model_name)
    _on_main_thread(_update)


class ConfigWindow:
    WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
    LANGUAGES = [
        ("de", "Deutsch"),
        ("en", "English"),
        ("fr", "Français"),
        ("es", "Español"),
        ("it", "Italiano"),
        ("nl", "Nederlands"),
        ("pl", "Polski"),
        ("auto", "Auto-Detect"),
    ]

    def __init__(self, master: tk.Tk, cfg: "Config", hotkey_mgr: "HotkeyManager"):
        self._master = master
        self._cfg = cfg
        self._hotkey_mgr = hotkey_mgr
        self._win: Optional[tk.Toplevel] = None
        self._capturing_mode: Optional[int] = None
        self._captured_keys: set[str] = set()
        self._hotkey_entries: dict[int, tk.StringVar] = {}
        self._hotkey_entry_widgets: dict[int, tk.Entry] = {}
        self._status_var: Optional[tk.StringVar] = None
        self._model_info_var: Optional[tk.StringVar] = None
        self._progress_var: Optional[tk.DoubleVar] = None
        self._model_var: Optional[tk.StringVar] = None
        self._api_key_var: Optional[tk.StringVar] = None
        self._download_btn: Optional[tk.Button] = None
        self._progress_bar: Optional[ttk.Progressbar] = None
        self._progress_label: Optional[tk.Label] = None
        self._lang_var: Optional[tk.StringVar] = None
        self._injection_method_var: Optional[tk.StringVar] = None
        self._delay_var: Optional[tk.IntVar] = None
        self._delay_label: Optional[tk.Label] = None
        self._delay_spin: Optional[tk.Spinbox] = None
        self._prompt_entry: Optional[tk.Text] = None
        self._mic_var: Optional[tk.StringVar] = None
        self._mic_combo: Optional[ttk.Combobox] = None

    def is_open(self) -> bool:
        return self._win is not None and self._win.winfo_exists()

    def focus(self) -> None:
        if self._win:
            self._win.lift()
            self._win.focus_force()

    def show(self) -> None:
        self._win = tk.Toplevel(self._master)
        self._win.title("VoiceDrop Settings")
        self._win.resizable(False, False)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self._win.lift()
        self._win.focus_force()

    def _on_close(self) -> None:
        self._flush_pending()
        if self._win:
            self._win.destroy()
            self._win = None

    def _flush_pending(self) -> None:
        """Persist any UI-only state that hasn't been written yet.

        Safety net for fields that normally save on FocusOut — if the user
        closes the window without the widget losing focus first, the change
        would otherwise be lost.
        """
        try:
            if self._prompt_entry is not None:
                val = self._prompt_entry.get("1.0", "end-1c").strip()
                if val != (self._cfg.get("whisper_initial_prompt") or ""):
                    self._cfg.set("whisper_initial_prompt", val)
        except (tk.TclError, AttributeError):
            pass
        try:
            if self._api_key_var is not None:
                key = self._api_key_var.get().strip()
                if key != (self._cfg.get("api_key") or ""):
                    self._cfg.set("api_key", key)
        except (tk.TclError, AttributeError):
            pass
        try:
            if self._delay_var is not None:
                val = max(0, min(2000, int(self._delay_var.get())))
                if val != self._cfg.get("injection_delay_ms"):
                    self._cfg.set("injection_delay_ms", val)
        except (ValueError, tk.TclError, AttributeError):
            pass
        try:
            mdv = getattr(self, "_mute_delay_var", None)
            if mdv is not None:
                val = max(0, min(2000, int(mdv.get())))
                if val != self._cfg.get("mute_release_delay_ms"):
                    self._cfg.set("mute_release_delay_ms", val)
        except (ValueError, tk.TclError, AttributeError):
            pass

    def _build_ui(self) -> None:
        win = self._win
        pad = {"padx": 12, "pady": 6}

        # ── Hotkeys section ──────────────────────────────────────
        hk_frame = tk.LabelFrame(win, text="Hotkeys", font=("Segoe UI", 9, "bold"))
        hk_frame.pack(fill="x", **pad)

        tk.Label(hk_frame, text="Click a field, then press the desired key combination.",
                 font=("Segoe UI", 8), fg="gray").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 2))

        mode_labels = {
            1: "Mode 1 – Verbatim:",
            2: "Mode 2 – Clean Text:",
            3: "Mode 3 – Translate EN:",
        }
        for row_idx, (mode, label) in enumerate(mode_labels.items(), start=1):
            var = tk.StringVar(value=self._cfg.get(f"hotkey_mode{mode}"))
            self._hotkey_entries[mode] = var

            tk.Label(hk_frame, text=label, font=("Segoe UI", 9)).grid(
                row=row_idx, column=0, sticky="w", padx=8, pady=3)

            entry = tk.Entry(hk_frame, textvariable=var, width=22,
                             font=("Segoe UI", 9), state="readonly",
                             readonlybackground="white", cursor="hand2")
            entry.grid(row=row_idx, column=1, sticky="w", padx=8, pady=3)
            self._hotkey_entry_widgets[mode] = entry
            entry.bind("<Button-1>",
                       lambda e, m=mode, v=var, w=entry: self._start_capture(m, v, w))

        # ── API Key section ──────────────────────────────────────
        api_frame = tk.LabelFrame(win, text="Claude API Key", font=("Segoe UI", 9, "bold"))
        api_frame.pack(fill="x", **pad)

        self._api_key_var = tk.StringVar(value=self._cfg.get("api_key"))
        tk.Label(api_frame, text="API Key:", font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=8, pady=(6, 3))

        api_entry = tk.Entry(api_frame, textvariable=self._api_key_var,
                             width=34, show="•", font=("Segoe UI", 9))
        api_entry.grid(row=0, column=1, sticky="w", padx=4, pady=(6, 3))
        api_entry.bind("<FocusOut>", lambda _e: self._save_api_key(silent=True))

        tk.Button(api_frame, text="Save", command=self._save_api_key,
                  font=("Segoe UI", 9)).grid(row=0, column=2, padx=6, pady=(6, 3))

        help_text = (
            "No API key yet? Get one here: https://console.anthropic.com/\n"
            "Steps: Sign up → Go to \"API Keys\" → Click \"Create Key\" → Paste here.\n"
            "Mode 1 works without an API key. Modes 2 and 3 require one."
        )
        tk.Label(api_frame, text=help_text, font=("Segoe UI", 8), fg="#555555",
                 justify="left").grid(row=1, column=0, columnspan=3, sticky="w",
                                      padx=8, pady=(0, 6))

        # ── Whisper Model section ────────────────────────────────
        wm_frame = tk.LabelFrame(win, text="Whisper Model", font=("Segoe UI", 9, "bold"))
        wm_frame.pack(fill="x", **pad)

        self._model_var = tk.StringVar(value=self._cfg.get("whisper_model"))
        tk.Label(wm_frame, text="Model:", font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=8, pady=6)

        combo = ttk.Combobox(wm_frame, textvariable=self._model_var,
                             values=self.WHISPER_MODELS, state="readonly", width=12,
                             font=("Segoe UI", 9))
        combo.grid(row=0, column=1, sticky="w", padx=4, pady=6)
        combo.bind("<<ComboboxSelected>>", self._on_model_change)

        self._download_btn = tk.Button(wm_frame, text="Download Model",
                                       command=self._download_model,
                                       font=("Segoe UI", 9))
        self._download_btn.grid(row=0, column=2, padx=8, pady=6)

        # Language row
        tk.Label(wm_frame, text="Language:", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=8, pady=(0, 6))
        current_lang = self._cfg.get("whisper_language") or "de"
        # Build display label for current value
        lang_display = {code: label for code, label in self.LANGUAGES}
        lang_display_values = [label for _, label in self.LANGUAGES]
        self._lang_var = tk.StringVar(value=lang_display.get(current_lang, current_lang))
        lang_combo = ttk.Combobox(wm_frame, textvariable=self._lang_var,
                                  values=lang_display_values, state="readonly", width=14,
                                  font=("Segoe UI", 9))
        lang_combo.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 6))
        lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

        # Initial-Prompt row
        tk.Label(wm_frame, text="Sprach-Prompt:", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="nw", padx=8, pady=(0, 6))

        prompt_entry = tk.Text(wm_frame, font=("Segoe UI", 9),
                               width=36, height=3, wrap="word")
        prompt_entry.insert("1.0", self._cfg.get("whisper_initial_prompt") or "")
        prompt_entry.grid(row=2, column=1, columnspan=2, sticky="ew",
                          padx=(4, 8), pady=(0, 2))
        self._prompt_entry = prompt_entry

        def _save_prompt(_event=None):
            val = prompt_entry.get("1.0", "end-1c").strip()
            if val != (self._cfg.get("whisper_initial_prompt") or ""):
                self._cfg.set("whisper_initial_prompt", val)

        prompt_entry.bind("<FocusOut>", _save_prompt)
        prompt_entry.bind("<KeyRelease>", _save_prompt)

        tk.Label(wm_frame,
                 text='Tipp: Leer lassen = kein Prompt. Bei Sprache "Deutsch" wird\n'
                      'der Prompt genutzt, damit Whisper nicht ins Englische kippt.',
                 font=("Segoe UI", 8), fg="#666", justify="left").grid(
            row=3, column=1, columnspan=2, sticky="w", padx=(4, 8), pady=(0, 6))

        self._progress_var = tk.DoubleVar(master=win, value=0)
        self._progress_bar = ttk.Progressbar(wm_frame, variable=self._progress_var,
                                              maximum=100, length=260)
        self._progress_bar.grid(row=4, column=0, columnspan=3, padx=8, pady=(0, 4))
        self._progress_bar.grid_remove()

        self._progress_label = tk.Label(wm_frame, text="", font=("Segoe UI", 8), fg="#444")
        self._progress_label.grid(row=5, column=0, columnspan=3, padx=8, pady=(0, 6))
        self._progress_label.grid_remove()

        # ── Mikrofon section ─────────────────────────────────────
        mic_frame = tk.LabelFrame(win, text="Mikrofon", font=("Segoe UI", 9, "bold"))
        mic_frame.pack(fill="x", **pad)

        from recorder import get_input_devices
        device_names = ["Standard (System)"] + [name for name, _ in get_input_devices()]
        current_device = self._cfg.get("audio_device") or ""
        mic_display = current_device if current_device in device_names else "Standard (System)"
        self._mic_var = tk.StringVar(value=mic_display)

        tk.Label(mic_frame, text="Gerät:", font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=8, pady=6)

        self._mic_combo = ttk.Combobox(
            mic_frame, textvariable=self._mic_var,
            values=device_names, state="readonly", width=34,
            font=("Segoe UI", 9),
        )
        self._mic_combo.grid(row=0, column=1, sticky="w", padx=(4, 4), pady=6)
        self._mic_combo.bind("<<ComboboxSelected>>", self._on_mic_change)

        tk.Button(
            mic_frame, text="↻", font=("Segoe UI", 9),
            command=self._refresh_mic_list, width=3,
        ).grid(row=0, column=2, padx=(0, 8), pady=6)

        # ── Texteingabe section ──────────────────────────────────
        inj_frame = tk.LabelFrame(win, text="Texteingabe", font=("Segoe UI", 9, "bold"))
        inj_frame.pack(fill="x", **pad)

        self._injection_method_var = tk.StringVar(
            value=self._cfg.get("injection_method") or "clipboard")

        tk.Radiobutton(
            inj_frame, text="Zwischenablage (Standard)",
            variable=self._injection_method_var, value="clipboard",
            font=("Segoe UI", 9), command=self._on_injection_method_change,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))

        tk.Radiobutton(
            inj_frame, text="Zeichenweise (für Citrix/VM)",
            variable=self._injection_method_var, value="type",
            font=("Segoe UI", 9), command=self._on_injection_method_change,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(2, 4))

        self._delay_label = tk.Label(inj_frame, text="Verzögerung (ms):", font=("Segoe UI", 9))
        self._delay_label.grid(row=2, column=0, sticky="w", padx=8, pady=(0, 6))

        self._delay_var = tk.IntVar(value=self._cfg.get("injection_delay_ms") or 150)
        self._delay_spin = tk.Spinbox(
            inj_frame, from_=0, to=2000, increment=50,
            textvariable=self._delay_var, width=6, font=("Segoe UI", 9),
            command=self._on_delay_change,
        )
        self._delay_spin.grid(row=2, column=1, sticky="w", padx=4, pady=(0, 6))
        self._delay_spin.bind("<FocusOut>", lambda _: self._on_delay_change())
        self._update_delay_row_visibility()

        # ── System section ───────────────────────────────────────
        sys_frame = tk.LabelFrame(win, text="System", font=("Segoe UI", 9, "bold"))
        sys_frame.pack(fill="x", **pad)

        import autostart as _autostart_mod
        self._autostart_var = tk.BooleanVar(value=_autostart_mod.is_enabled())

        def _on_autostart_toggle():
            try:
                if self._autostart_var.get():
                    _autostart_mod.enable()
                else:
                    _autostart_mod.disable()
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("VoiceDrop", f"Autostart konnte nicht geändert werden:\n{e}",
                                     parent=self._win)
                # Zustand zurücksetzen
                self._autostart_var.set(_autostart_mod.is_enabled())

        tk.Checkbutton(
            sys_frame,
            text="Mit Windows starten (Autostart)",
            variable=self._autostart_var,
            command=_on_autostart_toggle,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=8, pady=(6, 2))

        self._mute_var = tk.BooleanVar(
            value=bool(self._cfg.get("mute_during_recording")))
        tk.Checkbutton(
            sys_frame,
            text="System-Audio während Aufnahme stummschalten",
            variable=self._mute_var,
            command=lambda: self._cfg.set("mute_during_recording", self._mute_var.get()),
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=8, pady=(2, 2))

        mute_delay_row = tk.Frame(sys_frame)
        mute_delay_row.pack(anchor="w", padx=24, pady=(0, 6))
        tk.Label(mute_delay_row, text="Nach Loslassen noch stumm halten (ms):",
                 font=("Segoe UI", 9)).pack(side="left")
        self._mute_delay_var = tk.IntVar(
            value=int(self._cfg.get("mute_release_delay_ms") or 0))

        def _on_mute_delay_change():
            try:
                val = max(0, min(2000, int(self._mute_delay_var.get())))
            except (ValueError, tk.TclError):
                val = 100
            self._mute_delay_var.set(val)
            if val != self._cfg.get("mute_release_delay_ms"):
                self._cfg.set("mute_release_delay_ms", val)

        mute_delay_spin = tk.Spinbox(
            mute_delay_row, from_=0, to=2000, increment=50,
            textvariable=self._mute_delay_var, width=6, font=("Segoe UI", 9),
            command=_on_mute_delay_change,
        )
        mute_delay_spin.pack(side="left", padx=(6, 0))
        mute_delay_spin.bind("<FocusOut>", lambda _e: _on_mute_delay_change())

        min_hold_row = tk.Frame(sys_frame)
        min_hold_row.pack(anchor="w", padx=24, pady=(0, 6))
        tk.Label(min_hold_row, text="Mindest-Haltezeit Hotkey (ms):",
                 font=("Segoe UI", 9)).pack(side="left")
        self._min_hold_var = tk.IntVar(
            value=int(self._cfg.get("min_hold_duration_ms") or 0))

        def _on_min_hold_change():
            try:
                val = max(0, min(2000, int(self._min_hold_var.get())))
            except (ValueError, tk.TclError):
                val = 250
            self._min_hold_var.set(val)
            if val != self._cfg.get("min_hold_duration_ms"):
                self._cfg.set("min_hold_duration_ms", val)

        min_hold_spin = tk.Spinbox(
            min_hold_row, from_=0, to=2000, increment=50,
            textvariable=self._min_hold_var, width=6, font=("Segoe UI", 9),
            command=_on_min_hold_change,
        )
        min_hold_spin.pack(side="left", padx=(6, 0))
        min_hold_spin.bind("<FocusOut>", lambda _e: _on_min_hold_change())

        # ── Status section ───────────────────────────────────────
        st_frame = tk.LabelFrame(win, text="Status", font=("Segoe UI", 9, "bold"))
        st_frame.pack(fill="x", **pad)

        self._status_var = tk.StringVar(master=win, value="Ready")
        self._model_info_var = tk.StringVar(
            master=win, value=f"Model: {self._cfg.get('whisper_model')}"
        )

        tk.Label(st_frame, textvariable=self._status_var,
                 font=("Segoe UI", 9)).pack(side="left", padx=8, pady=6)
        tk.Label(st_frame, textvariable=self._model_info_var,
                 font=("Segoe UI", 9), fg="#555").pack(side="right", padx=8, pady=6)

        tk.Frame(win, height=6).pack()

    # ── Hotkey capture ───────────────────────────────────────────

    def _start_capture(self, mode: int, var: tk.StringVar, entry: tk.Entry) -> None:
        if self._capturing_mode is not None:
            return
        self._capturing_mode = mode
        self._captured_keys = set()
        entry.config(readonlybackground="#fffacd")
        var.set("Press keys...")
        self._hotkey_mgr.stop()
        self._win.bind("<KeyPress>", self._on_capture_keypress)
        self._win.focus_set()

    # Maps shifted-digit keysyms (German and US keyboard) back to the base digit.
    _SHIFTED_DIGIT_MAP = {
        # US keyboard: Shift+1..0
        "exclam": "1", "at": "2", "numbersign": "3", "dollar": "4",
        "percent": "5", "asciicircum": "6", "ampersand": "7",
        "asterisk": "8", "parenleft": "9", "parenright": "0",
        # German keyboard: Shift+1=!, Shift+2=", Shift+3=#, ...
        "quotedbl": "2", "section": "3", "slash": "7", "equal": "0",
    }

    def _on_capture_keypress(self, event: tk.Event) -> None:
        if self._capturing_mode is None:
            return
        keysym = event.keysym.lower()
        if keysym in ("control_l", "control_r"):
            self._captured_keys.add("ctrl")
        elif keysym in ("shift_l", "shift_r"):
            self._captured_keys.add("shift")
        elif keysym in ("alt_l", "alt_r"):
            self._captured_keys.add("alt")
        elif keysym in self._SHIFTED_DIGIT_MAP:
            # Shift+digit arrives as e.g. "exclam" — map back to the actual digit
            self._captured_keys.add(self._SHIFTED_DIGIT_MAP[keysym])
            self._finish_capture()
        elif len(keysym) == 1 or (keysym.startswith("f") and keysym[1:].isdigit()):
            self._captured_keys.add(keysym)
            self._finish_capture()

    def _finish_capture(self) -> None:
        mode = self._capturing_mode
        if mode is None:
            return
        self._win.unbind("<KeyPress>")
        keys = self._captured_keys
        modifiers = sorted(k for k in keys if k in ("ctrl", "shift", "alt"))
        triggers = [k for k in keys if k not in ("ctrl", "shift", "alt")]
        if triggers:
            hotkey_str = "+".join(modifiers + triggers)
        else:
            hotkey_str = self._cfg.get(f"hotkey_mode{mode}")
        self._hotkey_entries[mode].set(hotkey_str)
        self._cfg.set(f"hotkey_mode{mode}", hotkey_str)
        self._capturing_mode = None
        self._captured_keys = set()
        for widget in self._hotkey_entry_widgets.values():
            widget.config(readonlybackground="white")
        self._hotkey_mgr.reload_hotkeys()

    # ── API Key ──────────────────────────────────────────────────

    def _save_api_key(self, silent: bool = False) -> None:
        key = self._api_key_var.get().strip()
        if key == (self._cfg.get("api_key") or ""):
            return
        self._cfg.set("api_key", key)
        if not silent and self._status_var:
            self._status_var.set("API key saved.")
            self._win.after(2000, lambda: self._status_var.set("Ready")
                            if self._status_var else None)

    # ── Whisper Model ────────────────────────────────────────────

    def _on_lang_change(self, _event=None) -> None:
        label = self._lang_var.get()
        code = next((c for c, l in self.LANGUAGES if l == label), "de")
        # "auto" → empty string → Whisper auto-detects
        self._cfg.set("whisper_language", "" if code == "auto" else code)

    def _on_model_change(self, _event=None) -> None:
        model_name = self._model_var.get()
        self._cfg.set("whisper_model", model_name)
        if self._model_info_var:
            self._model_info_var.set(f"Model: {model_name}")
        from transcriber import get_transcriber
        get_transcriber().set_model_name(model_name)

    def _download_model(self) -> None:
        model_name = self._model_var.get()
        if self._download_btn:
            self._download_btn.config(state="disabled", text="Downloading...")
        if self._progress_bar:
            self._progress_bar.grid()
        if self._progress_label:
            self._progress_label.config(text=f"Downloading {model_name}...")
            self._progress_label.grid()
        if self._progress_var:
            self._progress_var.set(0)
        threading.Thread(
            target=self._download_thread, args=(model_name,), daemon=True
        ).start()

    def _win_after(self, fn) -> None:
        """Safely schedule fn on the main thread, ignoring destroyed windows."""
        try:
            if _main_root:
                _main_root.after(0, fn)
        except Exception:
            pass

    def _download_thread(self, model_name: str) -> None:
        try:
            import tqdm as tqdm_module

            original_tqdm = tqdm_module.tqdm
            outer_self = self

            class ProgressTqdm(tqdm_module.tqdm):
                def update(inner_self, n=1):
                    super().update(n)
                    if inner_self.total:
                        pct = min(100, int(100 * inner_self.n / inner_self.total))
                        outer_self._win_after(lambda p=pct: outer_self._set_progress(p))

            tqdm_module.tqdm = ProgressTqdm
            try:
                import whisper
                whisper.load_model(model_name)
            finally:
                tqdm_module.tqdm = original_tqdm

            from transcriber import get_transcriber
            tr = get_transcriber()
            tr.set_model_name(model_name)
            tr.load_model()

            self._win_after(lambda: self._on_download_done(True, model_name))
        except Exception as e:
            self._win_after(
                lambda err=str(e): self._on_download_done(False, model_name, err))

    def _set_progress(self, pct: int) -> None:
        try:
            if self._progress_var and self.is_open():
                self._progress_var.set(pct)
        except Exception:
            pass

    def _on_download_done(self, success: bool, model_name: str, error: str = "") -> None:
        try:
            if self.is_open():
                if self._download_btn:
                    self._download_btn.config(state="normal", text="Download Model")
                if self._progress_bar:
                    self._progress_bar.grid_remove()
                if self._progress_label:
                    self._progress_label.grid_remove()
        except Exception:
            pass
        if success:
            if self._status_var and self.is_open():
                self._status_var.set(f"Model '{model_name}' ready.")
            if self._model_info_var and self.is_open():
                self._model_info_var.set(f"Model: {model_name}")
        else:
            show_error_popup(f"Failed to download model '{model_name}':\n{error}")

    # ── Injection method ─────────────────────────────────────────

    def _on_injection_method_change(self) -> None:
        self._cfg.set("injection_method", self._injection_method_var.get())
        self._update_delay_row_visibility()

    def _update_delay_row_visibility(self) -> None:
        is_clipboard = (self._injection_method_var.get() == "clipboard")
        if self._delay_label:
            self._delay_label.config(fg="black" if is_clipboard else "gray")
        if self._delay_spin:
            self._delay_spin.config(state="normal" if is_clipboard else "disabled")

    def _on_delay_change(self) -> None:
        try:
            val = max(0, min(2000, int(self._delay_var.get())))
        except (ValueError, tk.TclError):
            val = 150
        self._delay_var.set(val)
        self._cfg.set("injection_delay_ms", val)

    # ── Mikrofon ─────────────────────────────────────────────────

    def _on_mic_change(self, _event=None) -> None:
        selection = self._mic_var.get()
        self._cfg.set("audio_device", None if selection == "Standard (System)" else selection)

    def _refresh_mic_list(self) -> None:
        from recorder import get_input_devices
        device_names = ["Standard (System)"] + [name for name, _ in get_input_devices()]
        if self._mic_combo:
            self._mic_combo.config(values=device_names)
        if self._mic_var and self._mic_var.get() not in device_names:
            self._mic_var.set("Standard (System)")
            self._cfg.set("audio_device", None)

    # ── Status update (called from main thread via after()) ──────

    def update_status(self, status: str, model_name: str = "") -> None:
        if self._status_var and self.is_open():
            self._status_var.set(status)
        if model_name and self._model_info_var and self.is_open():
            self._model_info_var.set(f"Model: {model_name}")
