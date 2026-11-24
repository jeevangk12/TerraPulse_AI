from __future__ import annotations

from datetime import datetime, timezone
from math import cos, radians
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config.locations import LOCATIONS, find_location
from app.config.settings import settings
from app.engine.risk_engine import RULES, calculate_risk, crop_parameters, supported_crops
from app.models.schemas import AdvisoryRequest, SatelliteAnalyzeRequest
from app.services.advisory import AdvisoryNotConfigured, AdvisoryProviderError, generate_advisory
from app.services.history import HistoryProviderError, get_forecast_context
from app.services.satellite import SatelliteProviderError, analyze as analyze_satellite, status as satellite_status
from app.services.weather import WeatherProviderError, get_forecast

app = FastAPI(
    title="TerraPulse AI API",
    version="0.1.0",
    description="Weather-backed agricultural climate-risk decision support for Karnataka demo locations.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


async def _weather_for(name: str, latitude: float, longitude: float, timeout_seconds: float | None = None) -> dict[str, Any]:
    kwargs = {} if timeout_seconds is None else {"timeout_seconds": timeout_seconds}
    data = await get_forecast(latitude, longitude, **kwargs)
    data["location"] = name
    data["requested_coordinates"] = {"latitude": latitude, "longitude": longitude}
    return data


def _known_location(name: str) -> tuple[str, dict[str, float]]:
    found = find_location(name)
    if found is None:
        raise HTTPException(status_code=404, detail="This location is not in the Karnataka demo list.")
    canonical, coordinates = found
    return canonical, dict(coordinates)


def _known_crop(crop: str) -> str:
    parameters = crop_parameters(crop)
    if parameters is None:
        raise HTTPException(status_code=422, detail=f"Unsupported crop. Choose one of: {', '.join(supported_crops())}.")
    return str(parameters["name"])


@app.get("/api/health")
async def health() -> dict[str, Any]:
    copernicus_configured = bool(settings.copernicus_client_id and settings.copernicus_client_secret)
    return {
        "status": "healthy",
        "weather_api": "configured",
        "gemini_configured": bool(settings.gemini_api_key),
        "copernicus_configured": copernicus_configured,
        "provider_reachability_checked": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/locations")
async def locations() -> dict[str, Any]:
    return {
        "locations": [
            {"name": name, "latitude": coords["latitude"], "longitude": coords["longitude"]}
            for name, coords in LOCATIONS.items()
        ]
    }


@app.get("/api/crops")
async def crops() -> dict[str, Any]:
    return {"crops": supported_crops(), "threshold_status": RULES["threshold_status"], "rule_version": RULES["rule_version"]}


@app.get("/api/weather")
async def weather_at_coordinates(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> dict[str, Any]:
    try:
        data = await _weather_for("Custom coordinates", latitude, longitude)
    except WeatherProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return data


@app.get("/api/weather/{location}")
async def weather_by_location(location: str) -> dict[str, Any]:
    canonical, coords = _known_location(location)
    try:
        return await _weather_for(canonical, coords["latitude"], coords["longitude"])
    except WeatherProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/risk/{location}")
async def risk_by_location(location: str, crop: str = Query(..., min_length=1, max_length=40)) -> dict[str, Any]:
    canonical, coords = _known_location(location)
    crop_name = _known_crop(crop)
    try:
        weather_data = await _weather_for(canonical, coords["latitude"], coords["longitude"])
        risk = calculate_risk(weather_data, crop_name)
        risk.update({"location": canonical, "crop": crop_name, "source": "Open-Meteo", "retrieved_at": weather_data.get("retrieved_at")})
        return risk
    except WeatherProviderError as exc:
        risk = calculate_risk({}, crop_name)
        risk["location"] = canonical
        risk["crop"] = crop_name
        risk["source"] = "Open-Meteo"
        risk["limitations"].insert(0, f"Weather input was unavailable: {exc}")
        return risk


@app.get("/api/history/{location}")
async def historical_context(location: str) -> dict[str, Any]:
    canonical, coords = _known_location(location)
    try:
        forecast = await _weather_for(canonical, coords["latitude"], coords["longitude"])
        context = await get_forecast_context(coords["latitude"], coords["longitude"], forecast)
    except WeatherProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except HistoryProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    context["location"] = canonical
    return context


@app.get("/api/satellite/status")
async def satellite_integration_status() -> dict[str, object]:
    return satellite_status()


def _resolve_satellite_area(request: SatelliteAnalyzeRequest) -> tuple[str, dict[str, object], str]:
    """Return (label, GeoJSON polygon, area_type) for a satellite request."""
    geometry = request.geometry
    if geometry and geometry.get("type") == "Polygon":
        return request.location or "Custom field", geometry, "field_polygon"
    if geometry and geometry.get("type") == "Point":
        longitude, latitude = geometry["coordinates"]
        label, area_type = request.location or "Custom coordinates", "coordinate_buffer"
    elif request.latitude is not None and request.longitude is not None:
        latitude, longitude = request.latitude, request.longitude
        label, area_type = request.location or "Custom coordinates", "coordinate_buffer"
    else:
        label, coordinates = _known_location(request.location or "")
        latitude, longitude = coordinates["latitude"], coordinates["longitude"]
        area_type = "demo_location_buffer"
    return label, _point_buffer_geometry(float(latitude), float(longitude)), area_type


@app.post("/api/satellite/analyze")
async def satellite_analyze(request: SatelliteAnalyzeRequest) -> dict[str, object]:
    location, geometry, area_type = _resolve_satellite_area(request)
    try:
        return await analyze_satellite(location, request.date_from, request.date_to, geometry, area_type)
    except SatelliteProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _point_buffer_geometry(latitude: float, longitude: float) -> dict[str, object]:
    lat_delta = 500 / 111_320
    lon_delta = 500 / (111_320 * max(0.15, abs(cos(radians(latitude)))))
    west, east = max(-180.0, longitude - lon_delta), min(180.0, longitude + lon_delta)
    south, north = max(-90.0, latitude - lat_delta), min(90.0, latitude + lat_delta)
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }


@app.post("/api/advisory")
async def advisory(request: AdvisoryRequest) -> dict[str, Any]:
    canonical, coords = _known_location(request.location)
    crop_name = _known_crop(request.crop)
    try:
        weather_data = await _weather_for(canonical, coords["latitude"], coords["longitude"], timeout_seconds=6)
    except WeatherProviderError as exc:
        weather_data = {
            "source": "Open-Meteo",
            "retrieved_at": None,
            "weather_status": "unavailable",
            "weather_error": str(exc),
        }
    risk = calculate_risk(weather_data, crop_name)
    if weather_data.get("weather_error"):
        risk["limitations"].insert(0, f"Weather input was unavailable: {weather_data['weather_error']}")
    try:
        text = await generate_advisory(canonical, crop_name, request.question, weather_data, risk)
    except AdvisoryNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AdvisoryProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "location": canonical,
        "crop": crop_name,
        "advisory": text,
        "weather_source": weather_data.get("source", "Unavailable"),
        "weather_retrieved_at": weather_data.get("retrieved_at"),
        "ai_model": settings.gemini_model,
    }
