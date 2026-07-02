"""
setup.py  –  VoiceDrop Installer / Updater / Deinstaller

Starten:
    python setup.py              -> GUI-Installer
    python setup.py --uninstall  -> Deinstallations-Dialog
"""

import ctypes
import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

import autostart  # ensure_named_launcher() – VoiceDrop.exe statt pythonw.exe


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _needs_elevation(path: Path) -> bool:
    """True, wenn in den Pfad ohne Admin-Rechte nicht geschrieben werden kann."""
    test = path / ".voicedrop_write_test"
    try:
        path.mkdir(parents=True, exist_ok=True)
        test.touch()
        test.unlink()
        return False
    except (PermissionError, OSError):
        return True


def _relaunch_as_admin() -> None:
    """Dieses Skript mit Admin-Rechten neu starten (UAC-Prompt)."""
    script = str(Path(__file__).resolve())
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}"', None, 1
    )
    sys.exit(0)

# ──────────────────────────────────────────────────────────────────────────────
# Pfade  (Defaults, werden im GUI ggf. überschrieben)
# ──────────────────────────────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent

_LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
_APPDATA        = Path(os.environ.get("APPDATA",      Path.home() / "AppData" / "Roaming"))

DEFAULT_INSTALL_DIR = _LOCAL_APP_DATA / "VoiceDrop"

START_MENU_LNK = _APPDATA / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "VoiceDrop.lnk"
DESKTOP_LNK    = Path.home() / "Desktop" / "VoiceDrop.lnk"

# Registry-Schlüssel
_UNINSTALL_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceDrop"
_INSTALL_REG    = r"Software\VoiceDrop"

# Dateien, die in das Installationsverzeichnis kopiert werden
_APP_FILES = [
    "main.py", "config.py", "recorder.py", "transcriber.py",
    "processor.py", "hotkeys.py", "ui.py", "icons.py",
    "version.py", "single_instance.py", "autostart.py",
    "setup.py", "requirements.txt", "README.md",
    # config.json wird NICHT kopiert – Nutzerdaten liegen ausschließlich in
    # %APPDATA%\VoiceDrop\config.json und werden von config.py verwaltet.
]

# ──────────────────────────────────────────────────────────────────────────────
# Version aus Quellverzeichnis laden
# ──────────────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(_SRC_DIR))
try:
    from version import VERSION, APP_NAME, PUBLISHER
except ImportError:
    VERSION, APP_NAME, PUBLISHER = "1.0.0", "VoiceDrop", "Andreas Stanke"


# ══════════════════════════════════════════════════════════════════════════════
# Registry-Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def is_installed() -> bool:
    """True, wenn VoiceDrop bereits installiert ist."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INSTALL_REG):
            return True
    except FileNotFoundError:
        return False


def get_installed_dir() -> Path | None:
    """Gibt das installierte Verzeichnis zurück, oder None."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INSTALL_REG) as k:
            d, _ = winreg.QueryValueEx(k, "InstallDir")
            return Path(d)
    except (FileNotFoundError, OSError):
        return None


def get_installed_version() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INSTALL_REG) as k:
            v, _ = winreg.QueryValueEx(k, "Version")
            return v
    except (FileNotFoundError, OSError):
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# Kern-Logik  (kein Tkinter – kann auch headless genutzt werden)
# ══════════════════════════════════════════════════════════════════════════════

