import os
import threading
import pystray
from PIL import Image

class SystemTrayApp:
    """Minimal system tray application using pystray."""
    def __init__(self, app_name: str, on_show: callable, on_quit: callable):
        self.app_name = app_name
        self.on_show = on_show
        self.on_quit = on_quit
        self.icon = None

    def _create_icon(self):
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_logo.png")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
            
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
            else:
                # Fallback blank image
                image = Image.new('RGB', (64, 64), color=(0, 0, 0))
        except Exception:
            image = Image.new('RGB', (64, 64), color=(0, 0, 0))
            
        menu = pystray.Menu(
            pystray.MenuItem("Show Assistant", self._on_show_clicked, default=True),
            pystray.MenuItem("Quit", self._on_quit_clicked)
        )
        self.icon = pystray.Icon("name", image, self.app_name, menu)

    def _on_show_clicked(self, icon, item):
        self.on_show()

    def _on_quit_clicked(self, icon, item):
        self.icon.stop()
        self.on_quit()

    def start(self):
        self._create_icon()
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self):
        if self.icon:
            self.icon.stop()
