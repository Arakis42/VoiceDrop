import io
import logging
import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

_local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
_log_dir = _local_app_data / "VoiceDrop"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "voicedrop.log"

# Tägliche Rotation um Mitternacht; backupCount=1 → es bleiben nur die aktive
# Datei (heute) und ein Backup (gestern) erhalten, alles Ältere wird gelöscht.
from logging.handlers import TimedRotatingFileHandler

_log_handler = TimedRotatingFileHandler(
    str(_log_file), when="midnight", backupCount=1, encoding="utf-8"
)
_log_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(message)s")
)
logging.basicConfig(level=logging.DEBUG, handlers=[_log_handler])

# Wenn die vorhandene Logdatei noch von einem früheren Tag stammt, einmalig
# beim Start rotieren, damit der heutige Lauf frisch beginnt und alte Riesen-
# Logs nicht bis zur nächsten Mitternacht weiterwachsen.
try:
    if _log_file.exists() and _log_file.stat().st_size > 0:
        import datetime as _dt

        _mtime = _dt.date.fromtimestamp(_log_file.stat().st_mtime)
        if _mtime < _dt.date.today():
            _log_handler.doRollover()
except Exception:
    pass


def _handle_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


sys.excepthook = _handle_exception

# ── Single-Instance-Guard ─────────────────────────────────────────────────────
# Muss VOR allen weiteren Imports passieren, damit kein zweites Fenster aufgeht.
import single_instance
if not single_instance.acquire():
    single_instance.notify_existing()
    sys.exit(0)

import pyperclip
import pystray
from pynput import keyboard as pynput_keyboard

import audio_mute
import autostart as _autostart
from config import get_config
from hotkeys import HotkeyManager
from icons import create_normal_icon, create_processing_icon, create_recording_icon
from processor import ProcessorError, get_processor
from recorder import AudioRecorder, RecorderError
from transcriber import TranscriberError, get_transcriber
from ui import (
    open_config_window,
    set_main_root,
    show_error_popup,
    update_status_in_window,
)
from version import APP_NAME, VERSION


def _release_stuck_modifiers(kb) -> None:
    """Hält ein Modifier (Ctrl/Shift/Alt) logisch gedrückt — etwa weil eine
    Makro-Taste eine Modifier-Kombi sendet und sich desynchronisiert — dann
    verfälscht das ALLE folgenden simulierten Tastendrücke (aus 'a' wird
    Ctrl+Alt+a → '©' o. ä.). Vor dem Einfügen daher alle Modifier explizit
    loslassen. Das Loslassen einer nicht gedrückten Taste ist harmlos.
    """
    K = pynput_keyboard.Key
    for mod in (K.ctrl_l, K.ctrl_r, K.shift_l, K.shift_r, K.alt_l, K.alt_r, K.alt_gr):
        try:
            kb.release(mod)
        except Exception:
            pass


def inject_text(text: str) -> None:
    cfg = get_config()
    method = cfg.get("injection_method")
    delay_ms = cfg.get("injection_delay_ms")

    if method == "type":
        try:
            kb = pynput_keyboard.Controller()
            _release_stuck_modifiers(kb)
            kb.type(text)
        except Exception as e:
            show_error_popup(f"Failed to inject text: {e}")
        return

    try:
        original = pyperclip.paste()
    except Exception:
        original = ""
    try:
        pyperclip.copy(text)
        time.sleep(max(0, int(delay_ms)) / 1000.0)
        kb = pynput_keyboard.Controller()
        _release_stuck_modifiers(kb)
        with kb.pressed(pynput_keyboard.Key.ctrl):
            kb.press("v")
            kb.release("v")

        def _restore():
            time.sleep(2.0)
            try:
                pyperclip.copy(original)
            except Exception:
                pass

        threading.Thread(target=_restore, daemon=True).start()
    except Exception as e:
        show_error_popup(f"Failed to inject text: {e}")


