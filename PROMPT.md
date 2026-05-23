# VoiceDrop – Windows Speech-to-Text Tray App

## Project Goal
Build a Windows 11 tray application in Python that records audio via a global hotkey,
transcribes it locally with Whisper, optionally polishes or translates the text via
Claude API, and injects the result at the current cursor position.

---

## Tech Stack
- Python 3.11+
- openai-whisper (local, no cloud)
- pynput (global hotkeys)
- pystray + Pillow (system tray)
- tkinter (config window – already bundled with Python)
- pyaudio (microphone recording)
- anthropic (Claude API SDK for Mode 2 & 3)
- keyboard (text injection at cursor via pyperclip + simulated Ctrl+V)
- pyperclip (clipboard interaction)
- python-dotenv (local config persistence)

---

## Project Structure
Create the following layout:
voicedrop/
├── main.py              # Entry point, tray setup
├── recorder.py          # Microphone recording logic
├── transcriber.py       # Whisper transcription
├── processor.py         # Claude API calls (Mode 2 & 3)
├── hotkeys.py           # Global hotkey registration via pynput
├── config.py            # Load/save config (JSON file)
├── ui.py                # Config window (tkinter)
├── config.json          # Created at first run, gitignored
├── requirements.txt
└── README.md

---

## Core Features

### System Tray
- App lives in the system tray (bottom-right Windows taskbar)
- Tray icon has a right-click menu with:
  - "Settings" → opens Config Window
  - "Quit" → exits cleanly
- Tray icon changes color/state while recording (e.g. red dot)

### Recording Behavior
- Hold hotkey → recording starts
- Release hotkey → recording stops, processing begins
- Visual feedback: tray icon changes while recording
- Audio is recorded to a temporary in-memory buffer (no temp files on disk)

### Three Modes (each with its own hotkey)

**Mode 1 – Verbatim**
- Whisper transcription output, as-is
- No API call needed
- Inject result at cursor

**Mode 2 – Clean Text (German)**
- Whisper transcription
- Send to Claude API with this system prompt:
You are a text editor. The user dictated the following text.
Clean it up: fix grammar, remove filler words, improve flow.
Keep the original language. Keep the meaning and tone.
Return only the cleaned text, no explanations.
- Inject result at cursor

**Mode 3 – Clean + Translate to English**
- Whisper transcription
- Send to Claude API with this system prompt:
You are a text editor and translator. The user dictated the following text.
First clean it up: fix grammar, remove filler words, improve flow.
Then translate the cleaned text into natural English.
Return only the final English text, no explanations.
- Inject result at cursor

### Text Injection
- Copy result to clipboard
- Simulate Ctrl+V at the current cursor position
- Restore previous clipboard content after 2 seconds

---

## Config Window (tkinter)

Build a simple settings window with these sections:

### Hotkeys
- Three labeled input fields: Mode 1, Mode 2, Mode 3
- Each shows the current hotkey (e.g. "ctrl+shift+1")
- Click field → press new key combo → saved automatically
- Default hotkeys: Ctrl+Shift+1 / Ctrl+Shift+2 / Ctrl+Shift+3

### Claude API Key
- Labeled input field (password-masked)
- "Save" button
- Below the field: a clearly visible help text:
No API key yet? Get one here: https://console.anthropic.com/
Steps: Sign up → Go to "API Keys" → Click "Create Key" → Paste here.
Mode 1 works without an API key. Modes 2 and 3 require one.

### Whisper Model
- Dropdown showing: tiny, base, small, medium, large-v3
- Pre-selected: medium
- "Download model" button that triggers download with a progress indicator

### Status / Info
- Show current status: "Ready", "Recording...", "Processing..."
- Show which model is loaded

---

## Config Persistence
- Save all settings to `config.json` in the app directory
- Never commit `config.json` (add to .gitignore)
- On first launch: create config.json with defaults, open Config Window automatically

---

## Setup & Installation
Create a `README.md` with step-by-step instructions:
1. Install Python 3.11+ from python.org
2. Install dependencies: `pip install -r requirements.txt`
3. Download Whisper model on first launch (via Config Window)
4. Get Claude API key (link + steps explained in Config Window)
5. Set hotkeys in Config Window
6. Run: `python main.py`

Also create a `start.bat` for easy launch on Windows:
```bat
@echo off
python main.py
pause
```

---

## Error Handling
- No microphone found → show popup with helpful message
- No API key set for Mode 2/3 → show popup: "Please add your Claude API key in Settings"
- Claude API error → show popup with error message, don't crash
- Whisper model not downloaded → show popup: "Please download the Whisper model in Settings first"

---

## Requirements
Generate a `requirements.txt` with pinned versions for:
openai-whisper, pynput, pystray, Pillow, pyaudio, anthropic, pyperclip, python-dotenv

---

## Implementation Notes
- Use threading for recording + transcription (never block the tray/UI)
- Whisper model is loaded once at startup and kept in memory
- All Claude API calls use: model="claude-sonnet-4-6", max_tokens=2048
- App must not require admin rights to run
- Target OS: Windows 11
- No installer needed – runs directly with `python main.py`

---

## Start
Begin with:
1. Create the full project structure
2. Implement `config.py` and `config.json` defaults
3. Implement `ui.py` (Config Window) with API key onboarding
4. Implement `recorder.py`
5. Implement `transcriber.py` (load Whisper medium)
6. Implement `processor.py` (Claude API for Mode 2 & 3)
7. Implement `hotkeys.py`
8. Implement `main.py` with tray

Test each component before moving to the next.