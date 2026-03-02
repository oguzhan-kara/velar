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
        """Called from wake word listener thread. Dispatch pipeline on separate thread."""
        # Return from listener thread immediately so it can detect next wake word
        threading.Thread(target=self._run_voice_pipeline, daemon=True).start()

    def _run_voice_pipeline(self):
        """Full voice pipeline: chime -> capture -> POST -> playback. Runs on its own thread."""
        from chime import play_chime, play_cancelled, play_audio_response
        from audio_capture import capture_utterance
        from backend_client import post_voice_audio

        try:
            # 1. Chime — immediate feedback that wake word was heard
            self.title = ICON_LISTENING
            play_chime()

            # 2. Capture utterance with VAD
            audio_bytes = capture_utterance(self._config.audio_device_index)
            if audio_bytes is None:
                # No speech in 3s — play cancelled tone and return to idle
                play_cancelled()
                self.title = ICON_IDLE
                return

            # 3. POST to backend
            self.title = ICON_PROCESSING
            mp3_bytes = post_voice_audio(
                audio_pcm_bytes=audio_bytes,
                backend_url=self._config.backend_url,
                auth_token=self._config.auth_token,
            )

            # 4. Play response
            self.title = ICON_IDLE
            play_audio_response(mp3_bytes)

        except Exception as exc:
            logger.error("Voice pipeline failed: %s", exc)
            self.title = ICON_ERROR
            time.sleep(3)  # show error briefly
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
