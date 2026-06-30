import json
import os
from pathlib import Path
from typing import Any

# Nutzerdaten immer in %APPDATA%\VoiceDrop\ – das funktioniert auch wenn
# die App in Program Files installiert ist (kein Schreibrecht dort nötig).
_APP_DATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
CONFIG_DIR = _APP_DATA / "VoiceDrop"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "hotkey_mode1": "ctrl+shift+1",
    "hotkey_mode2": "ctrl+shift+2",
    "hotkey_mode3": "ctrl+shift+3",
    "whisper_model": "medium",
    "whisper_language": "de",
    "whisper_initial_prompt": (
        "Ich spreche hauptsächlich Deutsch und verwende gelegentlich "
        "englische Fachbegriffe aus der IT und Programmierung."
    ),
    "api_key": "",
    "first_run": True,
    "injection_method": "clipboard",   # "clipboard" | "type"
    "injection_delay_ms": 150,
    "mute_during_recording": True,
    "mute_release_delay_ms": 100,
    "min_hold_duration_ms": 250,
    "audio_device": None,   # None = system default; otherwise stored as device name string
}


def _find_legacy_config() -> Path | None:
    """Sucht eine config.json neben der aktuell ausgeführten main.py (Migration)."""
    import sys
    for candidate in (
        Path(sys.argv[0]).parent / "config.json",   # neben main.py
        Path(__file__).parent / "config.json",       # neben config.py
    ):
        try:
            if candidate.resolve() != CONFIG_FILE.resolve() and candidate.exists():
                return candidate
        except OSError:
            pass
    return None


class Config:
    def __init__(self):
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = {**DEFAULTS, **saved}
            except (json.JSONDecodeError, OSError):
                self._data = dict(DEFAULTS)
        else:
            # Migration: alte config.json neben main.py/config.py einmalig übernehmen
            legacy = _find_legacy_config()
            if legacy:
                try:
                    with open(legacy, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                    self._data = {**DEFAULTS, **saved}
                    self.save()
                    return
                except (json.JSONDecodeError, OSError):
                    pass
            self._data = dict(DEFAULTS)
            self.save()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, CONFIG_FILE)
        except OSError as e:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise e

    def get(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def is_first_run(self) -> bool:
        return bool(self._data.get("first_run", True))

    def mark_first_run_done(self) -> None:
        self.set("first_run", False)


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
