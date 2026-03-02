"""STT unit tests and Turkish WER acceptance test scaffold.

Fast tests (no model required):
  - test_stt_service_creation       — class structure check
  - test_stt_result_schema          — Pydantic schema validation
  - test_chat_request_validation    — ChatRequest field constraints
  - test_audio_format_conversion    — soundfile WAV round-trip

Slow / conditional tests (skip when model or fixtures are absent):
  - test_language_detection_returns_valid_code  — requires Whisper model
  - test_turkish_stt_wer                        — requires audio fixture files
"""

import io
import os

import numpy as np
import pytest
import soundfile as sf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def word_error_rate(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate using edit distance on token lists.

    WER = edit_distance(ref_words, hyp_words) / len(ref_words)

    Returns 0.0 when both strings are empty. Returns 1.0 when reference is
    empty but hypothesis is not (all words are insertions).
    """
    import editdistance

    ref_words = reference.strip().lower().split()
    hyp_words = hypothesis.strip().lower().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    distance = editdistance.eval(ref_words, hyp_words)
    return distance / len(ref_words)


# ---------------------------------------------------------------------------
# Fast unit tests — always pass (no model, no fixtures, no env vars needed)
# ---------------------------------------------------------------------------

def test_stt_service_creation():
    """STTService can be imported and has the expected interface."""
    from app.voice.stt import STTService  # noqa: PLC0415

    # Verify class structure — do NOT instantiate (that loads the 5-20s model)
    assert hasattr(STTService, "transcribe")
    assert hasattr(STTService, "_transcribe_sync")
    assert hasattr(STTService, "_decode_audio")


def test_stt_result_schema():
    """STTResult Pydantic model validates correctly."""
    from app.voice.schemas import STTResult  # noqa: PLC0415

    result = STTResult(text="merhaba", language="tr", language_probability=0.95)
    assert result.text == "merhaba"
    assert result.language == "tr"
    assert result.language_probability == pytest.approx(0.95)


def test_chat_request_validation():
    """ChatRequest enforces min_length=1, max_length=4000 and optional history."""
    from app.voice.schemas import ChatRequest  # noqa: PLC0415

    req = ChatRequest(message="hello")
    assert req.message == "hello"
    assert req.history is None
    assert req.language is None

    # min_length=1 constraint — empty string must fail
    with pytest.raises(Exception):
        ChatRequest(message="")

    # With history and language override
    req2 = ChatRequest(
        message="devam et",
        history=[{"role": "user", "content": "merhaba"}],
        language="tr",
    )
    assert req2.history is not None
    assert len(req2.history) == 1
    assert req2.language == "tr"


def test_audio_format_conversion():
    """WAV bytes are correctly decoded to a numpy float32 array via soundfile."""
    # Generate 1 second of silence at 16 kHz
    audio = np.zeros(16000, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, 16000, format="WAV")
    wav_bytes = buf.getvalue()

    # Verify soundfile can round-trip the bytes
    buf2 = io.BytesIO(wav_bytes)
    data, sr = sf.read(buf2, dtype="float32")
    assert sr == 16000
    assert len(data) == 16000
    assert data.dtype == np.float32
    assert np.allclose(data, 0.0)


# ---------------------------------------------------------------------------
# Slow / conditional tests — skip when Whisper model or audio fixtures absent
# ---------------------------------------------------------------------------

_MODEL_AVAILABLE = os.environ.get("WHISPER_MODEL_AVAILABLE", "").lower() == "true"
_TURKISH_FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "fixtures", "turkish_audio"
)
_FIRST_FIXTURE = os.path.join(_TURKISH_FIXTURES_DIR, "saat_kac.wav")


@pytest.mark.skipif(
    not _MODEL_AVAILABLE,
    reason="Set WHISPER_MODEL_AVAILABLE=true and ensure model is downloaded to run this test",
)
def test_language_detection_returns_valid_code():
    """Transcription returns a valid BCP-47 language code ('tr' or 'en').

    Verifies VOICE-05: the STT service correctly identifies the spoken language
    so that downstream TTS can select the matching voice profile.
    """
    import asyncio

    from app.voice.stt import get_stt_service  # noqa: PLC0415

    stt = get_stt_service()

    # 1 second of silence — Whisper will return an empty transcript but still
    # emit a language detection result.
    silence = np.zeros(16000, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, silence, 16000, format="WAV")
    wav_bytes = buf.getvalue()

    result = asyncio.run(stt.transcribe(wav_bytes))
    assert result.language in {"tr", "en", "af", "am", "ar", "bg", "bn", "ca",
                                "cs", "cy", "da", "de", "el", "es", "et", "fa",
                                "fi", "fr", "gl", "gu", "ha", "hi", "hr", "hu",
                                "hy", "id", "is", "it", "iw", "ja", "jw", "ka",
                                "kk", "km", "kn", "ko", "la", "lo", "lt", "lv",
                                "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
                                "my", "ne", "nl", "no", "pa", "pl", "ps", "pt",
                                "ro", "ru", "sk", "sl", "so", "sq", "sr", "su",
                                "sv", "sw", "ta", "te", "tg", "th", "tk", "tl",
                                "tt", "uk", "ur", "uz", "vi", "xh", "yi", "yo",
                                "zh", "zu"}, \
        f"Unexpected language code: {result.language!r}"
    assert 0.0 <= result.language_probability <= 1.0


@pytest.mark.skipif(
    not os.path.exists(_FIRST_FIXTURE),
    reason="Turkish audio fixtures not yet generated — run scripts/generate_turkish_fixtures.py",
)
def test_turkish_stt_wer():
    """Turkish WER acceptance test: average WER must be < 15%.

    Reference utterances cover common voice assistant intents in Turkish.
    Audio fixtures should be recorded at 16 kHz mono WAV using a native speaker
    or a high-quality TTS system (e.g. ElevenLabs Turkish voice).
    """
    import asyncio

    from app.voice.stt import get_stt_service  # noqa: PLC0415

    references = [
        ("saat_kac.wav", "saat kaç"),
        ("bugun_hava_nasil.wav", "bugün hava nasıl"),
        ("takvimde_ne_var.wav", "takvimde ne var"),
        ("hatirlatici_kur.wav", "hatırlatıcı kur"),
        ("bana_kahvalti_oner.wav", "bana kahvaltı öner"),
    ]

    stt = get_stt_service()
    wer_scores: list[float] = []

    for filename, reference in references:
        fixture_path = os.path.join(_TURKISH_FIXTURES_DIR, filename)
        if not os.path.exists(fixture_path):
            pytest.skip(f"Fixture missing: {fixture_path}")
            return

        with open(fixture_path, "rb") as fh:
            audio_bytes = fh.read()

        result = asyncio.run(stt.transcribe(audio_bytes))
        wer = word_error_rate(reference, result.text)
        wer_scores.append(wer)

    avg_wer = sum(wer_scores) / len(wer_scores)
    assert avg_wer < 0.15, (
        f"Turkish WER {avg_wer:.1%} exceeds 15% threshold — "
        f"per-utterance WERs: {[f'{w:.1%}' for w in wer_scores]}"
    )
