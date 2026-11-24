import dataclasses

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.services.weather import WeatherProviderError

client = TestClient(main.app)

FAKE = {
    "source": "Open-Meteo",
    "retrieved_at": "2026-11-23T08:00:00+00:00",
    "current": {"time": "2026-11-23T14:15", "temperature_2m": 28.0},
    "daily": {"time": [f"2026-11-{23 + i:02d}" for i in range(7)], "precipitation_sum": [4.0] * 7, "temperature_2m_max": [31.0] * 7},
    "hourly": {"time": ["2026-11-23T14:00"], "soil_moisture_7_to_28cm": [0.2]},
    "soil_moisture_status": "available",
}


@pytest.fixture
def fake_weather(monkeypatch):
    async def ok(latitude, longitude, **_):
        return dict(FAKE)
    monkeypatch.setattr(main, "get_forecast", ok)


@pytest.fixture
def failing_weather(monkeypatch):
    async def boom(latitude, longitude, **_):
        raise WeatherProviderError("The weather provider timed out. Try again shortly.", 504)
    monkeypatch.setattr(main, "get_forecast", boom)


def test_health_schema():
    body = client.get("/api/health").json()
    assert body["status"] == "healthy"
    assert {"weather_api", "gemini_configured", "copernicus_configured", "provider_reachability_checked"} <= set(body)
    assert body["provider_reachability_checked"] is False


def test_locations_and_crops():
    locations = client.get("/api/locations").json()["locations"]
    assert len(locations) == 7
    for loc in locations:
        assert -90 <= loc["latitude"] <= 90 and -180 <= loc["longitude"] <= 180
    assert len(client.get("/api/crops").json()["crops"]) == 6


def test_unknown_location_404():
    assert client.get("/api/weather/Atlantis").status_code == 404
    assert client.get("/api/risk/Atlantis", params={"crop": "Rice"}).status_code == 404


@pytest.mark.parametrize("params", [{"latitude": 91, "longitude": 0}, {"latitude": 0, "longitude": 181}, {"latitude": "x", "longitude": 0}])
def test_invalid_coordinates_422(params):
    assert client.get("/api/weather", params=params).status_code == 422


def test_unsupported_crop_422():
    assert client.get("/api/risk/Mandya", params={"crop": "Wheat"}).status_code == 422


def test_weather_by_location_is_case_insensitive(fake_weather):
    body = client.get("/api/weather/mandya").json()
    assert body["location"] == "Mandya"


def test_risk_with_weather(fake_weather):
    body = client.get("/api/risk/Mandya", params={"crop": "rice"}).json()
    assert body["crop"] == "Rice" and body["data_completeness"] == "complete"
    assert 0 <= body["overall_score"] <= 100


def test_risk_degrades_when_weather_provider_fails(failing_weather):
    response = client.get("/api/risk/Mandya", params={"crop": "Rice"})
    assert response.status_code == 200
    body = response.json()
    assert body["overall_score"] is None and body["data_completeness"] == "incomplete"
    assert "unavailable" in body["limitations"][0]


def test_weather_provider_failure_is_controlled(failing_weather):
    assert client.get("/api/weather/Mandya").status_code == 504


def test_advisory_without_key_returns_503(fake_weather, monkeypatch):
    import app.services.advisory as advisory
    monkeypatch.setattr(advisory, "settings", dataclasses.replace(advisory.settings, gemini_api_key=""))
    response = client.post("/api/advisory", json={"location": "Mandya", "crop": "Rice", "question": "Risks?"})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]  # names the variable, never the value


def test_advisory_rejects_extra_fields_and_empty_question():
    assert client.post("/api/advisory", json={"location": "Mandya", "crop": "Rice", "question": ""}).status_code == 422
    assert client.post("/api/advisory", json={"location": "Mandya", "crop": "Rice", "question": "x", "role": "admin"}).status_code == 422


def test_satellite_not_configured_is_explicit_no_data(monkeypatch):
    import app.services.satellite as satellite
    monkeypatch.setattr(satellite, "settings", dataclasses.replace(satellite.settings, copernicus_client_id=""))
    body = client.post("/api/satellite/analyze", json={"location": "Mandya", "date_from": "2026-10-01", "date_to": "2026-11-01"}).json()
    assert body["available"] is False and body["status"] == "not_configured" and body["ndvi_mean"] is None


@pytest.mark.parametrize("payload", [
    {"location": "Mandya", "date_from": "2026-11-02", "date_to": "2026-11-01"},
    {"location": "Mandya", "date_from": "2026-01-01", "date_to": "2026-11-01"},
    {"date_from": "2026-10-01", "date_to": "2026-11-01"},
    {"latitude": 12.5, "date_from": "2026-10-01", "date_to": "2026-11-01"},
])
def test_satellite_validation_422(payload):
    assert client.post("/api/satellite/analyze", json=payload).status_code == 422


def test_satellite_unknown_location_404():
    payload = {"location": "Atlantis", "date_from": "2026-10-01", "date_to": "2026-11-01"}
    assert client.post("/api/satellite/analyze", json=payload).status_code == 404
