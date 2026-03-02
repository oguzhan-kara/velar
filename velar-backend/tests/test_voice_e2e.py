"""End-to-end integration tests for VELAR voice pipeline.

Tests verify the full pipeline using the ASGI test client with mocked
external services (Claude, ElevenLabs). No real API keys are required.

Pipeline tested:
    /voice: audio upload -> STT -> Claude -> TTS -> audio response
    /chat:  text input  -> Claude -> TTS -> JSON with audio_base64

Authentication is mocked by overriding get_current_user dependency.
Claude and TTS calls are mocked via unittest.mock.patch.
STT is mocked where needed to avoid loading the Whisper model.
"""

import base64
import io
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
import soundfile as sf
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers — sys.modules mock for app.config
# ---------------------------------------------------------------------------

def _inject_mock_config() -> None:
    """Inject minimal mock app.config so the app can be imported without .env."""
    if "app.config" not in sys.modules or not isinstance(
        sys.modules["app.config"], types.ModuleType
    ):
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.elevenlabs_api_key = ""
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_anon_key = "test-anon"
        mock_settings.supabase_jwt_secret = "test-jwt-secret-that-is-long-enough-32chars"
        mock_settings.database_url = "postgresql+asyncpg://test:test@localhost/test"
        mock_settings.whisper_model_size = "large-v3-turbo"
        mock_settings.debug = True

        mock_config_module = types.ModuleType("app.config")
        mock_config_module.settings = mock_settings
        sys.modules["app.config"] = mock_config_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_fake_wav(duration_secs: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a minimal WAV file (silence) as bytes."""
    samples = int(duration_secs * sample_rate)
    audio = np.zeros(samples, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV")
    return buf.getvalue()


def _make_fake_current_user() -> dict:
    """Return a mock CurrentUser dict for auth bypass."""
    return {"user_id": "test-user-id", "email": "test@example.com"}


@pytest_asyncio.fixture
async def app_client():
    """ASGI test client with mocked config and auth.

    Injects mock app.config before importing the FastAPI app, then overrides
    the get_current_user dependency to bypass JWT validation.
    """
    _inject_mock_config()

    # Import app after config mock is in place
    from app.main import app  # noqa: PLC0415
    from app.dependencies import get_current_user  # noqa: PLC0415

    # Override auth dependency — return fake user without touching JWT
    app.dependency_overrides[get_current_user] = lambda: _make_fake_current_user()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    # Clean up dependency override
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# /chat endpoint tests
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    """Integration tests for POST /api/v1/chat."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_with_mock_claude(self, app_client):
        """POST /chat with mocked Claude and TTS returns 200 with text and audio."""
        import app.voice.conversation as conv_module  # noqa: PLC0415
        from app.voice.tts import _LazyTTSProxy  # noqa: PLC0415

        fake_audio = b"fake-mp3-audio-bytes"

        mock_content = MagicMock()
        mock_content.text = "Bugün hava güzel!"

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"

        mock_claude_client = MagicMock()
        mock_claude_client.messages.create = MagicMock(return_value=mock_response)

        with (
            patch.object(conv_module, "_get_client", return_value=mock_claude_client),
            patch.object(_LazyTTSProxy, "synthesize", new_callable=lambda: lambda self: AsyncMock(return_value=fake_audio)) as _,
        ):
            # Patch synthesize differently to avoid lambda complexity
            with patch("app.voice.tts._LazyTTSProxy.synthesize", new=AsyncMock(return_value=fake_audio)):
                response = await app_client.post(
                    "/api/v1/chat",
                    json={"message": "Bugün hava nasıl?", "language": "tr"},
                )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert "text" in body and body["text"], "Response must have non-empty 'text'"
        assert "audio_base64" in body and body["audio_base64"], "Response must have non-empty 'audio_base64'"
        assert "detected_language" in body, "Response must have 'detected_language'"
        # Verify audio_base64 is valid base64
        decoded = base64.b64decode(body["audio_base64"])
        assert len(decoded) > 0, "Decoded audio must be non-empty"

    @pytest.mark.asyncio
    async def test_chat_with_history(self, app_client):
        """POST /chat with history passes prior turns to Claude."""
        import app.voice.conversation as conv_module  # noqa: PLC0415

        captured_messages = []

        mock_content = MagicMock()
        mock_content.text = "Evet, anlıyorum."

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        def capture_create(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return mock_response

        mock_claude_client = MagicMock()
        mock_claude_client.messages.create = MagicMock(side_effect=capture_create)

        fake_audio = b"fake-audio"

        with (
            patch.object(conv_module, "_get_client", return_value=mock_claude_client),
            patch("app.voice.tts._LazyTTSProxy.synthesize", new=AsyncMock(return_value=fake_audio)),
        ):
            response = await app_client.post(
                "/api/v1/chat",
                json={
                    "message": "Devam et",
                    "history": [
                        {"role": "user", "content": "Merhaba"},
                        {"role": "assistant", "content": "Merhaba! Nasıl yardımcı olabilirim?"},
                    ],
                    "language": "tr",
                },
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        # Verify history was included: 2 history turns + 1 current = 3 messages
        assert len(captured_messages) == 3, (
            f"Expected 3 messages (2 history + 1 current), got {len(captured_messages)}"
        )
        assert captured_messages[-1]["content"] == "Devam et", "Last message must be the current user input"

    @pytest.mark.asyncio
    async def test_chat_endpoint_missing_message_returns_422(self, app_client):
        """POST /chat without 'message' field returns 422 validation error."""
        response = await app_client.post(
            "/api/v1/chat",
            json={},  # missing 'message' field
        )
        assert response.status_code == 422, (
            f"Expected 422 validation error, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# /voice endpoint tests
# ---------------------------------------------------------------------------

class TestVoiceEndpoint:
    """Integration tests for POST /api/v1/voice."""

    @pytest.mark.asyncio
    async def test_voice_endpoint_with_mocks(self, app_client):
        """POST /voice with mocked STT and streaming pipeline returns 200 audio/mpeg.

        The /voice endpoint uses stream_conversation_to_audio (not the sequential
        run_conversation -> tts_service path). We mock the streaming function directly
        to avoid mocking the Anthropic streaming client internals.
        """
        from app.voice.schemas import STTResult  # noqa: PLC0415

        fake_wav = _make_fake_wav()
        fake_audio = b"fake-mp3-response"

        mock_stt_result = STTResult(
            text="Merhaba VELAR",
            language="tr",
            language_probability=0.97,
        )

        mock_stt_service = AsyncMock()
        mock_stt_service.transcribe = AsyncMock(return_value=mock_stt_result)

        # Mock stream_conversation_to_audio to return (text, audio_bytes) directly
        async def mock_stream(*args, **kwargs) -> tuple[str, bytes]:
            return "Merhaba, bugün güneşli.", fake_audio

        with (
            patch("app.voice.router.get_stt_service", return_value=mock_stt_service),
            patch("app.voice.router.stream_conversation_to_audio", side_effect=mock_stream),
        ):
            response = await app_client.post(
                "/api/v1/voice",
                files={"audio": ("test.wav", fake_wav, "audio/wav")},
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("content-type", "").startswith("audio/mpeg"), (
            f"Expected audio/mpeg content-type, got {response.headers.get('content-type')}"
        )
        assert "x-transcript" in response.headers, "Response must have X-Transcript header"
        assert "x-response-text" in response.headers, "Response must have X-Response-Text header"
        assert "x-detected-language" in response.headers, "Response must have X-Detected-Language header"
        assert len(response.content) > 0, "Response body must be non-empty audio bytes"

        # Transcript is the raw STT text (percent-encoded for turkish chars)
        assert response.headers["x-detected-language"] == "tr"

    @pytest.mark.asyncio
    async def test_voice_endpoint_empty_audio_returns_422(self, app_client):
        """POST /voice with empty transcript returns 422 with 'No speech detected'."""
        from app.voice.schemas import STTResult  # noqa: PLC0415

        # STT returns empty text (silence)
        mock_stt_result = STTResult(
            text="",
            language="tr",
            language_probability=0.5,
        )

        mock_stt_service = AsyncMock()
        mock_stt_service.transcribe = AsyncMock(return_value=mock_stt_result)

        fake_wav = _make_fake_wav()

        with patch("app.voice.router.get_stt_service", return_value=mock_stt_service):
            response = await app_client.post(
                "/api/v1/voice",
                files={"audio": ("silence.wav", fake_wav, "audio/wav")},
            )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        assert "No speech detected" in response.text, (
            f"Expected 'No speech detected' in error. Got: {response.text}"
        )
