# Avantika — Local Workspace Intelligence
> **An intelligent, poised, and privacy-first local desktop companion running natively on Windows.**

`[ Python 3.12 ]` `[ Ollama ]` `[ CustomTkinter ]` `[ Edge-TTS ]` `[ SQLite ]` `[ PyInstaller ]` `[ Windows 11 ]`

## Core Vision & Identity
Inspired by the scholarly and astronomical heritage of ancient **Avanti**, Avantika is built with a singular philosophy: **Zero-Telemetry, 100% Offline, Privacy-First Intelligence.** 

Avantika acts as your local AI companion. She assists with operating system automation, workspace task management, research, and technical inquiries with clarity, precision, and a calm, dignified tone. Because all cognitive reasoning is powered locally by Ollama, none of your conversations, tasks, or keystrokes ever leave your computer.

---

## Architectural Loop

```text
 16kHz Mic Stream
        │
        ▼
 ┌─────────────────┐       ┌─────────────────┐       ┌──────────────────┐
 │  openWakeWord   │ ────► │ Speech-to-Text  │ ────► │  SQLite Memory   │
 │ ("Avantika")    │       │ (STT / VAD)     │       │ (Bounded History)│
 └─────────────────┘       └─────────────────┘       └─────────┬────────┘
                                                               │
                                                               ▼
 ┌─────────────────┐       ┌─────────────────┐       ┌──────────────────┐
 │  Audio Barge-In │ ◄──── │  CustomTkinter  │ ◄──── │ Ollama Inference │
 │  (Esc / "Stop") │       │ Token Streaming │       │ (llama3.2 Local) │
 └─────────────────┘       └─────────▲───────┘       └─────────┬────────┘
                                     │                         │
                                     └─────────────────────────┘
                                           Edge-TTS Voice
```

---

## Key Subsystems & Features

1. **Cognitive Engine**
   - **Local LLM Streaming**: Uses `llama3.2` via Ollama for zero-credit, private inference.
   - **Performance Tuning**: Warm VRAM caching (`keep_alive="30m"`), strict context boundaries (last 6 turns), and token generation caps (`num_predict=256`).
   - **Deterministic Bypass**: System commands execute with **0ms latency**, routing directly to system utilities without waking the LLM.

2. **Adaptive Voice Pipeline**
   - **Wake-Word**: Continuous, offline background listening via `openWakeWord`. Summons via `"Avantika"` (or `"Hey Jarvis"`).
   - **Neural Voice**: Elegant conversational playback utilizing `edge-tts` (`en-IN-NeerjaNeural`).
   - **Instant Barge-In**: Interrupt the assistant mid-sentence by pressing the `Esc` key or audibly saying *"Stop"*, *"Quiet"*, or *"Pause"*.

3. **OS Automation**
   - Native detached subprocess app launcher (Chrome, VS Code, Spotify, Calc, etc.).
   - Master volume control and web search routing.
   - **System Telemetry**: Live CPU and RAM usage gauges rendered natively in the UI via `psutil`.

4. **Persistent Memory**
   - SQLite-backed dual engine (`workspace_tasks.db`).
   - Maintains your CRUD task list and preserves your multi-turn conversation history across application reboots.

5. **System Integration**
   - **System Tray**: Hides elegantly in the Windows notification area (`pystray`).
   - **Global Hotkey**: Summon the assistant from any application by pressing `Ctrl + Alt + Space` (powered directly by Win32 `ctypes`).
   - **Silent Boot**: Auto-starts seamlessly on Windows login via the `HKCU` Registry.

6. **Production Packaging**
   - Compiled into a highly optimized, standalone single-directory PyInstaller executable (`dist/Avantika/Avantika.exe`) complete with custom icons and automated Start Menu shortcut injection.

---

## Installation & Prerequisites

**Prerequisites:**
- Windows 10 / 11
- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running locally.

**Step-by-step Setup (PowerShell):**

1. **Clone & Install Dependencies**
   ```powershell
   git clone https://github.com/yourusername/Avantika-AI.git
   cd Avantika-AI
   pip install -r requirements.txt
   ```

2. **Download Local LLM**
   ```powershell
   ollama pull llama3.2
   ```

3. **(Optional) Compile Standalone Binary**
   ```powershell
   python build_app.py
   powershell -ExecutionPolicy Bypass -File .\setup_shortcut.ps1
   ```
   *Your compiled binary will be available at `dist\Avantika\Avantika.exe`.*

---

## Voice Commands & Usage Cheatsheet

| Intent | Sample Voice/Text Command | Action |
|---|---|---|
| **App Launching** | *"Open VS Code"* / *"Launch Spotify"* | Opens the application natively. |
| **Volume Control** | *"Set volume to 50"* | Adjusts Windows master volume. |
| **Task Creation** | *"Add a task to email the team"* | Creates a new persistent TODO. |
| **Task Management**| *"Complete task 1"* / *"List my tasks"* | Mutates/reads the SQLite database. |
| **Web Research** | *"Search the web for quantum physics"* | Opens your default browser. |
| **Interruption** | *"Stop"* / *"Quiet"* / (Press `Esc`) | Instantly halts the TTS voice. |
| **Global Summon** | (Press `Ctrl + Alt + Space`) | Brings Avantika to the foreground. |

---

## Project Structure

```text
Avantika/
├── main.py                   # App entry point, daemon orchestration
├── engine.py                 # LLM cognition, tool bridging, deterministic routing
├── gui.py                    # CustomTkinter interface, token streaming, telemetry
├── audio.py                  # PyAudio capture, openWakeWord, TTS synthesis, barge-in
├── tools.py                  # Python tool definitions (OS controls, search, etc.)
├── db.py                     # SQLite interface for memory and tasks
├── tray.py                   # Windows system tray minimization (pystray)
├── hotkey.py                 # Global Win32 background hotkey (ctypes)
├── autostart.py              # HKCU registry modifications for silent boot
├── build_app.py              # PyInstaller production compilation script
├── patch.py                  # Automated patching script
├── setup_shortcut.ps1        # Start Menu shortcut generator
├── configure_autostart.ps1   # PowerShell wrapper for autostart lifecycle
├── app.ico / app_logo.png    # GUI and executable branding assets
└── README.md                 # You are here
```

---

## Configuration & Hyperparameters

| File | Parameter | Description |
|---|---|---|
| `engine.py` | `num_ctx` | Context window size (Default: 2048) |
| `engine.py` | `keep_alive` | VRAM cache retention duration (Default: "30m") |
| `engine.py` | `history limit` | Max previous conversation turns (Default: 6) |
| `audio.py` | `WAKE_THRESHOLD`| openWakeWord confidence threshold (Default: 0.55) |
| `audio.py` | `_TTS_VOICE` | Edge-TTS neural voice (Default: `en-IN-NeerjaNeural`) |
| `gui.py` | `after(25)` | Tkinter event queue drain rate in ms (Default: 25) |
