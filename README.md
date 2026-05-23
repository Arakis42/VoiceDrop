# VoiceDrop

Windows 11 speech-to-text tray app — hold a hotkey, speak, release, and the transcribed (and optionally polished) text is injected at your cursor.

## Features

| Mode | Hotkey | What it does |
|------|--------|--------------|
| 1 – Verbatim | `Ctrl+Shift+1` | Whisper transcription, injected as-is |
| 2 – Clean Text | `Ctrl+Shift+2` | Transcription cleaned up by Claude (grammar, filler words) |
| 3 – Translate EN | `Ctrl+Shift+3` | Transcription cleaned and translated to English by Claude |

Modes 2 and 3 require a Claude API key. Mode 1 is fully local and free.

## Setup

### 1. Install Python 3.11+

Download from https://www.python.org/ — make sure "Add Python to PATH" is checked during install.

### 2. Install dependencies

```
pip install -r requirements.txt
```

> **PyAudio on Windows**: if `pip install PyAudio` fails, download the matching wheel from  
> https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio  
> then install with `pip install PyAudio‑0.2.14‑cpXX‑cpXX‑win_amd64.whl`

### 3. Run the app

Double-click `start.bat`, or run:

```
python main.py
```

On first launch the Settings window opens automatically.

### 4. Download the Whisper model

In the Settings window → **Whisper Model** section → select a model → click **Download Model**.

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| tiny | ~75 MB | very fast | basic |
| base | ~150 MB | fast | good |
| small | ~480 MB | moderate | better |
| **medium** | ~1.5 GB | slower | **recommended** |
| large-v3 | ~3 GB | slow | best |

### 5. Get a Claude API key (for Modes 2 & 3)

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to **API Keys** → click **Create Key**
4. Paste the key in Settings → **Claude API Key** → click **Save**

### 6. Customize hotkeys (optional)

In Settings → **Hotkeys** → click any field → press your desired key combination.

## Usage

1. Place the cursor where you want text inserted (any text field, editor, browser, etc.)
2. Hold the hotkey for the mode you want
3. Speak clearly
4. Release the hotkey — processing starts automatically
5. Text is pasted at the cursor within a few seconds

## Requirements

- Windows 11 (Windows 10 should work too)
- Python 3.11+
- A microphone
- Internet connection only for: downloading the Whisper model (one-time) and Claude API calls (Modes 2 & 3)

## No admin rights needed

VoiceDrop uses the standard Windows clipboard + simulated Ctrl+V for text injection. No elevated permissions required.
