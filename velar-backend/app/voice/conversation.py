"""Claude conversation loop for VELAR voice assistant.

Implements the reasoning stage of the voice pipeline: takes user text (from STT
or direct text input) and returns a voice-optimized response via Claude Haiku.

Phase 4: Active tool_use loop — Claude can invoke calendar, weather, reminders,
and places tools. The loop runs until stop_reason == "end_turn", executing any
tool calls in between. Tool failures return graceful fallback strings rather than
crashing the loop.

Usage:
    from app.voice.conversation import run_conversation

    response_text = await run_conversation(user_text="Merhaba, hava nasıl?")
"""

import asyncio
import logging

import anthropic
from fastapi import HTTPException

from app.voice.tools.registry import TOOL_DEFINITIONS, execute_tool

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
    detected_language: str | None = None,
    memory_context: str | None = None,   # Phase 3: relevant memory facts
    user_id: str | None = None,          # Phase 4: for tool context (Phase 5+ user-scoped tools)
) -> str:
    """Run a Claude Haiku conversation with active tool_use loop.

    Passes TOOL_DEFINITIONS to Claude on every call. If Claude invokes tools,
    executes them and loops until stop_reason == "end_turn". Tool failures
    return graceful fallback strings and never crash the loop.

    Args:
        user_text:          The current user message (post-STT or raw text).
        history:            Optional list of prior turns:
                            [{"role": "user"|"assistant", "content": str}, ...]
                            Truncated to the last 10 turns before sending.
        max_tokens:         Maximum tokens for Claude's response (default 512 for voice).
        detected_language:  Optional language code ("tr" or "en") detected from STT or
                            heuristic. When provided, appends a language context note to
                            the system prompt so Claude responds in the correct language.
                            Do NOT modify VELAR_SYSTEM_PROMPT — always create a local copy.
        memory_context:     Optional formatted string of relevant memory facts from
                            get_relevant_facts() + facts_to_context_string(). When
                            provided, injected into the system prompt with hallucination
                            guard instructions. If None or empty, no memory block added.
        user_id:            Optional user ID for tool context (used by Phase 5+ user-scoped tools).

    Returns:
        The assistant's text response, optimized for TTS.

    Raises:
        HTTPException(502): Claude API returned an error.
        HTTPException(503): Anthropic API key is not configured.
    """
    # Build system prompt — never modify the VELAR_SYSTEM_PROMPT constant
    system = VELAR_SYSTEM_PROMPT

    # Inject memory context with hallucination guard (Phase 3)
    # The guard is CRITICAL: without it, Claude may invent facts it wasn't given.
    if memory_context and memory_context.strip():
        system += (
            "\n\n## [VELAR MEMORY — What I know about you]\n"
            + memory_context
            + "\n\n"
            "[IMPORTANT: The above list is EVERYTHING I know about you. "
            "If a fact is not listed above, I do NOT know it. "
            "Do NOT claim facts about you that are not listed here. "
            "When referencing a stored fact, be natural — do not say 'according to my memory'.]"
        )

    if detected_language:
        lang_name = {"tr": "Turkish", "en": "English"}.get(detected_language, detected_language)
        system += f"\n\n[Context: The user is speaking {lang_name}. Respond in {lang_name}.]"

    # Build messages: truncate history to last 10 turns, then append current input
    prior_turns: list[dict] = list(history or [])
    if len(prior_turns) > 10:
        prior_turns = prior_turns[-10:]

    messages = prior_turns + [{"role": "user", "content": user_text}]

    client = _get_client()

    try:
        # Phase 4: Active tool_use loop — runs until stop_reason == "end_turn"
        while True:
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                tools=TOOL_DEFINITIONS,
            )

            if response.stop_reason == "end_turn":
                # Extract text response from content blocks
                for block in response.content:
                    if block.type == "text":
                        return block.text
                return ""  # fallback if no text block present

            if response.stop_reason == "tool_use":
                # Append Claude's response (containing tool_use blocks) to history
                messages.append({"role": "assistant", "content": response.content})

                # Execute each tool call and collect results
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            result = await execute_tool(block.name, block.input, user_id)
                        except Exception as exc:
                            logger.warning(
                                "Tool %r failed: %s", block.name, exc
                            )
                            result = f"I couldn't fetch that right now. ({exc})"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                # Append tool results as user turn — Claude synthesizes voice response
                messages.append({"role": "user", "content": tool_results})
                # Loop continues — Claude will synthesize response using tool results

            else:
                # Unexpected stop_reason (e.g. "max_tokens", "stop_sequence") — bail gracefully
                logger.warning("Unexpected stop_reason: %s", response.stop_reason)
                return "I couldn't process that request right now."

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
