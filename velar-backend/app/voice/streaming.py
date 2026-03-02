"""Sentence-boundary streaming for VELAR voice pipeline.

Implements sub-4s perceived latency by streaming Claude's response through
a sentence splitter and dispatching each sentence to TTS immediately, while
Claude continues generating the rest of the response.

Latency model (sequential baseline: 3.5s+):
    STT: ~1s + Claude full response: ~1.5s + TTS full response: ~1s = 3.5s+

Latency model (sentence streaming: ~1.6s perceived):
    STT: ~1s + Claude first sentence: ~300ms + TTS first sentence: ~75-300ms = ~1.6s
    (subsequent sentences stream in the background)

Usage:
    from app.voice.streaming import stream_conversation_to_audio

    full_text, audio_bytes = await stream_conversation_to_audio(
        user_text="Merhaba, hava nasıl?",
        language="tr",
        detected_language="tr",
    )
"""

import asyncio
import logging
import re

import anthropic

from app.config import settings
from app.voice.conversation import VELAR_SYSTEM_PROMPT
from app.voice.tts import tts_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentence boundary detection
# ---------------------------------------------------------------------------

# Matches a sentence-ending punctuation mark (. ! ?) followed by one or more
# whitespace characters. This is the split point: everything up to and including
# the punctuation becomes a sentence; the rest stays in the buffer.
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries, returning a list of sentence strings.

    Used internally by stream_conversation_to_audio and directly in unit tests.

    Examples:
        "Hello. World."  -> ["Hello.", "World."]
        "One sentence"   -> ["One sentence"]  (no boundary -> single item)
        "A! B? C."       -> ["A!", "B?", "C."]
    """
    parts = SENTENCE_BOUNDARY_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Streaming conversation to audio
# ---------------------------------------------------------------------------

async def stream_conversation_to_audio(
    user_text: str,
    language: str = "tr",
    history: list[dict] | None = None,
    detected_language: str | None = None,
) -> tuple[str, bytes]:
    """Stream Claude response through sentence-boundary TTS dispatch.

    Returns (full_response_text, concatenated_audio_bytes).

    Strategy:
        1. Build system prompt with optional language context.
        2. Collect Claude's streamed text deltas via asyncio.to_thread
           (the Anthropic SDK streaming API is synchronous).
        3. Accumulate deltas in a buffer. On each sentence boundary (. ! ?
           followed by whitespace), dispatch that sentence to TTS immediately
           via asyncio.create_task.
        4. After Claude finishes, dispatch any remaining text (last sentence
           may not end with punctuation).
        5. await asyncio.gather(*tts_tasks) to collect all audio chunks in
           sentence order, then concatenate.

    Latency win: TTS for sentence 1 starts while Claude is still generating
    sentences 2, 3, etc. — the first audio chunk is ready much sooner than
    waiting for the full response.

    Args:
        user_text:          The user's transcribed speech.
        language:           Language code for TTS voice selection ("tr" or "en").
        history:            Optional prior turns (truncated to last 10).
                            Phase 3 will replace this with memory-backed retrieval.
        detected_language:  Optional language code detected from STT. When provided,
                            appends [Context: ...] to the system prompt.

    Returns:
        Tuple of (full_response_text, mp3_audio_bytes).
    """
    # Build language-aware system prompt (same logic as conversation.py)
    system = VELAR_SYSTEM_PROMPT
    if detected_language:
        lang_name = {"tr": "Turkish", "en": "English"}.get(detected_language, detected_language)
        system += f"\n\n[Context: The user is speaking {lang_name}. Respond in {lang_name}.]"

    # Build messages list with truncated history
    # Phase 3 will replace this with memory-backed context retrieval.
    messages = ((history or [])[-10:]) + [{"role": "user", "content": user_text}]

    # ---------------------------------------------------------------------------
    # Step 1: Collect Claude streaming deltas via to_thread (SDK is sync)
    # ---------------------------------------------------------------------------
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def _stream_claude() -> list[str]:
        """Collect all text deltas from Claude's streaming response."""
        deltas: list[str] = []
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                deltas.append(text)
        return deltas

    try:
        all_deltas = await asyncio.to_thread(_stream_claude)
    except anthropic.AuthenticationError as exc:
        logger.error("Anthropic authentication failed in streaming: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Anthropic API key not configured") from exc
    except anthropic.APIError as exc:
        logger.error("Claude API error in streaming: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="Claude API error") from exc

    # ---------------------------------------------------------------------------
    # Step 2: Walk deltas, detect sentence boundaries, dispatch TTS tasks
    # ---------------------------------------------------------------------------
    buffer = ""        # Accumulates streamed text between boundaries
    full_text = ""     # Complete response text for the caller
    tts_tasks: list[asyncio.Task] = []

    for delta in all_deltas:
        buffer += delta
        full_text += delta

        # Dispatch each complete sentence to TTS as soon as a boundary is found
        while True:
            match = SENTENCE_BOUNDARY_RE.search(buffer)
            if not match:
                break
            # Include the punctuation in the sentence; drop the whitespace boundary
            sentence = buffer[: match.start() + 1].strip()
            buffer = buffer[match.end() :]

            if sentence:
                logger.debug("Dispatching sentence to TTS (%d chars): %r", len(sentence), sentence[:50])
                task = asyncio.create_task(
                    tts_service.synthesize(text=sentence, language=language)
                )
                tts_tasks.append(task)

    # Dispatch any remaining text (last sentence without trailing punctuation)
    remaining = buffer.strip()
    if remaining:
        logger.debug("Dispatching remainder to TTS (%d chars): %r", len(remaining), remaining[:50])
        task = asyncio.create_task(
            tts_service.synthesize(text=remaining, language=language)
        )
        tts_tasks.append(task)

    # ---------------------------------------------------------------------------
    # Step 3: Await all TTS tasks and concatenate audio in sentence order
    # ---------------------------------------------------------------------------
    if tts_tasks:
        audio_chunks: tuple[bytes, ...] = await asyncio.gather(*tts_tasks)
        combined_audio = b"".join(audio_chunks)
    else:
        # Edge case: empty response from Claude
        logger.warning("stream_conversation_to_audio: Claude returned empty response")
        combined_audio = b""

    logger.info(
        "Streaming complete: %d sentences, %d audio bytes",
        len(tts_tasks),
        len(combined_audio),
    )

    return full_text, combined_audio
