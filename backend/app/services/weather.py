from __future__ import annotations

import asyncio
import copy
import time
from datetime import datetime, timezone
from typing import Any

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CORE_PARAMS = {
    "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
    "hourly": "temperature_2m,precipitation,precipitation_probability",
    "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum,precipitation_probability_max",
    "timezone": "Asia/Kolkata",
    "forecast_days": 7,
    "temperature_unit": "celsius",
    "wind_speed_unit": "kmh",
    "precipitation_unit": "mm",
}
SOIL_PARAMS = {
    "hourly": "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm",
    "timezone": "Asia/Kolkata",
    "forecast_days": 7,
}
SOIL_KEYS = (
    "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm",
)
CACHE_SECONDS = 600
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = asyncio.Lock()


class WeatherProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def current_soil_moisture(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the soil-moisture value for the hour matching the current reading.

    Open-Meteo hourly series start at local midnight, so taking index 0 would
    report a value from the start of the day, not from now. Times are local ISO
    strings (Asia/Kolkata), so they compare correctly as strings.
    """
    hourly = payload.get("hourly") if isinstance(payload.get("hourly"), dict) else {}
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    units = payload.get("hourly_units") if isinstance(payload.get("hourly_units"), dict) else {}
    times = hourly.get("time") if isinstance(hourly.get("time"), list) else []
    now = current.get("time") if isinstance(current.get("time"), str) else None
    index = 0
    if now:
        for i, t in enumerate(times):
            if isinstance(t, str) and t <= now:
                index = i
            else:
                break
    result: dict[str, dict[str, Any]] = {}
    for key in SOIL_KEYS:
        series = hourly.get(key)
        if not isinstance(series, list) or index >= len(series):
            continue
        value = series[index]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            continue
        result[key] = {"value": float(value), "unit": units.get(key), "time": times[index] if index < len(times) else None}
    return result


def _cache_key(latitude: float, longitude: float) -> str:
    return f"{latitude:.4f}:{longitude:.4f}"


def _validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise WeatherProviderError("Open-Meteo returned an invalid response.")
    if payload.get("error"):
        raise WeatherProviderError("Open-Meteo could not return weather for this location.")
    if not isinstance(payload.get("current"), dict) or not isinstance(payload.get("daily"), dict):
        raise WeatherProviderError("Open-Meteo returned an incomplete weather response.")
    return payload


async def _request_json(client: httpx.AsyncClient, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = await client.get(FORECAST_URL, params=params)
    except httpx.TimeoutException as exc:
        raise WeatherProviderError("The weather provider timed out. Try again shortly.", 504) from exc
    except httpx.RequestError as exc:
        raise WeatherProviderError("The weather provider could not be reached.", 502) from exc

    if response.status_code == 429:
        raise WeatherProviderError("The weather provider rate limit was reached. Try again shortly.", 503)
    if response.is_error:
        raise WeatherProviderError(f"The weather provider returned HTTP {response.status_code}.", 502)
    try:
        payload = response.json()
    except ValueError as exc:
        raise WeatherProviderError("The weather provider returned malformed data.", 502) from exc
    if not isinstance(payload, dict):
        raise WeatherProviderError("The weather provider returned malformed data.", 502)
    if payload.get("error"):
        reason = payload.get("reason")
        safe_reason = reason if isinstance(reason, str) and len(reason) < 180 else "the requested variables were unavailable"
        raise WeatherProviderError(f"The weather provider rejected the request: {safe_reason}.", 502)
    return payload


async def get_forecast(latitude: float, longitude: float, timeout_seconds: float = 12) -> dict[str, Any]:
    key = _cache_key(latitude, longitude)
    async with _cache_lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return copy.deepcopy(cached[1])

    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5))
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "TerraPulse-AI/0.1"}) as client:
        core_params = {**CORE_PARAMS, "latitude": latitude, "longitude": longitude}
        payload = _validate_payload(await _request_json(client, core_params))

        # Soil models and supported depths vary by forecast source. A missing soil
        # variable must not discard otherwise valid weather data.
        soil_status = "unavailable"
        try:
            soil = await _request_json(client, {**SOIL_PARAMS, "latitude": latitude, "longitude": longitude})
            soil_hourly = soil.get("hourly")
            if isinstance(soil_hourly, dict):
                base_hourly = payload.setdefault("hourly", {})
                if soil_hourly.get("time") == base_hourly.get("time"):
                    for name in SOIL_KEYS:
                        if name in soil_hourly:
                            base_hourly[name] = soil_hourly[name]
                    payload.setdefault("hourly_units", {}).update(soil.get("hourly_units", {}))
                    soil_status = "available" if any(name in base_hourly for name in SOIL_KEYS) else "unavailable"
        except WeatherProviderError:
            soil_status = "unavailable"

    payload["soil_moisture_status"] = soil_status
    payload["soil_moisture_current"] = current_soil_moisture(payload)
    payload["source"] = "Open-Meteo"
    payload["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    async with _cache_lock:
        _cache[key] = (time.monotonic(), copy.deepcopy(payload))
    return payload
