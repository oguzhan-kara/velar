"""Conversation loop for VELAR voice assistant.

Provider selection via LLM_PROVIDER env var:
- "gemini"    (default): Use Google Gemini 2.0 Flash (free tier at aistudio.google.com).
- "anthropic": Use Claude Haiku (paid, unchanged from Phase 4).

Both providers implement the full VELAR feature set:
- VELAR_SYSTEM_PROMPT personality
- Tool use (calendar, weather, reminders, places)
- Language mirroring (Turkish/English auto-detect)
- Memory context injection ([VELAR MEMORY] block)

Usage:
    from app.voice.conversation import run_conversation

    response_text = await run_conversation(user_text="Merhaba, hava nasıl?")
"""

import asyncio
import logging

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
# Anthropic client (unchanged from Phase 4 — lazy singleton)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Return (or create) the Anthropic client using the current settings."""
    global _client
    if _client is None:
        import anthropic
        from app.config import settings  # lazy import — avoids startup validation
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ---------------------------------------------------------------------------
# Gemini tool definitions (translated from Anthropic format)
# ---------------------------------------------------------------------------

def _build_gemini_tools() -> list:
    """Convert TOOL_DEFINITIONS (Anthropic format) to Gemini function_declarations format.

    Anthropic uses "input_schema" with JSON Schema. Gemini uses "parameters"
    with the same JSON Schema subset. The translation is 1-to-1 for these tools.
    """
    declarations = []
    for tool in TOOL_DEFINITIONS:
        # Anthropic's input_schema is a JSON Schema object — Gemini's parameters is the same
        decl = {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        }
        declarations.append(decl)
    return [{"function_declarations": declarations}]


# ---------------------------------------------------------------------------
# Gemini conversation loop
# ---------------------------------------------------------------------------

async def _run_gemini_conversation(
    user_text: str,
    history: list[dict] | None = None,
    max_tokens: int = 512,
    detected_language: str | None = None,
    memory_context: str | None = None,
    user_id: str | None = None,
) -> str:
    """Run a Gemini 2.0 Flash conversation with active function-calling loop.

    Implements the same feature set as the Anthropic path:
    - VELAR_SYSTEM_PROMPT personality via system_instruction
    - Tool use via Gemini function calling (same 4 tools)
    - Language mirroring via detected_language hint
    - Memory context injection with hallucination guard

    Args:
        user_text:         The current user message.
        history:           Optional list of prior turns (role/content dicts).
        max_tokens:        Max tokens for Gemini's response.
        detected_language: Optional language code ("tr" or "en").
        memory_context:    Optional formatted memory facts string.
        user_id:           Optional user ID for tool context.

    Returns:
        The assistant's text response, optimized for TTS.

    Raises:
        HTTPException(503): GOOGLE_AI_API_KEY is not configured.
        HTTPException(502): Gemini API returned an error.
    """
    import google.generativeai as genai
    from app.config import settings

    if not settings.google_ai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Google AI API key not configured (set GOOGLE_AI_API_KEY)",
        )

    genai.configure(api_key=settings.google_ai_api_key)

    # Build system prompt — same structure as Anthropic path
    system = VELAR_SYSTEM_PROMPT

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

    # Build Gemini tool definitions
    gemini_tools = _build_gemini_tools()

    try:
        # Create model with system_instruction and tools
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            tools=gemini_tools,
            system_instruction=system,
        )

        # Build history for Gemini chat format
        # Gemini chat history uses {"role": "user"|"model", "parts": [text]}
        chat_history = []
        prior_turns: list[dict] = list(history or [])
        if len(prior_turns) > 10:
            prior_turns = prior_turns[-10:]

        for turn in prior_turns:
            role = "model" if turn.get("role") == "assistant" else "user"
            content = turn.get("content", "")
            if isinstance(content, str):
                chat_history.append({"role": role, "parts": [content]})
            # Skip complex content blocks from prior tool turns — Gemini chat
            # history only supports text messages. Tool results from prior turns
            # are not replayed; only the most recent conversation turn matters.

        chat = model.start_chat(history=chat_history)

        # Active function-calling loop — mirrors Anthropic tool_use loop
        current_message = user_text

        while True:
            def _send_message(msg):
                return chat.send_message(msg)

            response = await asyncio.to_thread(_send_message, current_message)

            # Check for function calls in the response parts
            function_calls = []
            text_parts = []

            for part in response.parts:
                if hasattr(part, "function_call") and part.function_call.name:
                    function_calls.append(part.function_call)
                elif hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            if function_calls:
                # Execute all function calls and collect responses
                from google.generativeai.types import content_types
                tool_response_parts = []

                for fc in function_calls:
                    tool_name = fc.name
                    # fc.args is a MapComposite (proto-plus mapping) — convert to dict
                    tool_inputs = dict(fc.args) if fc.args else {}

                    try:
                        result = await execute_tool(tool_name, tool_inputs, user_id)
                    except Exception as exc:
                        logger.warning("Tool %r failed: %s", tool_name, exc)
                        result = f"I couldn't fetch that right now. ({exc})"

                    tool_response_parts.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response={"result": str(result)},
                            )
                        )
                    )

                # Send all function responses back in one message
                # This continues the loop — Gemini will synthesize the final response
                current_message = tool_response_parts

            else:
                # No function calls — this is the final text response
                if text_parts:
                    return "".join(text_parts)
                # Fallback: try finish_message or candidates
                try:
                    return response.text
                except Exception:
                    return "I couldn't process that request right now."

    except HTTPException:
        raise  # Re-raise our own HTTP exceptions as-is
    except Exception as exc:
        error_str = str(exc).lower()
        if "api_key" in error_str or "api key" in error_str or "authentication" in error_str:
            logger.error("Gemini authentication failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Google AI API key not configured or invalid",
            ) from exc
        logger.error("Gemini API error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Gemini API error",
        ) from exc


