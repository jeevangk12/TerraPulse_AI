from app.engine.risk_engine import RULES, calculate_risk, crop_parameters, supported_crops
from app.services.weather import current_soil_moisture


def weather(rain=None, highs=None, soil=True):
    rain = [5.0] * 7 if rain is None else rain
    highs = [30.0] * 7 if highs is None else highs
    data = {
        "current": {"time": "2026-11-23T14:15"},
        "daily": {"precipitation_sum": rain, "temperature_2m_max": highs},
        "hourly": {"time": ["2026-11-23T00:00", "2026-11-23T13:00", "2026-11-23T14:00", "2026-11-23T15:00"]},
        "hourly_units": {"soil_moisture_7_to_28cm": "m³/m³"},
    }
    if soil:
        data["hourly"]["soil_moisture_7_to_28cm"] = [0.40, 0.30, 0.10, 0.35]
    return data


def test_weights_sum_to_one_and_cover_four_components():
    assert set(RULES["weights"]) == {"drought", "heat", "excessive_rain", "soil_moisture_stress"}
    assert abs(sum(RULES["weights"].values()) - 1.0) < 1e-9


def test_all_six_spec_crops_supported_case_insensitive():
    assert set(supported_crops()) == {"Sugarcane", "Rice", "Ragi", "Maize", "Cotton", "Groundnut"}
    assert crop_parameters("  rice ")["name"] == "Rice"
    assert crop_parameters("wheat") is None


def test_soil_moisture_uses_current_hour_not_midnight():
    soil = current_soil_moisture(weather())
    assert soil["soil_moisture_7_to_28cm"]["value"] == 0.10
    assert soil["soil_moisture_7_to_28cm"]["time"] == "2026-11-23T14:00"


def test_scores_are_bounded_and_composite_follows_formula():
    result = calculate_risk(weather(rain=[0.0] * 7, highs=[45.0] * 7), "Sugarcane")
    parts = result["components"]
    for item in parts.values():
        assert 0 <= item["score"] <= 100
    expected = sum(RULES["weights"][k] * parts[k]["score"] for k in RULES["weights"])
    assert result["overall_score"] == round(expected, 1)
    assert result["data_completeness"] == "complete"


def test_missing_soil_is_unknown_not_zero_and_blocks_composite():
    result = calculate_risk(weather(soil=False), "Rice")
    soil = result["components"]["soil_moisture_stress"]
    assert soil["score"] is None and soil["status"] == "unknown"
    assert result["overall_score"] is None and result["risk_level"] is None
    assert result["data_completeness"] == "partial"
    assert any("Soil-moisture" in text for text in result["limitations"])


def test_no_weather_is_incomplete_with_no_scores():
    result = calculate_risk({}, "Maize")
    assert result["data_completeness"] == "incomplete"
    assert all(item["score"] is None for item in result["components"].values())


def test_partial_precipitation_series_is_unknown():
    result = calculate_risk(weather(rain=[1.0, None, 1.0, 1.0, 1.0, 1.0, 1.0]), "Rice")
    assert result["components"]["drought"]["score"] is None
    assert result["components"]["excessive_rain"]["score"] is None


def test_risk_bands():
    low = calculate_risk(weather(rain=[10.0] * 7, highs=[28.0] * 7), "Rice")
    assert low["risk_level"] == "Low"
    high = calculate_risk(weather(rain=[0.0] * 7, highs=[48.0] * 7), "Rice")
    assert high["risk_level"] in {"High", "Critical"}
