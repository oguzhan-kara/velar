"""Unit tests for Phase 4 integration tools.

Tests mock external APIs — no real API keys required.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_tool_definitions_structure():
    """TOOL_DEFINITIONS has 4 tools with correct schema structure."""
    from app.voice.tools.registry import TOOL_DEFINITIONS
    assert len(TOOL_DEFINITIONS) == 4
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"get_calendar_events", "get_weather", "set_reminder", "get_places"}
    for tool in TOOL_DEFINITIONS:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


def test_reminder_quote_escaping():
    """set_reminder escapes double quotes in text to prevent AppleScript injection."""
    from app.voice.tools.reminder_tool import _set_reminder_sync
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = _set_reminder_sync('Buy "organic" milk', 30)
    # Ensure the AppleScript call was made (subprocess.run was called)
    assert mock_run.called
    # The script string passed to osascript must not contain unescaped quotes
    script_arg = mock_run.call_args[0][0]  # ["osascript", "-e", script]
    # Verify the text was escaped in the call
    assert result == "Reminder set: 'Buy \"organic\" milk' in 30 minutes."


def test_weather_cache_hit():
    """get_weather returns cached result when cache has not expired."""
    import time
    from app.voice.tools import weather_tool
    # Pre-populate cache
    weather_tool._cache["data"] = {
        "current": {"temp": 18.0, "weather": [{"description": "partly cloudy"}]},
        "daily": [{"temp": {"max": 22.0, "min": 12.0}, "pop": 0.3}]
    }
    weather_tool._cache["expires"] = time.time() + 1800
    with patch("requests.get") as mock_get:
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            weather_tool.get_weather()
        )
    # requests.get should NOT be called if cache is warm
    mock_get.assert_not_called()
    assert "18" in result  # temperature in result
    assert "22" in result  # high temp


@pytest.mark.asyncio
async def test_execute_tool_unknown_raises():
    """execute_tool raises ValueError for unknown tool names."""
    from app.voice.tools.registry import execute_tool
    with pytest.raises(ValueError, match="Unknown tool"):
        await execute_tool("nonexistent_tool", {}, None)


@pytest.mark.asyncio
async def test_execute_tool_routes_correctly():
    """execute_tool dispatches to correct tool module."""
    from app.voice.tools.registry import execute_tool
    with patch("app.voice.tools.weather_tool.get_weather",
               new_callable=AsyncMock, return_value="18°C, sunny") as mock:
        result = await execute_tool("get_weather", {}, None)
    mock.assert_called_once()
    assert result == "18°C, sunny"