# ---------------------------------------------------------------------------
# Anthropic (Claude Haiku) conversation loop — unchanged from Phase 4
# ---------------------------------------------------------------------------

async def _run_anthropic_conversation(
    user_text: str,
    history: list[dict] | None = None,
    max_tokens: int = 512,
    detected_language: str | None = None,
    memory_context: str | None = None,
    user_id: str | None = None,
) -> str:
    """Run a Claude Haiku conversation with active tool_use loop.

    This is the original Phase 4 implementation, preserved intact.
    Activated when LLM_PROVIDER=anthropic.

    Raises:
        HTTPException(502): Claude API returned an error.
        HTTPException(503): Anthropic API key is not configured.
    """
    import anthropic

    # Build system prompt — never modify the VELAR_SYSTEM_PROMPT constant
    system = VELAR_SYSTEM_PROMPT

    # Inject memory context with hallucination guard (Phase 3)
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


# ---------------------------------------------------------------------------
# Groq (Llama 3.3 70B) conversation loop — free tier via OpenAI-compatible API
# ---------------------------------------------------------------------------

def _build_groq_tools() -> list:
    """Convert TOOL_DEFINITIONS (Anthropic format) to OpenAI function-calling format.

    Anthropic uses {name, description, input_schema}.
    OpenAI/Groq uses {type: "function", function: {name, description, parameters}}.
    The JSON Schema payload (input_schema / parameters) is identical.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in TOOL_DEFINITIONS
    ]


async def _run_groq_conversation(
    user_text: str,
    history: list[dict] | None = None,
    max_tokens: int = 512,
    detected_language: str | None = None,
    memory_context: str | None = None,
    user_id: str | None = None,
) -> str:
    """Run a Groq Llama 3.3 70B conversation with active function-calling loop.

    Uses the OpenAI-compatible Groq API (same SDK, different base_url).
    Implements the same feature set as the Anthropic and Gemini paths:
    - VELAR_SYSTEM_PROMPT personality
    - Tool use via OpenAI function calling (same 4 tools)
    - Language mirroring via detected_language hint
    - Memory context injection with hallucination guard

    Args:
        user_text:         The current user message.
        history:           Optional list of prior turns (role/content dicts).
        max_tokens:        Max tokens for the response.
        detected_language: Optional language code ("tr" or "en").
        memory_context:    Optional formatted memory facts string.
        user_id:           Optional user ID for tool context.

    Returns:
        The assistant's text response, optimized for TTS.

    Raises:
        HTTPException(503): GROQ_API_KEY is not configured.
        HTTPException(502): Groq API returned an error.
    """
    import json
    from openai import AsyncOpenAI

    from app.config import settings

    if not settings.groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="Groq API key not configured (set GROQ_API_KEY)",
        )

    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    # Build system prompt — same structure as other providers
    system = VELAR_SYSTEM_PROMPT

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

    # Build message history — truncate to last 10 turns
    prior_turns: list[dict] = list(history or [])
    if len(prior_turns) > 10:
        prior_turns = prior_turns[-10:]

    messages = (
        [{"role": "system", "content": system}]
        + prior_turns
        + [{"role": "user", "content": user_text}]
    )

    groq_tools = _build_groq_tools()

    try:
        # Active function-calling loop — mirrors Anthropic tool_use loop
        while True:
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=groq_tools,
                tool_choice="auto",
                max_tokens=max_tokens,
            )

            choice = response.choices[0]
            message = choice.message

            if choice.finish_reason == "tool_calls" and message.tool_calls:
                # Append assistant message with tool_calls to history
                messages.append(message)

                # Execute each tool call and collect results
                for tc in message.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_inputs = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_inputs = {}

                    try:
                        result = await execute_tool(tool_name, tool_inputs, user_id)
                    except Exception as exc:
                        logger.warning("Tool %r failed: %s", tool_name, exc)
                        result = f"I couldn't fetch that right now. ({exc})"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })
                # Loop continues — Groq will synthesize response using tool results

            else:
                # No tool calls — return the text response
                return message.content or "I couldn't process that request right now."

    except HTTPException:
        raise
    except Exception as exc:
        error_str = str(exc).lower()
        if "api_key" in error_str or "api key" in error_str or "authentication" in error_str or "401" in error_str:
            logger.error("Groq authentication failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Groq API key not configured or invalid",
            ) from exc
        logger.error("Groq API error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Groq API error",
        ) from exc


# ---------------------------------------------------------------------------
# Public entry point — dispatches to provider based on LLM_PROVIDER setting
# ---------------------------------------------------------------------------

async def run_conversation(
    user_text: str,
    history: list[dict] | None = None,
    max_tokens: int = 512,
    detected_language: str | None = None,
    memory_context: str | None = None,   # Phase 3: relevant memory facts
    user_id: str | None = None,          # Phase 4: for tool context
) -> str:
    """Run a conversation turn with the configured LLM provider.

    Dispatches to Gemini (default, free) or Anthropic (paid) based on
    the LLM_PROVIDER setting.

    Args:
        user_text:          The current user message (post-STT or raw text).
        history:            Optional list of prior turns:
                            [{"role": "user"|"assistant", "content": str}, ...]
                            Truncated to the last 10 turns before sending.
        max_tokens:         Maximum tokens for the response (default 512 for voice).
        detected_language:  Optional language code ("tr" or "en").
        memory_context:     Optional formatted string of relevant memory facts.
        user_id:            Optional user ID for tool context.

    Returns:
        The assistant's text response, optimized for TTS.

    Raises:
        HTTPException(502): LLM API returned an error.
        HTTPException(503): Required API key is not configured.
    """
    from app.config import settings
    provider = getattr(settings, "llm_provider", "gemini").lower()

    if provider == "anthropic":
        return await _run_anthropic_conversation(
            user_text=user_text,
            history=history,
            max_tokens=max_tokens,
            detected_language=detected_language,
            memory_context=memory_context,
            user_id=user_id,
        )
    elif provider == "groq":
        return await _run_groq_conversation(
            user_text=user_text,
            history=history,
            max_tokens=max_tokens,
            detected_language=detected_language,
            memory_context=memory_context,
            user_id=user_id,
        )
    else:
        # Default: gemini
        return await _run_gemini_conversation(
            user_text=user_text,
            history=history,
            max_tokens=max_tokens,
            detected_language=detected_language,
            memory_context=memory_context,
            user_id=user_id,
        )
