"""
build_app.py — PyInstaller build driver for Local AI Assistant.
Produces dist/LocalAIAssistant/LocalAIAssistant.exe (onedir, no console).
"""

import os
import subprocess
import sys


def resolve_package_dir(package_name: str) -> str:
    """Return the filesystem directory of an installed package."""
    try:
        mod = __import__(package_name)
        return os.path.dirname(mod.__file__)
    except ImportError as e:
        raise SystemExit(f"[ERROR] Required package not importable: {package_name} — {e}")


def main() -> None:
    print("=" * 60)
    print(" Local AI Assistant — PyInstaller Build")
    print("=" * 60)

    # ── Resolve data asset paths ──────────────────────────────────
    ctk_path      = resolve_package_dir("customtkinter")
    edge_tts_path = resolve_package_dir("edge_tts")
    pygame_path   = resolve_package_dir("pygame")
    ollama_path   = resolve_package_dir("ollama")

    print(f"[INFO] customtkinter : {ctk_path}")
    print(f"[INFO] edge_tts      : {edge_tts_path}")
    print(f"[INFO] pygame        : {pygame_path}")
    print(f"[INFO] ollama        : {ollama_path}")

    # ── PyInstaller arguments ─────────────────────────────────────
    # Separator is ';' on Windows (os.pathsep)
    sep = os.pathsep

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "main.py",
        "--name",        "Avantika",
        "--onedir",
        "--windowed",
        "--noconsole",
        "--noconfirm",
        "--clean",
        # Custom Icon
        "--icon",        "app.ico",
        # Data assets
        "--add-data",    f"{ctk_path}{sep}customtkinter",
        "--add-data",    f"{edge_tts_path}{sep}edge_tts",
        "--add-data",    f"{pygame_path}{sep}pygame",
        "--add-data",    f"{ollama_path}{sep}ollama",
        "--add-data",    f"app.ico{sep}.",
        "--add-data",    f"app_logo.png{sep}.",
    ]
    
    if os.path.exists("avantika.onnx"):
        cmd.extend(["--add-data", f"avantika.onnx{sep}."])
        
    cmd.extend([
        # Hidden imports
        "--hidden-import", "customtkinter",
        "--hidden-import", "edge_tts",
        "--hidden-import", "pygame",
        "--hidden-import", "pygame.mixer",
        "--hidden-import", "pygame.mixer_music",
        "--hidden-import", "ollama",
        "--hidden-import", "pyjokes",
        "--hidden-import", "pywhatkit",
        "--hidden-import", "wikipedia",
        "--hidden-import", "speech_recognition",
        "--hidden-import", "pyaudio",
        "--hidden-import", "aiohttp",
        "--hidden-import", "certifi",
        "--hidden-import", "psutil",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "openwakeword",
        "--hidden-import", "db",
        "--hidden-import", "sqlite3",
        "--hidden-import", "tools",
        "--hidden-import", "audio",
        "--hidden-import", "gui",
        "--hidden-import", "engine",
        "--hidden-import", "autostart",
        "--hidden-import", "hotkey",
        # Collect all submodules for packages with dynamic internal imports
        "--collect-all", "customtkinter",
        "--collect-all", "edge_tts",
        "--collect-all", "pygame",
        "--collect-all", "ollama",
        "--collect-all", "pyjokes",
        "--collect-all", "psutil",
        "--collect-all", "openwakeword",
        # Project source modules
        "--paths",       ".",
    ])

    print("\n[INFO] Running PyInstaller...\n")
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

    if result.returncode != 0:
        raise SystemExit(f"[FAIL] PyInstaller exited with code {result.returncode}")

    # ── Post-build verification ───────────────────────────────────
    exe_path = os.path.join("dist", "Avantika", "LocalAIAssistant.exe")
    if not os.path.isfile(exe_path):
        raise SystemExit(f"[FAIL] Expected executable not found: {exe_path}")

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"\n[OK] Executable : {exe_path} ({size_mb:.1f} MB)")

    # Check CustomTkinter theme assets are bundled
    ctk_internal_paths = [
        os.path.join("dist", "Avantika", "_internal", "customtkinter"),
        os.path.join("dist", "Avantika", "customtkinter"),
    ]
    ctk_bundled = next((p for p in ctk_internal_paths if os.path.isdir(p)), None)
    if ctk_bundled:
        print(f"[OK] CustomTkinter assets : {ctk_bundled}")
    else:
        print("[WARN] CustomTkinter assets directory not found at expected paths — verify manually.")

    print("\n[OK] Build complete. Distribution ready at: dist/LocalAIAssistant/")


if __name__ == "__main__":
    main()

