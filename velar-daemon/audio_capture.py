import logging
import time

import numpy as np
import sounddevice as sd
import torch
from silero_vad import load_silero_vad

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280        # 80ms at 16kHz
MAX_RECORDING_SECS = 8      # hard timeout per CONTEXT.md
SILENCE_TIMEOUT_SECS = 1.5  # stop after 1.5s silence post-speech
NO_SPEECH_TIMEOUT_SECS = 3  # cancel if no speech within 3s of wake

# Load Silero VAD once at module level — not per-capture
_vad_model = load_silero_vad()


def _is_speech(chunk_bytes: bytes) -> bool:
    arr = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    tensor = torch.from_numpy(arr).unsqueeze(0)
    prob = _vad_model(tensor, SAMPLE_RATE).item()
    return prob > 0.5


def capture_utterance(audio_device_index=None) -> bytes | None:
    """Record from microphone until speech ends or timeout. Returns PCM bytes or None."""
    frames = []
    speech_started = False
    last_speech_time = None
    start_time = time.time()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=CHUNK_SAMPLES,
        device=audio_device_index,
    ) as stream:
        while True:
            elapsed = time.time() - start_time
            if elapsed > MAX_RECORDING_SECS:
                logger.info("Max recording time reached")
                break
            if not speech_started and elapsed > NO_SPEECH_TIMEOUT_SECS:
                logger.info(
                    "No speech detected within %.1fs — cancelling", NO_SPEECH_TIMEOUT_SECS
                )
                return None  # Caller plays cancelled tone

            chunk, _ = stream.read(CHUNK_SAMPLES)
            chunk_bytes = chunk.tobytes()
            frames.append(chunk_bytes)

            if _is_speech(chunk_bytes):
                speech_started = True
                last_speech_time = time.time()
            elif speech_started:
                silence_secs = time.time() - last_speech_time
                if silence_secs >= SILENCE_TIMEOUT_SECS:
                    logger.info("Speech ended after %.1fs silence", silence_secs)
                    break

    return b"".join(frames) if speech_started else None
