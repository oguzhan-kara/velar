# -*- coding: utf-8 -*-
import signal
import threading
import logging
import time

import rumps
from config import load_config
from wakeword import WakeWordListener

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Menu bar icon state constants
ICON_IDLE = "●"        # gray dot — waiting for wake word
ICON_LISTENING = "◉"   # blue — speech being captured
ICON_PROCESSING = "⟳"  # spinning — API call in progress
ICON_PAUSED = "⊘"      # muted — wake word paused
ICON_ERROR = "⚠"       # warning — backend unreachable


class VelarDaemon(rumps.App):
    def __init__(self):
        super().__init__("VELAR", title=ICON_IDLE)
        self._config = load_config()
        self._listener = WakeWordListener(
            on_wake=self._on_wake,
            sensitivity=self._config.wake_sensitivity,
            audio_device_index=self._config.audio_device_index,
        )
        self._paused = False
        self.menu = [
            rumps.MenuItem("Pause Wake Word", callback=self.toggle_pause),
            None,  # separator
            rumps.MenuItem("About VELAR", callback=self._show_about),
        ]
        signal.signal(signal.SIGTERM, self._sigterm_handler)

    def application_will_finish_launching_(self, notification):
        """Called after NSApplication main loop starts — safe to start background threads."""
        t = threading.Thread(target=self._listener.run, daemon=True)
        t.start()
        logger.info("Wake word listener thread started")

    def _on_wake(self):
        """Called from audio background thread when wake word detected."""
        self.title = ICON_LISTENING
        # Phase 04-02 wires audio capture + backend POST here.
        # For now, log and return to idle after 2s (smoke-test hook).
        logger.info("Wake word fired — audio capture pending (Phase 04-02)")
        time.sleep(2)
        self.title = ICON_IDLE

    @rumps.clicked("Pause Wake Word")
    def toggle_pause(self, sender):
        self._paused = not self._paused
        sender.state = self._paused
        self._listener.paused = self._paused
        self.title = ICON_PAUSED if self._paused else ICON_IDLE
        logger.info("Wake word %s", "paused" if self._paused else "resumed")

    def _show_about(self, _):
        rumps.alert(
            "VELAR",
            f"Backend: {self._config.backend_url}\nSensitivity: {self._config.wake_sensitivity}",
        )

    def _sigterm_handler(self, signum, frame):
        logger.info("SIGTERM received — shutting down")
        self._listener.paused = True
        rumps.quit_application()


if __name__ == "__main__":
    VelarDaemon().run()
