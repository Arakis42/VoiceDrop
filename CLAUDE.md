# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# From source directory (development)
python main.py

# Install / update the installed copy
python setup.py          # GUI installer
python setup.py --uninstall

# Silent install to default location (%LOCALAPPDATA%\VoiceDrop)
python setup.py --silent
```

There are no tests and no build step. The app runs directly from source.

## Installing dependencies

```bash
pip install -r requirements.txt
# For GPU acceleration (CUDA 12.8, RTX 40/50 series):
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

## Architecture

### Threading model — critical constraint
`tkinter` must own the **main thread**. `pystray` runs on a **daemon thread**. Violating this causes `Tcl_AsyncDelete` crashes.

```
Main thread:      tkinter hidden root → root.mainloop()
Daemon thread:    pystray icon.run()
Daemon thread:    pynput keyboard.Listener (OS hook)
  └─ short-lived threads: hotkey start/stop callbacks
Daemon thread:    Whisper model load (one-time at startup)
Daemon thread:    Recording loop (while hotkey held)
Daemon thread:    Processing pipeline (transcribe → Claude → inject)
Daemon thread:    Config window (tk.Toplevel, not tk.Tk)
```

All UI updates from background threads must go through `_main_root.after(0, fn)` — never call tkinter directly from a non-main thread.

### Data flow for a recording
1. `hotkeys.py` fires `on_record_start(mode)` → `recorder.start_recording()`
2. On key release → `recorder.stop_recording()` returns `io.BytesIO` WAV
3. `transcriber.transcribe(buffer)` → raw text (Whisper, GPU if available)
4. Mode 2/3: `processor.process(text, mode)` → Claude API
5. `inject_text(text)` → clipboard → pynput Ctrl+V simulation

### File responsibilities

| File | Purpose |
|------|---------|
| `main.py` | Entry point, `AppState`, `inject_text`, tray menu |
| `config.py` | JSON persistence singleton; reads/writes `%APPDATA%\VoiceDrop\config.json` |
| `hotkeys.py` | pynput hold/release detection; VK-code based key normalisation |
| `recorder.py` | `sounddevice` → in-memory WAV at 16 kHz mono |
| `transcriber.py` | Whisper load + transcribe; `torch.cuda.empty_cache()` on model switch |
| `processor.py` | Claude API for modes 2 & 3 |
| `ui.py` | tkinter `Toplevel` settings window; all updates via `_main_root.after()` |
| `icons.py` | PIL-generated tray icons + `save_ico_file()` for `.ico` |
| `single_instance.py` | Windows named mutex; second instance shows dialog and exits |
| `autostart.py` | `HKCU\...\Run` registry; no admin required |
| `setup.py` | GUI installer/updater; elevation via `ShellExecuteW` when needed |
| `version.py` | Single source of truth for version string |

### Config file locations
- **Active config**: `%APPDATA%\VoiceDrop\config.json` (writable by user, survives installs)
- **Log file**: `%LOCALAPPDATA%\VoiceDrop\voicedrop.log`
- The install directory (e.g. `Program Files`) is **read-only** at runtime — never write next to `main.py`

### Injection methods
- `clipboard`: pyperclip + Ctrl+V simulation (default). Does not work in Citrix (no clipboard access). Delay configurable via `injection_delay_ms`.
- `type`: pynput `kb.type(text)` — character-by-character via SendInput. Works in Citrix. Configured via `injection_method` and `injection_delay_ms` in config.

### Language / Whisper behaviour
When `whisper_language == "de"` **and** `whisper_initial_prompt` is set, `language` is passed as `None` (auto-detect per segment) and the prompt biases Whisper toward German while still allowing English technical terms through. Setting `whisper_language` to anything else, or clearing the prompt, uses standard Whisper behaviour.

### Hotkey capture in UI
`_on_capture_keypress` in `ui.py` uses tkinter keysyms. Digits pressed with Shift arrive as `"exclam"`, `"at"`, etc. — mapped back to digits via `_SHIFTED_DIGIT_MAP`. German keyboard variants are included.

### Installer / update workflow
`setup.py` copies source `.py` files to the install directory. `config.json` is **never** copied — user settings live exclusively in `%APPDATA%`. On update, only code files are overwritten. If the target directory requires admin (e.g. Program Files), `setup.py` detects this via a write-test and re-launches itself via `ShellExecuteW` with `"runas"`.
