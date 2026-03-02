"""Claude-based background fact extraction for VELAR memory system.

After each voice/chat turn, extract_facts_from_conversation() is called via
FastAPI BackgroundTasks. It uses Claude Haiku with structured output (output_config)
to extract personal facts from the conversation as a guaranteed-schema JSON array.

Structured output is GA for Claude Haiku 4.5 (claude-haiku-4-5-20251001) as of
late 2025. No beta headers required. Use output_config.format (the GA parameter).

Facts extracted: health, food, social, place, habit, work, preference categories.
Extraction is liberal — prefer to extract too much (user can delete) over missing facts.
"""

import asyncio
import json
import logging
import anthropic

logger = logging.getLogger(__name__)

# JSON schema for structured output — guarantees Claude returns exactly this shape
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["health", "food", "social", "place", "habit", "work", "preference"]
                    },
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["category", "key", "value", "confidence"],
                "additionalProperties": False,
            }
        }
    },
    "required": ["facts"],
    "additionalProperties": False,
}

EXTRACTION_SYSTEM_PROMPT = """\
You extract personal facts about the user from conversation excerpts.
Extract ONLY facts about the USER (not the assistant) that are clearly stated or strongly implied.
Be liberal — prefer to extract than to miss. If in doubt, extract it.

Return each fact with:
- category: one of [health, food, social, place, habit, work, preference]
- key: snake_case attribute name (e.g. "nut_allergy", "favorite_restaurant", "workplace")
- value: the fact value as stated or implied (e.g. "true", "Karaköy Lokantası", "Google")
- confidence: 0.7 for implied/uncertain facts, 0.85 for clearly stated facts

Rules:
- Never set confidence above 0.85 (you are Claude, not the user)
- Do not extract facts about the assistant or general knowledge
- Do not extract questions — only stated or implied facts
- Turkish and English text are both valid; keep values in the language used
- Return an empty facts array if no personal facts are present in the conversation

Examples of valid extractions:
  User: "Fıstık alerjim var, bunu bil." → {category: "health", key: "nut_allergy", value: "true", confidence: 0.85}
  User: "I moved to Ankara last month." → {category: "place", key: "current_city", value: "Ankara", confidence: 0.85}
  User: "I usually wake up at 6am." → {category: "habit", key: "wake_up_time", value: "06:00", confidence: 0.7}
"""


async def extract_facts_from_conversation(
    user_message: str,
    assistant_response: str,
) -> list[dict]:
    """Extract personal facts from a single conversation turn.

    Uses Claude Haiku with output_config structured output to guarantee JSON schema
    compliance. The sync Anthropic client is called via asyncio.to_thread (same pattern
    as conversation.py — the sync client is pinned at anthropic==0.84.0).

    Args:
        user_message:       The user's message text.
        assistant_response: Claude's response text (included for context but extraction
                            focuses on user-stated facts).

    Returns:
        List of fact dicts with keys: category, key, value, confidence.
        Empty list if extraction fails or no facts found — NEVER raises.
    """
    from app.config import settings

    if not settings.anthropic_api_key:
        logger.warning("anthropic_api_key not set — skipping fact extraction")
        return []

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    conversation_text = f"User: {user_message}\nAssistant: {assistant_response}"

    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": conversation_text}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "name": "fact_extraction",
                    "schema": EXTRACTION_SCHEMA,
                }
            },
        )
        data = json.loads(response.content[0].text)
        facts = data.get("facts", [])
        logger.info("Extracted %d facts from conversation turn", len(facts))
        return facts
    except Exception as exc:
        logger.warning("Fact extraction failed (non-fatal): %s", exc)
        return []