class AppState:
    def __init__(self, cfg, recorder: AudioRecorder, hotkey_mgr: HotkeyManager):
        self._cfg = cfg
        self._recorder = recorder
        self._hotkey_mgr = hotkey_mgr
        self._tray_icon = None
        self._current_mode: int = 1
        self._busy_lock = threading.Lock()
        self._is_busy = False

    def set_tray_icon(self, icon) -> None:
        self._tray_icon = icon

    def _set_icon(self, icon_fn) -> None:
        if self._tray_icon:
            try:
                self._tray_icon.icon = icon_fn()
            except Exception:
                pass

    def _set_tooltip(self, text: str) -> None:
        if self._tray_icon:
            try:
                self._tray_icon.title = f"VoiceDrop – {text}"
            except Exception:
                pass

    def update_status(self, status: str) -> None:
        self._set_tooltip(status)
        update_status_in_window(status, self._cfg.get("whisper_model"))

    def make_start_callback(self, mode: int):
        def _start(session: dict):
            with self._busy_lock:
                if self._is_busy:
                    # App ist noch beschäftigt (z. B. vorige Aufnahme wird verarbeitet).
                    # Stop-Callback informieren, dass nichts zu stoppen gibt.
                    session["event"].set()
                    return
                self._is_busy = True
                self._current_mode = mode
            if self._cfg.get("mute_during_recording"):
                audio_mute.mute_and_remember()
            try:
                self._recorder.start_recording()
            except RecorderError as e:
                audio_mute.restore()
                show_error_popup(str(e))
                with self._busy_lock:
                    self._is_busy = False
                session["event"].set()  # Fehlerfall: Stop-Pfad nicht blockieren
                return
            session["started"] = True   # Recorder läuft
            session["event"].set()
            self._set_icon(create_recording_icon)
            self.update_status("Recording...")

        return _start

    def make_stop_callback(self):
        def _stop(too_short: bool, session: dict):
            # Auf Recorder-Start warten (oder Early-Return von _start wegen Busy).
            # session["event"] wird in jedem Fall von _start gesetzt.
            session["event"].wait(timeout=1.0)

            if not session["started"]:
                # _start() war busy oder hat sich gemeldet ohne Aufnahme → nichts zu tun.
                logging.debug("STOP: session not started, ignoring")
                return

            if too_short:
                # Kurz-Druck: Aufnahme verwerfen und sofort zurücksetzen.
                logging.debug("min_hold not reached — discarding recording")
                self._recorder.stop_recording()  # Buffer verwerfen
                audio_mute.restore()
                with self._busy_lock:
                    self._is_busy = False
                self._set_icon(create_normal_icon)
                self.update_status("Ready")
                return

            # Normaler Pfad: Audio wiederherstellen und transkribieren.
            delay_ms = max(0, int(self._cfg.get("mute_release_delay_ms") or 0))
            if delay_ms > 0:
                threading.Timer(delay_ms / 1000.0, audio_mute.restore).start()
            else:
                audio_mute.restore()
            audio_buffer = self._recorder.stop_recording()
            mode = self._current_mode
            self._set_icon(create_processing_icon)
            self.update_status("Processing...")
            threading.Thread(
                target=self._process_and_inject,
                args=(mode, audio_buffer),
                daemon=True,
            ).start()

        return _stop

    def _process_and_inject(self, mode: int, audio: io.BytesIO) -> None:
        try:
            logging.debug("Processing mode=%d, audio_size=%d", mode, audio.seek(0, 2))
            audio.seek(0)
            transcriber = get_transcriber()
            text = transcriber.transcribe(audio)
            logging.debug("Transcribed: %r", text)
            if not text:
                logging.debug("Empty transcription, skipping inject")
                return
            if mode in (2, 3):
                api_key = self._cfg.get("api_key")
                if not api_key:
                    show_error_popup(
                        "Please add your Claude API key in Settings.\n"
                        "(Mode 1 works without an API key.)"
                    )
                    return
                processor = get_processor(api_key)
                text = processor.process(text, mode)
            inject_text(text)
        except TranscriberError as e:
            show_error_popup(str(e))
        except ProcessorError as e:
            show_error_popup(f"Claude API error:\n{e}")
        except Exception as e:
            show_error_popup(f"Unexpected error:\n{e}")
        finally:
            with self._busy_lock:
                self._is_busy = False
            self._set_icon(create_normal_icon)
            self.update_status("Ready")


