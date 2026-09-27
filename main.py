"""Application entry point orchestrating continuous background listener, GUI, and local LLM."""

import logging
import queue
import threading
import audio
from engine import AgentEngine
from gui import AssistantGUI

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def process_command_task(
    command: str, ui_queue: queue.Queue, engine: AgentEngine
) -> None:
    """Execute command reasoning via AgentEngine and handle TTS in worker thread."""
    clean_cmd = command.strip()
    if not clean_cmd:
        ui_queue.put(("STATUS", "Idle (Listening)"))
        return

    ui_queue.put(("USER", command))
    ui_queue.put(("STATUS", "Processing..."))

    # Local LLM reasoning & tool-dispatching with guardrails
    reply = engine.process_query(clean_cmd)

    ui_queue.put(("ASSISTANT", reply))
    audio.speak(reply)
    ui_queue.put(("STATUS", "Idle (Listening)"))


def dispatch_text_command(
    command: str, ui_queue: queue.Queue, engine: AgentEngine
) -> None:
    """Spawn background thread for text or voice command processing."""
    threading.Thread(
        target=process_command_task,
        args=(command, ui_queue, engine),
        daemon=True,
        name="CommandWorkerThread",
    ).start()


def _settings_consumer(
    settings_queue: queue.Queue, engine: AgentEngine, stop_event: threading.Event
) -> None:
    """Background thread: apply SETTINGS_CHANGE and CHAT_CLEAR events from the GUI."""
    while not stop_event.is_set():
        try:
            event_type, payload = settings_queue.get(timeout=0.5)
            if event_type == "SETTINGS_CHANGE":
                if "speech_rate" in payload:
                    audio.set_speech_rate(int(payload["speech_rate"]))
                if "speech_volume" in payload:
                    audio.set_speech_volume(float(payload["speech_volume"]))
            elif event_type == "CHAT_CLEAR":
                engine.clear_history()
                logger.info("Chat history cleared via GUI trigger.")
            settings_queue.task_done()
        except queue.Empty:
            continue


def main() -> None:
    """Initialize watchdog, autonomous listener, settings consumer, and start GUI."""
    ui_queue: queue.Queue = queue.Queue()
    settings_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    # Initialize zero-credit local agent engine with live status callbacks
    agent_engine = AgentEngine(
        status_notifier=lambda s: ui_queue.put(("STATUS", s))
    )

    # Watchdog handlers for continuous audio listener
    def on_autonomous_voice_input(recognized_text: str) -> None:
        logger.info("Autonomous speech captured: %s", recognized_text)
        dispatch_text_command(recognized_text, ui_queue, agent_engine)

    def on_mic_error(exc: Exception) -> None:
        logger.warning("Microphone error caught by watchdog: %s", exc)
        ui_queue.put(("STATUS", "Mic disconnected. Reconnecting in 3s..."))
        ui_queue.put(("SYSTEM", f"Audio device warning: {exc}. Retrying in 3 seconds..."))

    def on_listener_status(status_text: str) -> None:
        ui_queue.put(("STATUS", status_text))

    def on_audio_level(level: float) -> None:
        """Forward normalized RMS amplitude to GUI meter via thread-safe queue."""
        ui_queue.put(("AUDIO_LEVEL", level))

    # Bridge SETTINGS_CHANGE events from shared ui_queue → settings_queue for the consumer thread.
    # We wrap the GUI's queue so settings events are intercepted and forwarded.
    class _SettingsBridgeQueue(queue.Queue):
        """Proxy queue that intercepts SETTINGS_CHANGE / CHAT_CLEAR and forwards to consumer."""
        def put(self, item, block=True, timeout=None):
            super().put(item, block=block, timeout=timeout)
            if isinstance(item, tuple) and len(item) == 2:
                etype, payload = item
                if etype in ("SETTINGS_CHANGE", "CHAT_CLEAR"):
                    settings_queue.put((etype, payload))

    bridge_queue: queue.Queue = _SettingsBridgeQueue()

    # Start settings consumer daemon
    settings_thread = threading.Thread(
        target=_settings_consumer,
        args=(settings_queue, agent_engine, stop_event),
        daemon=True,
        name="SettingsConsumerThread",
    )
    settings_thread.start()

    # Start persistent autonomous wakeword background listener
    audio.start_wakeword_listener(
        on_wake_callback=lambda: ui_queue.put(("STATUS", "Listening...")),
        on_command_captured=on_autonomous_voice_input,
        level_callback=on_audio_level,
    )

    # Launch GUI with bridge queue
    app = AssistantGUI(
        event_queue=bridge_queue,
        on_send_callback=lambda cmd: dispatch_text_command(cmd, bridge_queue, agent_engine),
        on_speak_callback=lambda: dispatch_text_command(
            audio.listen_command(), bridge_queue, agent_engine
        ),
    )
    
    import sys
    if "--minimized" in sys.argv:
        # Hide the root window so it starts silently in background
        app.root.withdraw()
        
    def _on_hotkey_triggered():
        app.bring_to_front()
        # Enqueue a synthetic speak trigger
        audio.stop_playback()
        threading.Thread(
            target=lambda: dispatch_text_command(audio.listen_command(), bridge_queue, agent_engine),
            daemon=True
        ).start()

    from hotkey import GlobalHotkeyListener
    from tray import SystemTrayApp
    
    def _quit_app():
        stop_event.set()
        hotkey_listener.stop()
        app.root.quit()

    tray_app = SystemTrayApp(
        app_name="Avantika Assistant",
        on_show=lambda: app.root.after(0, app.bring_to_front),
        on_quit=lambda: app.root.after(0, _quit_app)
    )
    tray_app.start()

    hotkey_listener = GlobalHotkeyListener(lambda: app.root.after(0, _on_hotkey_triggered))
    hotkey_listener.start()

    app.start()

    # Cleanup on GUI close (if not closed via tray)
    stop_event.set()
    hotkey_listener.stop()
    tray_app.stop()


if __name__ == "__main__":
    main()
