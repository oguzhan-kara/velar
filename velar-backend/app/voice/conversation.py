"""Claude conversation loop for VELAR voice assistant.

Implements the reasoning stage of the voice pipeline: takes user text (from STT
or direct text input) and returns a voice-optimized response via Claude Haiku.

The tool-use scaffold is present but empty for Phase 2; Phase 4+ will add real
tool definitions (calendar, reminders, weather, etc.) and a multi-turn loop.

Usage:
    from app.voice.conversation import run_conversation

    response_text = await run_conversation(user_text="Merhaba, hava nasıl?")
"""

import asyncio
import logging

import anthropic
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VELAR System Prompt
# ---------------------------------------------------------------------------

VELAR_SYSTEM_PROMPT = """\
You are VELAR, a proactive personal AI assistant.

## Identity & Persona
You are male, warm, confident, and slightly formal — like a skilled concierge, \
not a robot. Think of yourself as an intelligent companion in the style of Jarvis \
from Iron Man: calm under pressure, anticipatory, and subtly witty when appropriate.

## Language Rules (CRITICAL)
Always respond in the SAME language the user spoke to you:
- Turkish input → Turkish response
- English input → English response
- Mixed (code-switching) → respond in the dominant language of the user's message
Do NOT translate. Think natively in whichever language the user used. \
Never mix languages in a single response unless the user did so themselves.

## Voice Response Style
Your responses are heard, not read. Optimize for listening:
- Keep answers concise: 1-3 sentences for simple questions, up to 5 sentences \
for complex ones.
- Use short sentences with natural conversational rhythm.
- You may be slightly witty and anticipatory — phrases like "By the way..." \
or "I noticed..." are welcome when genuinely useful.
- Avoid walls of information. If a detailed answer is needed, give the most \
important point first and offer to elaborate.

## Formatting Rules
- Do not use emoji.
- Do not use markdown formatting (no bullet points, headers, bold, or code blocks) \
in voice responses.
- Spell out numbers and abbreviations that are awkward when read aloud.

## Boundaries
You are VELAR — not ChatGPT, not Claude, not any other product. \
Do not reveal the underlying model or company. If asked who made you, say \
"I'm VELAR, your personal AI assistant."
"""

# ---------------------------------------------------------------------------
# Anthropic client (module-level, lazy-safe because settings import is inside fn)
# ---------------------------------------------------------------------------

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    """Return (or create) the Anthropic client using the current settings."""
    global _client
    if _client is None:
        from app.config import settings  # lazy import — avoids startup validation
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ---------------------------------------------------------------------------
# Conversation loop
# ---------------------------------------------------------------------------

async def run_conversation(
    user_text: str,
    history: list[dict] | None = None,
    max_tokens: int = 512,
) -> str:
    """Run a single Claude Haiku conversation turn and return the response text.

    Args:
        user_text:  The current user message (post-STT or raw text).
        history:    Optional list of prior turns:
                    [{"role": "user"|"assistant", "content": str}, ...]
                    Truncated to the last 10 turns before sending.
        max_tokens: Maximum tokens for Claude's response (default 512 for voice).

    Returns:
        The assistant's text response, optimized for TTS.

    Raises:
        HTTPException(502): Claude API returned an error.
        HTTPException(503): Anthropic API key is not configured.
    """
    # Build messages: truncate history to last 10 turns, then append current input
    prior_turns: list[dict] = list(history or [])
    if len(prior_turns) > 10:
        prior_turns = prior_turns[-10:]

    messages = prior_turns + [{"role": "user", "content": user_text}]

    client = _get_client()

    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            system=VELAR_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=max_tokens,
            # Tool-use scaffold — Phase 4+ adds real tools here:
            # tools=[...],
            # When tools are added, check response.stop_reason == "tool_use"
            # and handle tool calls in a loop until stop_reason == "end_turn".
        )
    except anthropic.AuthenticationError as exc:
        logger.error("Anthropic authentication failed — API key may be missing or invalid: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured",
        ) from exc
    except anthropic.APIError as exc:
        logger.error("Claude API error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Claude API error",
        ) from exc

    return response.content[0].text
