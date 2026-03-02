"""Voice and chat API endpoints for VELAR voice pipeline.

Endpoints:
    POST /voice  — Audio upload -> STT -> Claude -> TTS -> returns MP3 audio
    POST /chat   — Text input -> Claude -> TTS -> returns JSON with audio_base64

Both endpoints require a valid JWT bearer token (Depends(get_current_user)).
"""

import base64
import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, get_current_user
from app.voice.conversation import run_conversation
from app.voice.schemas import ChatRequest, ChatResponse
from app.voice.stt import get_stt_service
from app.voice.tts import tts_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


@router.post("/voice")
async def voice_endpoint(
    audio: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Full voice round-trip: audio in, audio out.

    Pipeline:
        1. Read uploaded audio bytes
        2. STT — transcribe to text (faster-whisper, auto language detection)
        3. Claude — generate voice-optimized response
        4. TTS — synthesize response to MP3 audio
        5. Stream audio back with metadata in response headers

    Headers in response:
        X-Transcript:         The transcribed user speech
        X-Response-Text:      Claude's text response
        X-Detected-Language:  Detected language code ("tr" or "en")

    Raises:
        422: No speech detected in audio, or unsupported audio format
        502: Claude API returned an error
        503: Anthropic API key not configured
        500: TTS generation failed
    """
    # 1. Read uploaded audio
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Empty audio file uploaded")

    # 2. Speech-to-text
    stt = get_stt_service()
    try:
        stt_result = await stt.transcribe(audio_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not stt_result.text.strip():
        raise HTTPException(status_code=422, detail="No speech detected in audio")

    logger.info(
        "STT result: lang=%s prob=%.2f text=%r",
        stt_result.language,
        stt_result.language_probability,
        stt_result.text[:80],
    )

    # Short-utterance language fallback: low confidence + short text -> default to Turkish.
    # Turkish is the primary user language (per CONTEXT.md). Short utterances (< 5 words)
    # with low language_probability are prone to misdetection — safer to assume Turkish.
    detected_lang = stt_result.language
    if stt_result.language_probability < 0.8 and len(stt_result.text.split()) < 5:
        logger.info(
            "Low language confidence (%.2f) on short utterance (%d words), defaulting to Turkish",
            stt_result.language_probability,
            len(stt_result.text.split()),
        )
        detected_lang = "tr"

    # 3. Claude conversation — raises 502/503 on failure
    response_text = await run_conversation(
        user_text=stt_result.text,
        history=[],
        detected_language=detected_lang,
    )

    # 4. TTS synthesis
    try:
        audio_response = await tts_service.synthesize(
            text=response_text,
            language=detected_lang,
        )
    except Exception as exc:
        logger.error("TTS generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="TTS generation failed") from exc

    # 5. Stream MP3 audio with metadata headers
    return StreamingResponse(
        io.BytesIO(audio_response),
        media_type="audio/mpeg",
        headers={
            "X-Transcript": stt_result.text,
            "X-Response-Text": response_text,
            "X-Detected-Language": detected_lang,
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    """Text-in, JSON-out chat endpoint (no STT step).

    Pipeline:
        1. Claude — generate voice-optimized response from text input
        2. TTS — synthesize response to MP3 audio
        3. Return JSON with text response and base64-encoded audio

    Raises:
        502: Claude API returned an error
        503: Anthropic API key not configured
        500: TTS generation failed
    """
    # /chat uses sequential pipeline — JSON response requires complete audio before returning.
    # /voice uses streaming pipeline (stream_conversation_to_audio) for sub-4s latency.

    # Determine language: use explicit override if provided, otherwise use simple heuristic.
    # The heuristic is intentionally lightweight — Claude's system prompt is the primary
    # language driver. The heuristic is just a hint to help Claude for ambiguous inputs.
    if request.language:
        chat_lang = request.language
    else:
        # Detect Turkish by checking for Turkish-specific characters or common words.
        turkish_chars = set("ğşıöüçİĞŞ")
        common_turkish = {"merhaba", "evet", "hayır", "tamam", "nasıl", "ne", "ve",
                          "bir", "bu", "da", "de", "için", "ile"}
        message_lower = request.message.lower()
        has_turkish_char = any(c in turkish_chars for c in request.message)
        has_turkish_word = any(w in message_lower.split() for w in common_turkish)
        chat_lang = "tr" if (has_turkish_char or has_turkish_word) else "en"

    # 1. Claude conversation — raises 502/503 on failure
    response_text = await run_conversation(
        user_text=request.message,
        history=request.history,
        detected_language=chat_lang,
    )

    # 2. TTS synthesis
    language = chat_lang
    try:
        audio_response = await tts_service.synthesize(
            text=response_text,
            language=language,
        )
    except Exception as exc:
        logger.error("TTS generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="TTS generation failed") from exc

    # 3. Encode audio and return JSON response
    audio_base64 = base64.b64encode(audio_response).decode()

    return ChatResponse(
        text=response_text,
        audio_base64=audio_base64,
        detected_language=language,
    )
