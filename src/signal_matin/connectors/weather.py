"""Meteo Open-Meteo, sans cle API."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from ..models import DataSourceStatus, DataState, WeatherBlock

_CODES = {
    0: "Ciel degage", 1: "Peu nuageux", 2: "Partiellement nuageux",
    3: "Couvert", 45: "Brouillard", 48: "Brouillard givrant",
    51: "Bruine", 53: "Bruine", 55: "Bruine forte", 61: "Pluie faible",
    63: "Pluie", 65: "Pluie forte", 71: "Neige faible", 73: "Neige",
    75: "Neige forte", 80: "Averses", 81: "Averses", 82: "Fortes averses",
    95: "Orage", 96: "Orage et grele", 99: "Orage et grele",
}

_WIND_DIRECTIONS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW", "N"
]


def _wind_direction_to_cardinal(degrees: float) -> str:
    """Convertit des degres en direction cardinal."""
    if degrees < 0 or degrees >= 360:
        return "N"
    index = round(degrees / 22.5)
    return _WIND_DIRECTIONS[index % 16]


def _json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Signal-Matin/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def collect_weather(config: dict) -> tuple[WeatherBlock | None, DataSourceStatus]:
    location = str(config.get("location") or "").strip()
    latitude = config.get("latitude")
    longitude = config.get("longitude")
    if latitude is None or longitude is None:
        return None, DataSourceStatus(
            name="Meteo", state=DataState.UNAVAILABLE,
            detail="Coordonnees absentes dans la configuration.",
        )
    params = urllib.parse.urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "daily": "temperature_2m_min,temperature_2m_max",
        "forecast_days": 1,
        "timezone": "auto",
    })
    try:
        data = _json("https://api.open-meteo.com/v1/forecast?" + params)
        current = data["current"]
        daily = data.get("daily") or {}
        code = int(current.get("weather_code", -1))
        condition = _CODES.get(code, "Temps variable")
        wind = round(float(current.get("wind_speed_10m", 0)))
        wind_direction = float(current.get("wind_direction_10m")) if current.get("wind_direction_10m") is not None else None
        wind_gust = round(float(current.get("wind_gusts_10m", 0))) if current.get("wind_gusts_10m") is not None else None
        low = (daily.get("temperature_2m_min") or [None])[0]
        high = (daily.get("temperature_2m_max") or [None])[0]
        wet = any(word in condition.lower() for word in ("pluie", "averse", "bruine", "orage"))
        
        # Convertir la direction du vent en degres vers une direction cardinal
        direction_str = _wind_direction_to_cardinal(wind_direction) if wind_direction is not None else None
        
        # Construire le summary avec les details du vent
        if wind_gust and wind_gust > wind:
            wind_summary = f"vent {direction_str} {wind} km/h, rafales à {wind_gust} km/h" if direction_str else f"vent {wind} km/h, rafales à {wind_gust} km/h"
        else:
            wind_summary = f"vent {direction_str} {wind} km/h" if direction_str else f"vent {wind} km/h"
        
        block = WeatherBlock(
            location=location or "Position configuree",
            condition=condition,
            temperature_c=round(float(current["temperature_2m"])),
            low_c=round(float(low)) if low is not None else None,
            high_c=round(float(high)) if high is not None else None,
            wind_kmh=wind,
            wind_direction=wind_direction,
            wind_gust_kmh=wind_gust,
            summary=f"{condition}, {wind_summary}.",
            advice="Prevois de quoi rester au sec." if wet else "Conditions calmes pour commencer la journee.",
        )
        return block, DataSourceStatus(
            name="Meteo", state=DataState.LIVE, detail="Open-Meteo", item_count=1,
        )
    except Exception as error:
        return None, DataSourceStatus(
            name="Meteo", state=DataState.UNAVAILABLE,
            detail=f"Open-Meteo indisponible: {type(error).__name__}.",
        )
