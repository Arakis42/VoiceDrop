"""
autostart.py – Windows-Autostart via Registry (HKCU, kein Admin nötig).

Schreibt/loescht den Starteintrag unter:
  HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
"""
import logging
import sys
import winreg
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "VoiceDrop"


def is_enabled() -> bool:
    """True, wenn der Autostart-Eintrag existiert."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


def enable() -> None:
    """Autostart aktivieren — benutzt den aktuellen Python-Pfad."""
    cmd = _build_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY,
                             access=winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, cmd)
        logging.info("Autostart aktiviert: %s", cmd)
    except OSError as exc:
        logging.error("Autostart aktivieren fehlgeschlagen: %s", exc)
        raise


def disable() -> None:
    """Autostart-Eintrag entfernen."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY,
                             access=winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _APP_NAME)
        logging.info("Autostart deaktiviert.")
    except FileNotFoundError:
        pass  # War schon nicht gesetzt
    except OSError as exc:
        logging.error("Autostart deaktivieren fehlgeschlagen: %s", exc)
        raise


def toggle() -> bool:
    """Autostart umschalten. Gibt den neuen Zustand zurück."""
    if is_enabled():
        disable()
        return False
    else:
        enable()
        return True


def _build_command() -> str:
    """Baut den Startbefehl für den Registry-Eintrag.

    - Wenn als kompilierte .exe: direkt den Pfad zur exe.
    - Wenn als Python-Skript: pythonw.exe + main.py (kein Konsolenfenster).
    """
    if getattr(sys, "frozen", False):
        # PyInstaller-Bundle oder ähnliches
        return f'"{sys.executable}"'

    # Python-Skript: pythonw.exe verwenden (kein schwarzes Konsolenfenster)
    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable)  # Fallback auf python.exe

    # main.py aus dem Verzeichnis dieser Datei
    main_py = Path(__file__).parent / "main.py"
    return f'"{pythonw}" "{main_py}"'
