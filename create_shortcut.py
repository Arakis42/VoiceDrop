"""
create_shortcut.py – Legt eine VoiceDrop-Verknuepfung im Startmenue an.

Die Verknuepfung verwendet pythonw.exe (kein Konsolenfenster) und zeigt
auf dieselbe main.py wie der Autostart-Eintrag, sofern dieser existiert.
Falls kein Autostart gesetzt ist, wird der aktuelle Ordner verwendet.

Ausfuehren:
    python create_shortcut.py
"""
import os
import shlex
import sys
import winreg
from pathlib import Path

import comtypes.client

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "VoiceDrop"


def _resolve_target() -> tuple[str, str, str]:
    """Liefert (target, arguments, working_dir) fuer die Verknuepfung."""
    # 1) Autostart-Eintrag auslesen, falls vorhanden
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            cmd, _ = winreg.QueryValueEx(key, _APP_NAME)
        parts = shlex.split(cmd, posix=False)
        # shlex laesst Anfuehrungszeichen stehen -> entfernen
        parts = [p.strip('"') for p in parts]
        if parts:
            target = parts[0]
            arguments = " ".join(f'"{p}"' for p in parts[1:])
            workdir = str(Path(parts[1]).parent) if len(parts) > 1 else str(Path(target).parent)
            return target, arguments, workdir
    except (FileNotFoundError, OSError):
        pass

    # 2) Fallback: pythonw.exe + main.py aus diesem Verzeichnis
    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    main_py = Path(__file__).resolve().parent / "main.py"
    return str(pythonw), f'"{main_py}"', str(main_py.parent)


def _find_icon(workdir: str) -> str:
    """Sucht eine .ico Datei im Arbeitsverzeichnis."""
    for name in ("voicedrop.ico", "icon.ico", "app.ico"):
        candidate = Path(workdir) / name
        if candidate.exists():
            return str(candidate)
    return ""


def main() -> None:
    target, arguments, workdir = _resolve_target()

    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_menu.mkdir(parents=True, exist_ok=True)
    lnk_path = start_menu / "VoiceDrop.lnk"

    shell = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
    shortcut = shell.CreateShortCut(str(lnk_path))
    shortcut.TargetPath = target
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = workdir
    shortcut.WindowStyle = 7  # minimiert (pythonw zeigt eh nichts, aber sicher ist sicher)
    shortcut.Description = "VoiceDrop – Sprache zu Text"
    icon = _find_icon(workdir)
    if icon:
        shortcut.IconLocation = icon
    shortcut.Save()

    print(f"Verknuepfung angelegt: {lnk_path}")
    print(f"  Ziel       : {target}")
    print(f"  Argumente  : {arguments}")
    print(f"  Arbeitsdir : {workdir}")


if __name__ == "__main__":
    main()
