import io
import logging
import wave

import requests

logger = logging.getLogger(__name__)


def post_voice_audio(audio_pcm_bytes: bytes, backend_url: str, auth_token: str) -> bytes:
    """POST raw PCM audio to /api/v1/voice. Returns MP3 bytes from backend.

    The backend accepts WAV/audio via multipart upload. We wrap PCM bytes as a
    .wav file using a minimal WAV header so faster-whisper can decode it.
    Raises requests.HTTPError on 4xx/5xx responses.
    """
    # Wrap raw int16 PCM in a WAV container
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(16000)
        wf.writeframes(audio_pcm_bytes)
    wav_bytes = wav_buf.getvalue()

    url = f"{backend_url.rstrip('/')}/api/v1/voice"
    headers = {"Authorization": f"Bearer {auth_token}"}
    files = {"audio": ("utterance.wav", wav_bytes, "audio/wav")}

    logger.info("POSTing %d bytes of audio to %s", len(wav_bytes), url)
    resp = requests.post(url, files=files, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.content  # MP3 bytes
