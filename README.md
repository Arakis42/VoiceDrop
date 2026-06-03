# VoiceDrop

Windows speech-to-text tray app — hold a hotkey, speak, release, and the transcribed (and optionally polished) text is injected at your cursor. Transcription runs **locally** with Whisper; optional clean-up/translation uses the Claude API.

## Features

| Mode | Default hotkey | What it does |
|------|----------------|--------------|
| 1 – Verbatim | `Ctrl+Shift+1` | Whisper transcription, injected as-is |
| 2 – Clean Text | `Ctrl+Shift+2` | Transcription cleaned up by Claude (grammar, filler words) — keeps the original language |
| 3 – Translate EN | `Ctrl+Shift+3` | Transcription cleaned **and** translated to English by Claude |

Mode 1 is fully local and free. Modes 2 and 3 require a Claude API key.

- **Local transcription** with OpenAI Whisper — audio is recorded to an in-memory buffer only, no temp files on disk.
- **GPU acceleration** — automatically uses CUDA if a compatible PyTorch build and GPU are available, otherwise falls back to CPU.
- **Hold-to-talk** — recording runs while the hotkey is held; releasing it starts processing. Very short presses (below a configurable minimum hold) are discarded so accidental taps don't trigger a transcription.
- **System output muting** — while recording, the default speakers/headphones are muted so background audio doesn't bleed into the mic. The previous mute state is restored afterwards. Configurable.
- **Two injection methods** — clipboard + simulated Ctrl+V (default), or character-by-character typing for environments without clipboard access (e.g. Citrix).
- **German-aware** — by default biases Whisper toward German via an initial prompt while still letting English technical terms through (configurable).
- **System tray** — status tooltip and icon change between Ready / Recording / Processing; right-click menu for settings, autostart and quit.
- **Autostart with Windows** — toggle from the tray menu (no admin rights, `HKCU\...\Run`).
- **Single instance** — starting a second copy hands over to the running one.

## Setup

### 1. Install Python 3.11+

Download from <https://www.python.org/> — make sure **"Add Python to PATH"** is checked during install.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

For **GPU acceleration** (CUDA 12.8, e.g. RTX 40/50 series), install a CUDA build of PyTorch:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

If no CUDA build is present, VoiceDrop runs on CPU automatically.

### 3. Run the app

Double-click `start.bat`, or run:

```bash
python main.py
```

On first launch the Settings window opens automatically and the app appears in the system tray.

### 4. Download the Whisper model

In Settings → **Whisper Model** → select a model → click **Download Model**.

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| tiny | ~75 MB | very fast | basic |
| base | ~150 MB | fast | good |
| small | ~480 MB | moderate | better |
| **medium** | ~1.5 GB | slower | **recommended (default)** |
| large-v3 | ~3 GB | slow | best |

### 5. Get a Claude API key (for Modes 2 & 3)

1. Go to <https://console.anthropic.com/>
2. Sign up or log in
3. **API Keys** → **Create Key**
4. Paste the key in Settings → **Claude API Key** → **Save**

The key is stored locally in your per-user config (see [Where settings live](#where-settings-live)) and is sent only to Anthropic's API when you use Mode 2 or 3.

### 6. Customize hotkeys (optional)

In Settings → **Hotkeys** → click any field → press your desired key combination.

## Usage

1. Place the cursor where you want text inserted (any text field, editor, browser, etc.).
2. Hold the hotkey for the mode you want.
3. Speak clearly.
4. Release the hotkey — processing starts automatically.
5. Text is pasted at the cursor within a few seconds.

## Settings

Beyond hotkeys, model and API key, the following can be configured (Settings window / `config.json`):

| Setting | Default | Purpose |
|---------|---------|---------|
| `injection_method` | `clipboard` | `clipboard` (Ctrl+V) or `type` (character-by-character, for Citrix) |
| `injection_delay_ms` | `150` | Delay before the paste/type is sent |
| `mute_during_recording` | `true` | Mute system output while recording |
| `mute_release_delay_ms` | `100` | Delay before restoring system audio after recording |
| `min_hold_duration_ms` | `250` | Presses shorter than this are discarded |
| `whisper_language` | `de` | Whisper language (`de` + a prompt enables per-segment auto-detect) |
| `whisper_initial_prompt` | German/IT prompt | Biases Whisper toward your domain vocabulary |

## Installer (optional)

Instead of running from source you can install a copy:

```bash
python setup.py            # GUI installer / updater
python setup.py --silent   # silent install to %LOCALAPPDATA%\VoiceDrop
python setup.py --uninstall
```

The installer copies the source files to the install directory. It elevates automatically (via `runas`) only if the chosen target requires admin rights. Your settings are **never** copied — they always live in `%APPDATA%` and survive installs and updates.

## Where settings live

- **Config**: `%APPDATA%\VoiceDrop\config.json` (per-user, survives installs)
- **Log**: `%LOCALAPPDATA%\VoiceDrop\voicedrop.log`

`config.json` is git-ignored and never committed.

## Requirements

- Windows 11 (Windows 10 should work too)
- Python 3.11+
- A microphone
- Internet only for: downloading the Whisper model (one-time) and Claude API calls (Modes 2 & 3)

## No admin rights needed

VoiceDrop runs without elevated permissions. Text injection uses the standard Windows clipboard + simulated Ctrl+V (or simulated typing). Admin is only ever requested if you install into a protected location like `Program Files`.

## How it works

```
hotkey held        → record audio to in-memory WAV (16 kHz mono)
hotkey released    → Whisper transcribes locally (GPU if available)
mode 2 / 3         → Claude API cleans up / translates the text
                   → result injected at the cursor
```

Tech stack: `openai-whisper`, `pynput`, `pystray` + `Pillow`, `tkinter`, `sounddevice` + `soundfile`, `anthropic`, `pyperclip`, `pycaw`/`comtypes` (audio muting).
</content>
</invoke>
