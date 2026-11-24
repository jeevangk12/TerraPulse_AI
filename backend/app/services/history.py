from __future__ import annotations

import asyncio
import copy
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.config.settings import settings

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
BASELINE_START = "1991-01-01"
BASELINE_END = "2020-12-31"
MINIMUM_BASELINE_SAMPLES = 20
CACHE_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, dict[str, list[dict[str, float | str | None]]]]] = {}
_cache_lock = asyncio.Lock()


class HistoryProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


async def _load_normals(latitude: float, longitude: float) -> dict[str, list[dict[str, float | str | None]]]:
    key = f"{latitude:.3f}:{longitude:.3f}"
    async with _cache_lock:
        item = _cache.get(key)
        if item and time.monotonic() - item[0] < CACHE_SECONDS:
            return copy.deepcopy(item[1])

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": BASELINE_START,
        "end_date": BASELINE_END,
        "daily": "temperature_2m_max,precipitation_sum",
        "timezone": "Asia/Kolkata",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "models": "era5",
    }
    timeout_seconds = max(15, settings.open_meteo_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=6)) as client:
            response = await client.get(ARCHIVE_URL, params=params, headers={"User-Agent": "TerraPulse-AI/0.1"})
    except httpx.TimeoutException as exc:
        raise HistoryProviderError("The historical weather provider timed out.", 504) from exc
    except httpx.RequestError as exc:
        raise HistoryProviderError("The historical weather provider could not be reached.", 502) from exc
    if response.status_code == 429:
        raise HistoryProviderError("The historical weather provider rate limit was reached.", 503)
    if response.is_error:
        raise HistoryProviderError(f"The historical weather provider returned HTTP {response.status_code}.", 502)
    try:
        payload = response.json()
    except ValueError as exc:
        raise HistoryProviderError("The historical weather provider returned malformed data.") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise HistoryProviderError("The historical weather provider could not return the baseline.")

    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    maximums = daily.get("temperature_2m_max", [])
    precipitation = daily.get("precipitation_sum", [])
    grouped: dict[str, list[dict[str, float | str | None]]] = defaultdict(list)
    for index, day in enumerate(dates):
        if not isinstance(day, str) or len(day) < 10:
            continue
        grouped[day[5:10]].append({
            "temperature_2m_max": _finite(maximums[index]) if index < len(maximums) else None,
            "precipitation_sum": _finite(precipitation[index]) if index < len(precipitation) else None,
        })
    normals: dict[str, list[dict[str, float | str | None]]] = {}
    for month_day, values in grouped.items():
        normal_row: dict[str, float | str | None] = {"month_day": month_day}
        for field in ("temperature_2m_max", "precipitation_sum"):
            field_values = [row[field] for row in values if isinstance(row[field], float)]
            normal_row[field] = sum(field_values) / len(field_values) if field_values else None
            normal_row[f"{field}_sample_count"] = len(field_values)
        normals[month_day] = [normal_row]

    if not normals:
        raise HistoryProviderError("The historical weather provider returned no usable baseline values.")
    async with _cache_lock:
        _cache[key] = (time.monotonic(), copy.deepcopy(normals))
    return normals


async def get_forecast_context(latitude: float, longitude: float, forecast: dict[str, Any]) -> dict[str, Any]:
    normals = await _load_normals(latitude, longitude)
    daily = forecast.get("daily", {})
    dates = daily.get("time", [])
    forecast_maximums = daily.get("temperature_2m_max", [])
    forecast_precipitation = daily.get("precipitation_sum", [])
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    rows: list[dict[str, Any]] = []
    limitations: list[str] = []

    for index, day in enumerate(dates[:7]):
        if not isinstance(day, str):
            continue
        month_day = day[5:10]
        baseline_row = normals.get(month_day, [{}])[0]
        temp_samples = int(baseline_row.get("temperature_2m_max_sample_count", 0) or 0)
        rain_samples = int(baseline_row.get("precipitation_sum_sample_count", 0) or 0)
        forecast_max = _finite(forecast_maximums[index]) if index < len(forecast_maximums) else None
        forecast_rain = _finite(forecast_precipitation[index]) if index < len(forecast_precipitation) else None
        normal_max = _finite(baseline_row.get("temperature_2m_max"))
        normal_rain = _finite(baseline_row.get("precipitation_sum"))
        enough_temp = temp_samples >= MINIMUM_BASELINE_SAMPLES and normal_max is not None
        enough_rain = rain_samples >= MINIMUM_BASELINE_SAMPLES and normal_rain is not None
        rows.append({
            "date": day,
            "forecast_temperature_2m_max": forecast_max,
            "baseline_temperature_2m_max_mean": round(normal_max, 1) if normal_max is not None else None,
            "temperature_max_anomaly": round(forecast_max - normal_max, 1) if enough_temp and forecast_max is not None else None,
            "temperature_baseline_sample_count": temp_samples,
            "forecast_precipitation_sum": forecast_rain,
            "baseline_precipitation_sum_mean": round(normal_rain, 1) if normal_rain is not None else None,
            "precipitation_anomaly": round(forecast_rain - normal_rain, 1) if enough_rain and forecast_rain is not None else None,
            "precipitation_baseline_sample_count": rain_samples,
            "anomaly_status": "available" if enough_temp and enough_rain and forecast_max is not None and forecast_rain is not None else "insufficient_data",
        })

    if any(row["anomaly_status"] != "available" for row in rows):
        limitations.append(f"Anomalies are withheld when fewer than {MINIMUM_BASELINE_SAMPLES} matching baseline observations or a forecast value is available.")
    if not rows:
        limitations.append("The forecast provider returned no daily values to compare with the historical baseline.")

    return {
        "source": "Open-Meteo Historical Weather API (ERA5 reanalysis) and Forecast API",
        "baseline_period": {"start": BASELINE_START, "end": BASELINE_END},
        "baseline_method": "Mean daily maximum temperature and precipitation sum for the same month and day across ERA5 1991–2020; forecast anomalies use matching variables and units.",
        "forecast_period": {"start": rows[0]["date"] if rows else None, "end": rows[-1]["date"] if rows else None},
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "Asia/Kolkata",
        "units": {"temperature_2m_max": "°C", "precipitation_sum": "mm"},
        "minimum_baseline_samples_for_anomaly": MINIMUM_BASELINE_SAMPLES,
        "daily": rows,
        "limitations": limitations,
        "note": f"Forecast comparisons are not climate trends. Baseline dates are matched by calendar day; current local date is {today.isoformat()}.",
    }
