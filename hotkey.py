import ctypes
import ctypes.wintypes
import threading
import time
from typing import Callable
import logging

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

# Win32 Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.wintypes.HWND),
        ("message", ctypes.wintypes.UINT),
        ("wParam", ctypes.wintypes.WPARAM),
        ("lParam", ctypes.wintypes.LPARAM),
        ("time", ctypes.wintypes.DWORD),
        ("pt", ctypes.wintypes.POINT),
    ]

class GlobalHotkeyListener:
    """Threaded system-wide global hotkey listener using native Win32 APIs."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self._thread: threading.Thread | None = None
        self._running = False
        self._hotkey_id = 1

    def _message_loop(self) -> None:
        # Register the hotkey on the current thread
        # Modifiers: Ctrl + Alt + NoRepeat
        modifiers = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
        if not user32.RegisterHotKey(None, self._hotkey_id, modifiers, VK_SPACE):
            logger.error("Failed to register global hotkey (Ctrl+Alt+Space).")
            return

        logger.info("Global hotkey (Ctrl+Alt+Space) registered successfully.")
        
        msg = MSG()
        # Message pump
        while self._running:
            # PeekMessageW is non-blocking, so we sleep to avoid high CPU usage
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    try:
                        self.callback()
                    except Exception as e:
                        logger.error("Hotkey callback error: %s", e)
                
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.05)

        # Unregister the hotkey cleanly before thread exit
        user32.UnregisterHotKey(None, self._hotkey_id)

    def start(self) -> None:
        """Start the background hotkey listener thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True, name="HotkeyListenerThread")
        self._thread.start()

    def stop(self) -> None:
        """Stop the background hotkey listener thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
