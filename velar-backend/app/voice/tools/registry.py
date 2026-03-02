"""Tool registry for VELAR integration tools.

Defines TOOL_DEFINITIONS (Anthropic tool_use schema) and the execute_tool()
dispatcher for all four Phase 4 integration tools.

Usage:
    from app.voice.tools.registry import TOOL_DEFINITIONS, execute_tool
"""

TOOL_DEFINITIONS = [
    {
        "name": "get_calendar_events",
        "description": (
            "Retrieves upcoming events from the user's primary Google Calendar. "
            "Use when the user asks about their schedule, next appointment, today's events, "
            "or what they have planned. Returns a list of events with title, start time, and location. "
            "Do not use for past events. days_ahead=1 means today only; days_ahead=7 means the week."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days of events to fetch (1=today, 7=week)",
                    "default": 1,
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Fetches current weather conditions and forecast for the user's city. "
            "Use when the user asks about weather, temperature, rain, or whether to bring an umbrella. "
            "Returns current temperature, condition, high/low, and precipitation probability for 24h."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "set_reminder",
        "description": (
            "Creates a reminder in macOS Reminders app with iCloud sync. "
            "Use when the user says 'remind me', 'set a reminder', or 'don't let me forget'. "
            "The reminder will appear in Reminders.app and sync to iPhone. "
            "minutes_from_now must be a positive integer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The reminder text"},
                "minutes_from_now": {
                    "type": "integer",
                    "description": "When to trigger the reminder, in minutes from now",
                },
            },
            "required": ["text", "minutes_from_now"],
        },
    },
    {
        "name": "get_places",
        "description": (
            "Searches for nearby places matching a query (restaurants, cafes, gyms, etc.). "
            "Use when the user asks where to go, what's nearby, or for place recommendations. "
            "Returns top 3 open results with name, rating, and address. "
            "Location is the user's configured city, not real-time GPS."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What kind of place to find (e.g. 'coffee shop', 'italian restaurant')",
                }
            },
            "required": ["query"],
        },
    },
]


async def execute_tool(name: str, inputs: dict, user_id: str | None) -> str:
    """Dispatch a tool call by name and return the prose result string.

    Args:
        name:    Tool name (must match one of the TOOL_DEFINITIONS names).
        inputs:  Dict of tool input parameters from Claude's tool_use block.
        user_id: Optional user ID for future user-scoped tool calls (Phase 5+).

    Returns:
        Voice-optimized prose string with the tool result.

    Raises:
        ValueError: If the tool name is not recognized.
    """
    if name == "get_calendar_events":
        from app.voice.tools.calendar_tool import get_calendar_events
        try:
            return await get_calendar_events(**inputs)
        except Exception as exc:
            return f"Tool error: {exc}"
    elif name == "get_weather":
        from app.voice.tools.weather_tool import get_weather
        try:
            return await get_weather()
        except Exception as exc:
            return f"Tool error: {exc}"
    elif name == "set_reminder":
        from app.voice.tools.reminder_tool import set_reminder
        try:
            return await set_reminder(**inputs)
        except Exception as exc:
            return f"Tool error: {exc}"
    elif name == "get_places":
        from app.voice.tools.places_tool import get_places
        try:
            return await get_places(**inputs)
        except Exception as exc:
            return f"Tool error: {exc}"
    raise ValueError(f"Unknown tool: {name}")
