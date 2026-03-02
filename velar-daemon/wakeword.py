import logging
import time

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16kHz — openwakeword required minimum


class WakeWordListener:
    def __init__(self, on_wake, sensitivity: float = 0.5, audio_device_index=None):
        self.on_wake = on_wake
        self.sensitivity = sensitivity
        self.audio_device_index = audio_device_index
        self.paused = False
        # inference_framework='onnx' required for macOS ARM64 (tflite not available on arm64)
        self._model = Model(wakeword_models=["hey jarvis"], inference_framework="onnx")
        logger.info("WakeWordListener initialized (sensitivity=%.2f)", sensitivity)

    def run(self):
        """Blocking loop — must be called on a daemon background thread."""
        logger.info("Wake word listener starting")
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SAMPLES,
            device=self.audio_device_index,
        ) as stream:
            logger.info("Microphone stream open")
            while True:
                if self.paused:
                    time.sleep(0.1)
                    continue
                audio_chunk, _ = stream.read(CHUNK_SAMPLES)
                prediction = self._model.predict(audio_chunk.flatten())
                score = prediction.get("hey jarvis", 0.0)
                if score >= self.sensitivity:
                    logger.info("Wake word detected (score=%.3f)", score)
                    self._model.reset()  # prevent re-trigger on same frame
                    self.on_wake()
