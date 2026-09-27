import os
import sys
import winreg

APP_NAME = "AvantikaAIAssistant"

def get_launch_command() -> str:
    """Return the absolute path to the executable with the --minimized flag."""
    # Assuming this script is run from the project root, or we're compiled.
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        # Fallback for development script mode
        base_dir = os.path.dirname(os.path.abspath(__file__))
        exe_path = os.path.join(base_dir, "dist", "Avantika", "Avantika.exe")
        if not os.path.exists(exe_path):
            exe_path = sys.executable + ' "' + os.path.join(base_dir, "main.py") + '"'
            
    return f'"{exe_path}" --minimized'

def is_autostart_enabled() -> bool:
    """Check if the app is registered in HKCU Run key."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

def set_autostart(enable: bool) -> bool:
    """Enable or disable Windows startup registry key for the app."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                cmd = get_launch_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"Failed to set autostart: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "enable":
            set_autostart(True)
            print("Autostart Enabled.")
        elif sys.argv[1] == "disable":
            set_autostart(False)
            print("Autostart Disabled.")
        elif sys.argv[1] == "status":
            enabled = is_autostart_enabled()
            print(f"Autostart Status: {'Enabled' if enabled else 'Disabled'}")

