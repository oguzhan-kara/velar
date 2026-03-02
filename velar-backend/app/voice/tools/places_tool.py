"""Google Places API (New) integration for VELAR.

Searches for nearby places using the Places API (New) at places.googleapis.com/v1.
Returns top 3 open venues with name, rating, and address as voice-optimized prose.

API requirements:
    - google_places_api_key in settings (GOOGLE_PLACES_API_KEY env var)
    - Places API (New) enabled in Google Cloud Console
    - places_city in settings (PLACES_CITY env var, default: Istanbul)

Important: Uses the new Places API (places.googleapis.com/v1), NOT the legacy
endpoint (maps.googleapis.com). Requires X-Goog-FieldMask header to specify
which fields to return — omitting this header causes HTTP 400 (Pitfall 5).
"""

import asyncio
import logging

import requests

logger = logging.getLogger(__name__)

_geocode_cache: dict = {}  # city -> (lat, lon)


def _geocode_city(city: str, api_key: str) -> tuple[float, float]:
    """Resolve city name to (lat, lon) via OpenWeatherMap Geocoding API.

    Reuses the same geocoding approach as weather_tool for consistency.
    Results are cached in _geocode_cache for the process lifetime.
    """
    if city in _geocode_cache:
        return _geocode_cache[city]

    url = "https://api.openweathermap.org/geo/1.0/direct"
    # Note: uses OpenWeatherMap geocoding API (free, no special subscription).
    # For places_tool we use Google's Places API key for the Places call,
    # but we still use OWM geocoding to resolve the city to lat/lon.
    # If OWM API key is not set, fall back to a Google Geocoding approach.
    from app.config import settings  # lazy import

    owm_key = settings.openweathermap_api_key
    if owm_key:
        params = {"q": city, "limit": 1, "appid": owm_key}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data:
            lat, lon = data[0]["lat"], data[0]["lon"]
            _geocode_cache[city] = (lat, lon)
            return lat, lon

    # Fallback: Google Geocoding API using the Places API key
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": city, "key": api_key}
    resp = requests.get(geocode_url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        raise ValueError(f"Could not geocode city: {city!r}")
    loc = results[0]["geometry"]["location"]
    lat, lon = loc["lat"], loc["lng"]
    _geocode_cache[city] = (lat, lon)
    logger.debug("Geocoded %r -> (%.4f, %.4f) via Google", city, lat, lon)
    return lat, lon


def _get_places_sync(query: str) -> str:
    """Synchronous implementation — called via asyncio.to_thread."""
    from app.config import settings  # lazy import

    api_key = settings.google_places_api_key
    if not api_key:
        return "Places search is not configured. Please set GOOGLE_PLACES_API_KEY."

    lat, lon = _geocode_city(settings.places_city, api_key)

    # Google Places API (New) — Text Search endpoint supports keyword queries
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # X-Goog-FieldMask is REQUIRED — omitting causes HTTP 400 (Pitfall 5)
        "X-Goog-FieldMask": (
            "places.displayName,places.rating,"
            "places.formattedAddress,places.regularOpeningHours"
        ),
    }
    payload = {
        "textQuery": query,
        "maxResultCount": 5,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": 5000.0,
            }
        },
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    places = resp.json().get("places", [])

    if not places:
        return f"No places found matching '{query}'."

    results = []
    for p in places:
        name = p.get("displayName", {}).get("text", "Unknown")
        rating = p.get("rating", "N/A")
        address = p.get("formattedAddress", "")

        # Skip closed venues (Pitfall 5: filter is_open is False, not None)
        # None means opening hours not available — include those
        is_open = p.get("regularOpeningHours", {}).get("openNow", None)
        if is_open is False:
            continue

        if address:
            results.append(f"{name} ({rating} stars) on {address}")
        else:
            results.append(f"{name} ({rating} stars)")

        if len(results) == 3:
            break

    if not results:
        return f"No open places found matching '{query}' nearby."

    count = len(results)
    if count == 1:
        return f"I found one option: {results[0]}."
    elif count == 2:
        return f"I found 2 options: {results[0]}, and {results[1]}."
    else:
        return f"I found 3 options: {results[0]}, {results[1]}, and {results[2]}."


async def get_places(query: str) -> str:
    """Search for nearby places matching a keyword query.

    Args:
        query: What kind of place to find (e.g. 'coffee shop', 'italian restaurant').

    Returns:
        Voice-optimized prose with up to 3 open venue results.
    """
    return await asyncio.to_thread(_get_places_sync, query)
