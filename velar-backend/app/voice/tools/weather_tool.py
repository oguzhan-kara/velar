"""OpenWeatherMap One Call API 3.0 integration for VELAR.

Fetches current weather and daily forecast for the configured city.
Results are cached in-process for 30 minutes to minimize API calls.

API requirements:
    - openweathermap_api_key in settings (OPENWEATHERMAP_API_KEY env var)
    - "One Call by Call" subscription on openweathermap.org (1,000 free calls/day)
    - weather_city in settings (WEATHER_CITY env var, default: Istanbul)

Cache:
    Module-level _cache dict: {"data": <raw API response>, "expires": <float timestamp>}
    TTL: 30 minutes (CACHE_TTL = 1800 seconds)
"""

import asyncio
import logging
import time

import requests

logger = logging.getLogger(__name__)

CACHE_TTL = 1800  # 30 minutes

_cache: dict = {"data": None, "expires": 0.0}
_geocode_cache: dict = {}  # city -> (lat, lon)


def _geocode_city(city: str, api_key: str) -> tuple[float, float]:
    """Resolve city name to (lat, lon) via OpenWeatherMap Geocoding API.

    Results are cached in _geocode_cache for the lifetime of the process —
    city-level location only changes if settings change, so no TTL needed.
    """
    if city in _geocode_cache:
        return _geocode_cache[city]

    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city, "limit": 1, "appid": api_key}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"Could not geocode city: {city!r}")
    lat, lon = data[0]["lat"], data[0]["lon"]
    _geocode_cache[city] = (lat, lon)
    logger.debug("Geocoded %r -> (%.4f, %.4f)", city, lat, lon)
    return lat, lon


def _format_weather(data: dict) -> str:
    """Format raw API response as voice-optimized prose."""
    cur = data["current"]
    daily = data["daily"][0]
    temp = cur["temp"]
    condition = cur["weather"][0]["description"]
    high = daily["temp"]["max"]
    low = daily["temp"]["min"]
    rain_pct = int(daily.get("pop", 0) * 100)
    return (
        f"Currently {temp:.0f} degrees Celsius with {condition}. "
        f"Today's high is {high:.0f} and the low is {low:.0f}. "
        f"Rain probability: {rain_pct}%."
    )


def _get_weather_sync() -> str:
    """Synchronous implementation — called via asyncio.to_thread."""
    from app.config import settings  # lazy import — avoids startup validation

    now = time.time()
    if _cache["expires"] > now and _cache["data"] is not None:
        logger.debug("Weather cache hit (expires in %.0fs)", _cache["expires"] - now)
        return _format_weather(_cache["data"])

    api_key = settings.openweathermap_api_key
    if not api_key:
        return "Weather is not configured. Please set OPENWEATHERMAP_API_KEY."

    lat, lon = _geocode_city(settings.weather_city, api_key)
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "exclude": "minutely,alerts",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    _cache["data"] = data
    _cache["expires"] = now + CACHE_TTL
    logger.debug("Weather cache updated (TTL: %ds)", CACHE_TTL)
    return _format_weather(data)


async def get_weather() -> str:
    """Fetch current weather and forecast for the configured city.

    Returns:
        Voice-optimized prose string with temperature, conditions, and rain probability.
        Uses 30-minute in-process cache to minimize API calls.
    """
    return await asyncio.to_thread(_get_weather_sync)