def do_install(
    install_dir: Path,
    progress_cb=None,
    create_start_menu: bool = True,
    create_desktop:    bool = False,
    enable_autostart:  bool = False,
) -> None:
    """Vollständige Neuinstallation nach install_dir."""

    def _p(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    _p(0,  "Verzeichnis wird erstellt …")
    install_dir.mkdir(parents=True, exist_ok=True)

    _p(10, "Dateien werden kopiert …")
    _copy_files(install_dir, is_update=False)

    _p(40, "Icon wird erstellt …")
    ico = _generate_ico(install_dir)

    _p(55, "Verkuepfungen werden erstellt …")
    launcher = autostart.ensure_named_launcher()  # VoiceDrop.exe (Task-Manager)
    main_py = install_dir / "main.py"

    if create_start_menu:
        _create_shortcut(START_MENU_LNK, launcher, main_py, ico)
    if create_desktop:
        _create_shortcut(DESKTOP_LNK, launcher, main_py, ico)

    _p(75, "Registry wird geschrieben …")
    _write_install_reg(install_dir, ico)
    _write_uninstall_reg(install_dir, ico)

    if enable_autostart:
        _p(90, "Autostart wird eingerichtet …")
        _set_autostart(install_dir, True)

    _p(100, "Fertig.")


def do_update(install_dir: Path, progress_cb=None) -> None:
    """Update: neue Dateien kopieren, config.json des Nutzers behalten."""

    def _p(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    _p(0,  "Neue Dateien werden kopiert …")
    install_dir.mkdir(parents=True, exist_ok=True)
    _copy_files(install_dir, is_update=True)

    _p(60, "Icon wird aktualisiert …")
    ico = _generate_ico(install_dir)

    _p(80, "Registry wird aktualisiert …")
    _write_install_reg(install_dir, ico)
    _write_uninstall_reg(install_dir, ico)

    _p(100, "Update abgeschlossen.")


def do_uninstall(install_dir: Path, progress_cb=None) -> None:
    """Deinstallation: Autostart, Verknuepfungen, Registry, Dateien."""

    def _p(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    _p(0,  "Autostart wird entfernt …")
    try:
        _set_autostart(install_dir, False)
    except Exception:
        pass

    _p(20, "Verknuepfungen werden entfernt …")
    for lnk in (START_MENU_LNK, DESKTOP_LNK):
        try:
            lnk.unlink(missing_ok=True)
        except OSError:
            pass

    _p(45, "Registry-Eintraege werden entfernt …")
    for key in (_UNINSTALL_KEY, _INSTALL_REG):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass

    _p(65, "Dateien werden entfernt …")
    try:
        shutil.rmtree(install_dir, ignore_errors=True)
    except OSError:
        pass

    _p(100, "Deinstallation abgeschlossen.")


# ──────────────────────────────────────────────────────────────────────────────
# Interne Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────

def _copy_files(install_dir: Path, is_update: bool) -> None:
    for filename in _APP_FILES:
        if filename == "config.json":
            continue  # Niemals kopieren – liegt in %APPDATA%, nicht im Install-Dir
        src = _SRC_DIR / filename
        dst = install_dir / filename
        if not src.exists():
            continue
        shutil.copy2(src, dst)


def _generate_ico(install_dir: Path) -> Path:
    """Erzeugt voicedrop.ico im Installationsverzeichnis."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("icons_src", _SRC_DIR / "icons.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ico = install_dir / "voicedrop.ico"
    mod.save_ico_file(ico)
    return ico


def _create_shortcut(lnk: Path, target: Path, script: Path, icon: Path) -> None:
    """Erstellt eine .lnk-Verknuepfung via WScript.Shell (PowerShell).

    Pfade werden in PS-einfache Anfuehrungszeichen eingeschlossen (kein
    Escaping noetig, ausser fuer einfache Anfuehrungszeichen selbst – die
    kommen in Windows-Pfaden nicht vor).
    Double-Quotes in Arguments werden als woertliche Zeichen in einem
    PS-single-quoted String eingebettet: '$s.Arguments = '"pfad"'
    """
    lnk.parent.mkdir(parents=True, exist_ok=True)
    # In PS-single-quoted Strings sind " wörtliche Zeichen → korrekt für
    # den Arguments-Wert "C:\Pfad\main.py" (mit umschließenden Quotes).
    ps = (
        f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{lnk}');"
        f"$s.TargetPath='{target}';"
        f"$s.Arguments='\"{script}\"';"
        f"$s.WorkingDirectory='{script.parent}';"
        f"$s.IconLocation='{icon}';"
        f"$s.Description='VoiceDrop';"
        f"$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True,
    )


def _write_install_reg(install_dir: Path, ico: Path) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _INSTALL_REG) as k:
        winreg.SetValueEx(k, "InstallDir", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(k, "Version",    0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(k, "SourceDir",  0, winreg.REG_SZ, str(_SRC_DIR))


def _write_uninstall_reg(install_dir: Path, ico: Path) -> None:
    pythonw = _find_pythonw()
    uninstall_cmd = f'"{pythonw}" "{install_dir / "setup.py"}" --uninstall'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _UNINSTALL_KEY) as k:
        winreg.SetValueEx(k, "DisplayName",     0, winreg.REG_SZ,    APP_NAME)
        winreg.SetValueEx(k, "DisplayVersion",  0, winreg.REG_SZ,    VERSION)
        winreg.SetValueEx(k, "Publisher",       0, winreg.REG_SZ,    PUBLISHER)
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ,    str(install_dir))
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ,    uninstall_cmd)
        winreg.SetValueEx(k, "DisplayIcon",     0, winreg.REG_SZ,    str(ico))
        winreg.SetValueEx(k, "NoModify",        0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair",        0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "EstimatedSize",   0, winreg.REG_DWORD, 512)  # KB


def _set_autostart(install_dir: Path, enabled: bool) -> None:
    import importlib.util
    # autostart.py aus dem Installationsverzeichnis (oder Quellverzeichnis) laden
    src = install_dir / "autostart.py"
    if not src.exists():
        src = _SRC_DIR / "autostart.py"
    spec = importlib.util.spec_from_file_location("autostart_inst", src)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if enabled:
        mod.enable()
    else:
        mod.disable()


# ══════════════════════════════════════════════════════════════════════════════
# GUI
# ══════════════════════════════════════════════════════════════════════════════

def run_gui() -> None:
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    already = is_installed()
    inst_ver = get_installed_version()
    saved_dir = get_installed_dir()
    mode = "update" if already else "install"

    # Startwert fuer Install-Pfad
    default_dir = saved_dir if (already and saved_dir) else DEFAULT_INSTALL_DIR

    # ── Fenster ───────────────────────────────────────────────────────────────
    root = tk.Tk()
    root.title(f"VoiceDrop {VERSION} – {'Update' if mode == 'update' else 'Setup'}")
    root.resizable(False, False)
    root.configure(bg="#f0f0f0")

    W, H = 520, 470
    root.update_idletasks()
    sx = (root.winfo_screenwidth()  - W) // 2
    sy = (root.winfo_screenheight() - H) // 2
    root.geometry(f"{W}x{H}+{sx}+{sy}")

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = tk.Frame(root, bg="#1a3a6b", height=72)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="🎤  VoiceDrop",
             font=("Segoe UI", 18, "bold"), fg="white", bg="#1a3a6b"
             ).pack(side="left", padx=20, pady=14)
    tk.Label(hdr, text=f"v{VERSION}",
             font=("Segoe UI", 9), fg="#aac8ff", bg="#1a3a6b"
             ).pack(side="right", padx=16, pady=20)

    # ── Body ──────────────────────────────────────────────────────────────────
    body = tk.Frame(root, bg="#f0f0f0")
    body.pack(fill="both", expand=True, padx=24, pady=12)

    # Infotext
    if mode == "update":
        info = (
            f"Eine neuere Version ist verfuegbar.\n\n"
            f"Installierte Version:  {inst_ver}\n"
            f"Neue Version:              {VERSION}\n\n"
            f"Deine Einstellungen (API-Key, Hotkeys) bleiben erhalten."
        )
    else:
        info = (
            "VoiceDrop wird auf deinem PC eingerichtet.\n\n"
            "Waehle unten den Installationsort und die gewuenschten Optionen."
        )
    tk.Label(body, text=info,
             font=("Segoe UI", 9), bg="#f0f0f0", justify="left", anchor="w"
             ).pack(fill="x", pady=(0, 10))

    # ── Installationsort ──────────────────────────────────────────────────────
    dir_frame = tk.LabelFrame(body, text="Installationsort",
                               bg="#f0f0f0", font=("Segoe UI", 9, "bold"),
                               padx=10, pady=8)
    dir_frame.pack(fill="x", pady=(0, 8))

    dir_var = tk.StringVar(value=str(default_dir))

    dir_entry = tk.Entry(dir_frame, textvariable=dir_var,
                          font=("Segoe UI", 9), width=46)
    dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    def _browse():
        chosen = filedialog.askdirectory(
            title="Installationsordner waehlen",
            initialdir=dir_var.get(),
            parent=root,
            mustexist=False,
        )
        if chosen:
            # Benutzer hat z.B. C:\Programme gewaehlt → VoiceDrop-Unterordner anhängen
            p = Path(chosen)
            if p.name.lower() != "voicedrop":
                p = p / "VoiceDrop"
            dir_var.set(str(p))

    tk.Button(dir_frame, text="Durchsuchen …", command=_browse,
               font=("Segoe UI", 9), relief="flat", padx=8
               ).grid(row=0, column=1, sticky="e")

    dir_frame.columnconfigure(0, weight=1)

    # Hinweis
    tk.Label(dir_frame,
             text="Tipp: kein Admin nötig – %LOCALAPPDATA% ist dein persönlicher Ordner.",
             font=("Segoe UI", 8), fg="#666", bg="#f0f0f0"
             ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # ── Optionen ──────────────────────────────────────────────────────────────
    opt_frame = tk.LabelFrame(body, text="Optionen",
                               bg="#f0f0f0", font=("Segoe UI", 9, "bold"),
                               padx=10, pady=6)
    opt_frame.pack(fill="x", pady=(0, 8))

    var_start_menu = tk.BooleanVar(value=True)
    var_desktop    = tk.BooleanVar(value=False)
    var_autostart  = tk.BooleanVar(value=False)

    # Aktuellen Autostart-Status lesen
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("_as", _SRC_DIR / "autostart.py")
        _am   = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_am)
        var_autostart.set(_am.is_enabled())
    except Exception:
        pass

    for var, label in [
        (var_start_menu, "Startmenü-Eintrag erstellen"),
        (var_desktop,    "Desktop-Verknüpfung erstellen"),
        (var_autostart,  "Mit Windows starten (Autostart)"),
    ]:
        tk.Checkbutton(opt_frame, text=label, variable=var,
                        bg="#f0f0f0", font=("Segoe UI", 9)
                        ).pack(anchor="w")

    # ── Fortschritt ───────────────────────────────────────────────────────────
    prog_var = tk.DoubleVar(value=0)
    prog_msg = tk.StringVar(value="")
    prog_bar = ttk.Progressbar(body, variable=prog_var, maximum=100, length=472)
    prog_lbl = tk.Label(body, textvariable=prog_msg,
                         font=("Segoe UI", 8), fg="#555", bg="#f0f0f0")
    prog_bar.pack_forget()
    prog_lbl.pack_forget()

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_row = tk.Frame(body, bg="#f0f0f0")
    btn_row.pack(fill="x", side="bottom", pady=(4, 0))

    btn_label = "Aktualisieren" if mode == "update" else "Installieren"

    def _on_install():
        raw = dir_var.get().strip()
        if not raw:
            messagebox.showerror("Fehler", "Bitte einen Installationsordner angeben.", parent=root)
            return
        target = Path(raw)

        # Elevation prüfen bevor wir anfangen
        if _needs_elevation(target) and not _is_admin():
            if messagebox.askyesno(
                "Admin-Rechte erforderlich",
                f"Der gewählte Ordner\n  {target}\n\nbenötigt Administrator-Rechte.\n\n"
                f"Setup wird mit erhöhten Rechten neu gestartet (UAC-Dialog erscheint).\n\n"
                f"Fortfahren?",
                parent=root,
            ):
                root.destroy()
                _relaunch_as_admin()
            return

        btn_do.config(state="disabled")
        btn_cancel.config(state="disabled")
        prog_bar.pack(fill="x", pady=(6, 0))
        prog_lbl.pack(anchor="w")

        def _worker():
            try:
                def _cb(pct, msg):
                    root.after(0, lambda: (prog_var.set(pct), prog_msg.set(msg)))

                if mode == "update":
                    do_update(target, _cb)
                else:
                    do_install(
                        target, _cb,
                        create_start_menu=var_start_menu.get(),
                        create_desktop=var_desktop.get(),
                        enable_autostart=var_autostart.get(),
                    )
                root.after(0, lambda: _done(target))
            except Exception as exc:
                root.after(0, lambda e=str(exc): _error(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _done(target: Path):
        verb = "aktualisiert" if mode == "update" else "installiert"
        messagebox.showinfo(
            "VoiceDrop",
            f"VoiceDrop wurde erfolgreich {verb}!\n\n"
            f"Installationsort:\n  {target}\n\n"
            f"Du findest VoiceDrop jetzt im Startmenü.",
            parent=root,
        )
        root.destroy()

    def _error(msg: str):
        messagebox.showerror("Setup-Fehler",
                              f"Die Installation ist fehlgeschlagen:\n\n{msg}", parent=root)
        btn_do.config(state="normal")
        btn_cancel.config(state="normal")

    btn_cancel = tk.Button(btn_row, text="Abbrechen", command=root.destroy,
                            font=("Segoe UI", 10), relief="flat", padx=14, pady=6)
    btn_cancel.pack(side="right")

    btn_do = tk.Button(
        btn_row, text=btn_label, command=_on_install,
        font=("Segoe UI", 10, "bold"),
        bg="#1a3a6b", fg="white",
        activebackground="#2a5aab", activeforeground="white",
        relief="flat", padx=18, pady=6,
    )
    btn_do.pack(side="right", padx=(6, 0))

    root.mainloop()


def run_uninstall_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox

    install_dir = get_installed_dir() or DEFAULT_INSTALL_DIR

    root = tk.Tk()
    root.withdraw()

    if not messagebox.askyesno(
        "VoiceDrop deinstallieren",
        f"VoiceDrop wirklich deinstallieren?\n\n"
        f"Installationsort: {install_dir}\n\n"
        f"Deine Einstellungen (API-Key, Hotkeys) gehen dabei verloren.",
        parent=root,
    ):
        root.destroy()
        return

    def _cb(pct, msg):
        pass  # kein Fortschrittsbalken im Minimal-Dialog

    try:
        do_uninstall(install_dir, _cb)
        messagebox.showinfo("VoiceDrop",
                             "VoiceDrop wurde erfolgreich deinstalliert.",
                             parent=root)
    except Exception as exc:
        messagebox.showerror("Fehler",
                              f"Deinstallation teilweise fehlgeschlagen:\n{exc}",
                              parent=root)
    root.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--uninstall" in args:
        run_uninstall_gui()
    else:
        run_gui()
