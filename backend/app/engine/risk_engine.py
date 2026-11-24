from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.services.weather import current_soil_moisture

RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "crops.json"
with RULES_PATH.open(encoding="utf-8") as rules_file:
    RULES = json.load(rules_file)


def supported_crops() -> list[str]:
    return list(RULES["crops"].keys())


def crop_parameters(crop: str) -> dict[str, Any] | None:
    for name, params in RULES["crops"].items():
        if name.casefold() == crop.strip().casefold():
            return {"name": name, **params}
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _series(data: dict[str, Any], group: str, key: str) -> list[float | None]:
    values = data.get(group, {}).get(key, [])
    if not isinstance(values, list):
        return []
    return [_number(value) for value in values]


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _unknown(message: str) -> dict[str, Any]:
    return {"score": None, "status": "unknown", "evidence": [], "missing_reason": message}


def calculate_risk(weather: dict[str, Any], crop: str) -> dict[str, Any]:
    parameters = crop_parameters(crop)
    if parameters is None:
        raise ValueError("Unsupported crop.")

    precipitation = _series(weather, "daily", "precipitation_sum")
    maximums = _series(weather, "daily", "temperature_2m_max")
    params = parameters
    components: dict[str, dict[str, Any]] = {}
    limitations: list[str] = []

    valid_precip = [value for value in precipitation if value is not None]
    if len(valid_precip) == 7:
        total_rain = sum(valid_precip)
        target = float(params["rain_target_mm_7d"])
        components["drought"] = {
            "score": _clamp((target - total_rain) / target * 100),
            "status": "available",
            "evidence": [f"Seven-day forecast precipitation: {total_rain:.1f} mm.", f"Prototype crop reference: {target:.1f} mm over seven days."],
        }
    else:
        components["drought"] = _unknown("Seven daily precipitation values were not available.")
        limitations.append("Rainfall-deficit score is unknown because the complete seven-day precipitation forecast was unavailable.")

    valid_maximums = [value for value in maximums if value is not None]
    if len(maximums) == 7 and len(valid_maximums) == 7:
        maximum = max(valid_maximums)
        threshold = float(params["heat_threshold_c"])
        components["heat"] = {
            "score": _clamp((maximum - threshold) * 10),
            "status": "available",
            "evidence": [f"Highest daily maximum in the forecast: {maximum:.1f} °C.", f"Prototype crop heat threshold: {threshold:.1f} °C."],
        }
    else:
        components["heat"] = _unknown("Daily maximum temperature was unavailable.")
        limitations.append("Heat-stress score is unknown because a complete seven-day maximum-temperature forecast was unavailable.")

    if len(precipitation) == 7 and len(valid_precip) == 7:
        wettest_day = max(valid_precip)
        threshold = float(params["heavy_rain_threshold_mm_day"])
        components["excessive_rain"] = {
            "score": _clamp((wettest_day - threshold) / threshold * 100),
            "status": "available",
            "evidence": [f"Largest daily precipitation sum in the forecast: {wettest_day:.1f} mm.", f"Prototype heavy-rain reference: {threshold:.1f} mm in one day."],
        }
    else:
        components["excessive_rain"] = _unknown("Daily precipitation was unavailable.")
        limitations.append("Excess-rain score is unknown because a complete seven-day precipitation forecast was unavailable.")

    soil_value = None
    soil_layer = None
    soil_time = None
    soil_now = weather.get("soil_moisture_current")
    if not isinstance(soil_now, dict):
        soil_now = current_soil_moisture(weather)
    for key, layer in (
        ("soil_moisture_7_to_28cm", "7–28 cm layer"),
        ("soil_moisture_0_to_7cm", "0–7 cm layer"),
        ("soil_moisture_28_to_100cm", "28–100 cm layer"),
    ):
        item = soil_now.get(key)
        candidate = _number(item.get("value")) if isinstance(item, dict) else None
        if candidate is not None:
            soil_value, soil_layer = candidate, layer
            soil_time = item.get("time")
            break

    if soil_value is not None:
        threshold = float(params["soil_moisture_min_m3_m3"])
        components["soil_moisture_stress"] = {
            "score": _clamp((threshold - soil_value) / threshold * 100),
            "status": "available",
            "evidence": [f"Modelled soil moisture at the {soil_layer}{f' ({soil_time})' if soil_time else ''}: {soil_value:.3f} m³/m³.", f"Prototype crop reference: {threshold:.3f} m³/m³."],
        }
    else:
        components["soil_moisture_stress"] = _unknown("No supported soil-moisture value was returned.")
        limitations.append("Soil-moisture stress is unknown because the provider returned no supported soil-moisture value.")

    known_scores = [component["score"] for component in components.values() if component["score"] is not None]
    completeness = round(len(known_scores) / 4 * 100)
    complete = len(known_scores) == 4
    overall = None
    level = None
    if complete:
        overall = round(sum(RULES["weights"][name] * components[name]["score"] for name in RULES["weights"]), 1)
        level = "Low" if overall < 25 else "Moderate" if overall < 50 else "High" if overall < 75 else "Critical"

    return {
        "overall_score": overall,
        "risk_level": level,
        "components": components,
        "data_completeness": "complete" if complete else "partial" if known_scores else "incomplete",
        "data_completeness_percent": completeness,
        "weights": RULES["weights"],
        "rule_version": RULES["rule_version"],
        "threshold_status": RULES["threshold_status"],
        "thresholds": params,
        "limitations": limitations,
    }