def build_tray(app_state: AppState, cfg, hotkey_mgr: HotkeyManager):
    def on_settings(icon, item):
        open_config_window(cfg, hotkey_mgr)

    def on_autostart_toggle(icon, item):
        try:
            new_state = _autostart.toggle()
            state_text = "aktiviert" if new_state else "deaktiviert"
            import ui as ui_mod
            if ui_mod._main_root:
                from tkinter import messagebox
                ui_mod._main_root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "VoiceDrop",
                        f"Autostart {state_text}.",
                        parent=ui_mod._main_root,
                    ),
                )
        except Exception as e:
            show_error_popup(f"Autostart konnte nicht geändert werden:\n{e}")

    def autostart_checked(item):
        return _autostart.is_enabled()

    def on_about(icon, item):
        import ui as ui_mod
        if ui_mod._main_root:
            from tkinter import messagebox
            ui_mod._main_root.after(
                0,
                lambda: messagebox.showinfo(
                    f"Über {APP_NAME}",
                    f"{APP_NAME}  v{VERSION}\n\n"
                    f"Sprachaufnahme & Transkription mit Whisper\n"
                    f"Optionale KI-Verarbeitung via Claude API\n\n"
                    f"Hotkeys:\n"
                    f"  {cfg.get('hotkey_mode1')}  →  Wörtlich\n"
                    f"  {cfg.get('hotkey_mode2')}  →  Bereinigt (DE)\n"
                    f"  {cfg.get('hotkey_mode3')}  →  Übersetzt (EN)\n\n"
                    f"Halten = Aufnahme,  Loslassen = Transkribieren",
                    parent=ui_mod._main_root,
                ),
            )

    def on_quit(icon, item):
        hotkey_mgr.stop()
        single_instance.release()
        icon.stop()
        import ui as ui_mod
        if ui_mod._main_root:
            ui_mod._main_root.after(0, ui_mod._main_root.destroy)

    menu = pystray.Menu(
        pystray.MenuItem("Einstellungen", on_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Mit Windows starten",
            on_autostart_toggle,
            checked=autostart_checked,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Über VoiceDrop  v{VERSION}", on_about),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Beenden", on_quit),
    )
    icon = pystray.Icon(
        name="VoiceDrop",
        icon=create_normal_icon(),
        title="VoiceDrop – Bereit",
        menu=menu,
    )
    return icon


def main() -> None:
    cfg = get_config()

    # COM-Worker für Audio-Muting vorab starten, damit der Endpoint beim ersten
    # Tastendruck bereits gecacht ist (vermeidet 100–300 ms Anlauflatenz).
    audio_mute.initialize()

    # Create the hidden root tkinter window on the MAIN thread.
    # All tkinter operations (popups, config window) are dispatched here.
    root = tk.Tk()
    root.withdraw()
    set_main_root(root)

    # When a newer instance starts, it will signal us to quit so it can take
    # over. Tearing down the tkinter root from the main thread is the
    # cleanest way to unwind everything.
    def _on_takeover_request():
        logging.info("Takeover requested — shutting down.")
        try:
            root.after(0, root.destroy)
        except Exception:
            pass

    single_instance.install_quit_listener(_on_takeover_request)

    recorder = AudioRecorder()
    transcriber = get_transcriber()
    transcriber.set_model_name(cfg.get("whisper_model"))

    threading.Thread(target=_load_model_silently, args=(transcriber,), daemon=True).start()

    hotkey_mgr = HotkeyManager({})
    app_state = AppState(cfg, recorder, hotkey_mgr)

    callbacks = {
        1: (app_state.make_start_callback(1), app_state.make_stop_callback()),
        2: (app_state.make_start_callback(2), app_state.make_stop_callback()),
        3: (app_state.make_start_callback(3), app_state.make_stop_callback()),
    }
    hotkey_mgr._callbacks = callbacks
    hotkey_mgr.start()

    icon = build_tray(app_state, cfg, hotkey_mgr)
    app_state.set_tray_icon(icon)

    # Run pystray in a background thread; tkinter owns the main thread.
    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    if cfg.is_first_run():
        cfg.mark_first_run_done()
        root.after(1500, lambda: open_config_window(cfg, hotkey_mgr))

    # Main thread: tkinter event loop
    root.mainloop()

    # Clean shutdown
    hotkey_mgr.stop()
    icon.stop()


def _load_model_silently(transcriber) -> None:
    model = transcriber.get_model_name()
    logging.info("Loading Whisper model %r …", model)
    try:
        transcriber.load_model()
        logging.info("Whisper model %r loaded", model)
    except Exception:
        # Previously swallowed silently, which surfaced only later as the
        # misleading "please download the model" popup on the first dictation.
        logging.exception("Whisper model %r failed to load", model)


if __name__ == "__main__":
    main()
