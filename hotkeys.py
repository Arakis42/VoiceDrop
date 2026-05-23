import logging
import threading
from typing import Callable, Optional

try:
    from pynput import keyboard
    from pynput.keyboard import Key, KeyCode
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

# Windows VK codes for modifier variants
_CTRL_VKS = {162, 163}   # VK_LCONTROL, VK_RCONTROL
_SHIFT_VKS = {160, 161}  # VK_LSHIFT, VK_RSHIFT
_ALT_VKS = {164, 165}    # VK_LMENU, VK_RMENU


def _key_category(key) -> Optional[str]:
    """Return a canonical string for the key: 'ctrl', 'shift', 'alt', or a lowercase char/name."""
    if not PYNPUT_AVAILABLE:
        return None

    if isinstance(key, Key):
        if key in (Key.ctrl_l, Key.ctrl_r, Key.ctrl):
            return "ctrl"
        if key in (Key.shift_l, Key.shift_r, Key.shift):
            return "shift"
        if key in (Key.alt_l, Key.alt_r, Key.alt, Key.alt_gr):
            return "alt"
        return None

    if isinstance(key, KeyCode):
        vk = getattr(key, "vk", None)
        if vk is not None:
            if vk in _CTRL_VKS:
                return "ctrl"
            if vk in _SHIFT_VKS:
                return "shift"
            if vk in _ALT_VKS:
                return "alt"
            # A–Z (VK 65–90) → lowercase letter
            if 65 <= vk <= 90:
                return chr(vk + 32)
            # 0–9 number row (VK 48–57)
            if 48 <= vk <= 57:
                return chr(vk)
            # Numpad 0–9 (VK 96–105)
            if 96 <= vk <= 105:
                return str(vk - 96)
            # F1–F12 (VK 112–123)
            if 112 <= vk <= 123:
                return f"f{vk - 111}"
        # Fallback: use char, normalised to lowercase
        char = getattr(key, "char", None)
        if char:
            return char.lower()

    return None


def _parse_hotkey(hotkey_str: str) -> tuple[frozenset, str]:
    """Parse 'ctrl+shift+q' → ({'ctrl','shift'}, 'q')."""
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    trigger = parts[-1]
    modifiers = frozenset(parts[:-1])
    return modifiers, trigger


class HotkeyManager:
    def __init__(self, callbacks: dict[int, tuple[Callable, Callable]]):
        self._callbacks = callbacks
        self._held: set[str] = set()
        self._active_mode: Optional[int] = None
        self._lock = threading.Lock()
        self._listener: Optional["keyboard.Listener"] = None
        self._hotkeys: dict[int, tuple[frozenset, str]] = {}
        self._reload_config()

    def _reload_config(self) -> None:
        from config import get_config
        cfg = get_config()
        self._hotkeys = {
            1: _parse_hotkey(cfg.get("hotkey_mode1")),
            2: _parse_hotkey(cfg.get("hotkey_mode2")),
            3: _parse_hotkey(cfg.get("hotkey_mode3")),
        }
        logging.debug("Hotkeys reloaded: %s", self._hotkeys)

    def start(self) -> None:
        if not PYNPUT_AVAILABLE:
            return
        if self._listener and self._listener.is_alive():
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        with self._lock:
            self._held.clear()
            self._active_mode = None

    def reload_hotkeys(self) -> None:
        self.stop()
        self._reload_config()
        self.start()

    def _on_press(self, key) -> None:
        cat = _key_category(key)
        if cat is None:
            return

        with self._lock:
            self._held.add(cat)
            logging.debug("PRESS %s → held=%s active=%s", cat, self._held, self._active_mode)

            if self._active_mode is not None:
                return

            for mode, (modifiers, trigger) in self._hotkeys.items():
                required = modifiers | {trigger}
                if required and required.issubset(self._held):
                    self._active_mode = mode
                    logging.debug("COMBO START mode=%d", mode)
                    cb = self._callbacks.get(mode)
                    if cb:
                        t = threading.Thread(target=cb[0], daemon=True)
                        t.start()
                    break

    def _on_release(self, key) -> None:
        cat = _key_category(key)
        if cat is None:
            return

        with self._lock:
            self._held.discard(cat)
            logging.debug("RELEASE %s → held=%s active=%s", cat, self._held, self._active_mode)

            if self._active_mode is None:
                return

            modifiers, trigger = self._hotkeys.get(self._active_mode, (frozenset(), ""))
            combo = modifiers | {trigger}
            if cat in combo:
                mode = self._active_mode
                self._active_mode = None
                logging.debug("COMBO END mode=%d", mode)
                cb = self._callbacks.get(mode)
                if cb:
                    t = threading.Thread(target=cb[1], daemon=True)
                    t.start()
