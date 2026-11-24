from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from math import cos, isfinite, radians
from typing import Any

import httpx

from app.config.settings import settings

PROVIDER = "Copernicus Data Space Ecosystem / Sentinel-2 Level-2A"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
MIN_VALID_PIXEL_COVERAGE = 10.0

_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "quality", bands: 2, sampleType: "UINT8" },
      { id: "dataMask", bands: 2 }
    ]
  };
}

function evaluatePixel(sample) {
  // SCL classes: 3 cloud shadow, 8/9 cloud (medium/high probability), 10 thin cirrus.
  // Class 7 is "unclassified", not cloud: it is excluded from NDVI but not counted as cloud.
  const cloudyOrShadow = [3, 8, 9, 10].includes(sample.SCL);
  const invalid = [0, 1, 3, 7, 8, 9, 10, 11].includes(sample.SCL);
  const denominator = sample.B08 + sample.B04;
  const covered = sample.dataMask === 1;
  const valid = covered && !invalid && denominator > 0;
  const ndvi = valid ? Math.max(-1, Math.min(1, (sample.B08 - sample.B04) / denominator)) : 0;
  return {
    ndvi: [ndvi],
    quality: [valid ? 1 : 0, covered && cloudyOrShadow ? 1 : 0],
    dataMask: [valid ? 1 : 0, covered ? 1 : 0]
  };
}"""

_token_value: str | None = None
_token_expires_at = datetime.min.replace(tzinfo=timezone.utc)
_token_lock = asyncio.Lock()


class SatelliteProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def status() -> dict[str, object]:
    credentials_configured = bool(settings.copernicus_client_id and settings.copernicus_client_secret)
    return {
        "provider": PROVIDER,
        "configured": credentials_configured,
        "credentials_configured": credentials_configured,
        "integration_available": credentials_configured,
        "processing_available": credentials_configured,
        "status": "ready_to_request" if credentials_configured else "not_configured",
        "maximum_cloud_cover_percent": settings.copernicus_max_cloud_cover_percent,
        "message": (
            "Sentinel-2 search and NDVI statistics are enabled. Provider reachability and scene availability are checked on request."
            if credentials_configured
            else "Add a Copernicus Data Space OAuth client id and secret in the backend .env file to request imagery."
        ),
    }


async def _get_access_token(client: httpx.AsyncClient) -> str:
    global _token_value, _token_expires_at
    now = datetime.now(timezone.utc)
    if _token_value and now < _token_expires_at - timedelta(seconds=45):
        return _token_value
    async with _token_lock:
        now = datetime.now(timezone.utc)
        if _token_value and now < _token_expires_at - timedelta(seconds=45):
            return _token_value
        try:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.copernicus_client_id,
                    "client_secret": settings.copernicus_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.TimeoutException as exc:
            raise SatelliteProviderError("Copernicus authentication timed out. Retry the request.", 504) from exc
        except httpx.RequestError as exc:
            raise SatelliteProviderError("Copernicus authentication could not reach the provider.") from exc
        if response.status_code in (401, 403):
            raise SatelliteProviderError("Copernicus rejected the configured credentials. Check the backend client id and secret.", 503)
        if response.status_code == 429:
            raise SatelliteProviderError("Copernicus authentication is rate limited. Retry later.", 503)
        if response.is_error:
            raise SatelliteProviderError("Copernicus authentication is temporarily unavailable.", 503)
        try:
            body = response.json()
            token = body["access_token"]
            expires_in = max(60, int(body.get("expires_in", 300)))
        except (ValueError, KeyError, TypeError) as exc:
            raise SatelliteProviderError("Copernicus returned an invalid authentication response.") from exc
        if not isinstance(token, str) or not token:
            raise SatelliteProviderError("Copernicus returned an invalid authentication response.")
        _token_value = token
        _token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return token


def _sample_dimensions(geometry: dict[str, Any]) -> tuple[int, int]:
    points = geometry["coordinates"][0]
    longitudes = [float(point[0]) for point in points]
    latitudes = [float(point[1]) for point in points]
    mid_latitude = sum(latitudes) / len(latitudes)
    width_m = (max(longitudes) - min(longitudes)) * 111_320 * max(0.15, abs(cos(radians(mid_latitude))))
    height_m = (max(latitudes) - min(latitudes)) * 111_320
    return max(8, min(256, round(width_m / 10))), max(8, min(256, round(height_m / 10)))


def _stats_for_output(outputs: dict[str, Any], output_id: str, band_id: str) -> dict[str, Any] | None:
    bands = outputs.get(output_id, {}).get("bands", {})
    band = bands.get(band_id)
    # Only fall back to the sole band of a single-band output. Falling back to the
    # first band of a multi-band output would silently return the wrong statistic
    # (e.g. the "valid" band's statistics reported as cloud cover).
    if band is None and len(bands) == 1:
        band = next(iter(bands.values()))
    stats = band.get("stats") if isinstance(band, dict) else None
    return stats if isinstance(stats, dict) else None


def _percent(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, number * 100)) if number == number else None


def _unavailable(
    location: str,
    date_from: date,
    date_to: date,
    status_code: str,
    message: str,
    area_type: str,
) -> dict[str, Any]:
    return {
        "location": location,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "source": PROVIDER,
        "available": False,
        "observation_found": False,
        "status": status_code,
        "message": message,
        "reason": "No suitable Sentinel-2 observation with enough clear, valid pixels was returned for this area and date range.",
        "ndvi_mean": None,
        "ndvi_min": None,
        "ndvi_max": None,
        "observation_date": None,
        "cloud_cover": None,
        "valid_pixel_coverage": None,
        "spatial_coverage": None,
        "area_type": area_type,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


async def analyze(
    location: str,
    date_from: date,
    date_to: date,
    geometry: dict[str, Any],
    area_type: str,
) -> dict[str, Any]:
    if not settings.copernicus_client_id or not settings.copernicus_client_secret:
        return _unavailable(
            location,
            date_from,
            date_to,
            "not_configured",
            "Copernicus credentials are not configured, so no satellite imagery was searched or processed.",
            area_type,
        )

    width, height = _sample_dimensions(geometry)
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    request_body = {
        "input": {
            "bounds": {"geometry": geometry, "properties": {"crs": CRS84}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "leastCC"}}],
        },
        "aggregation": {
            "timeRange": {"from": start.isoformat().replace("+00:00", "Z"), "to": end.isoformat().replace("+00:00", "Z")},
            "aggregationInterval": {"of": "P1D"},
            "width": width,
            "height": height,
            "evalscript": _EVALSCRIPT,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=settings.copernicus_timeout_seconds) as client:
            token = await _get_access_token(client)
            response = await client.post(
                STATS_URL,
                json=request_body,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
    except SatelliteProviderError:
        raise
    except httpx.TimeoutException as exc:
        raise SatelliteProviderError("Sentinel-2 processing timed out. Try a shorter date range or retry later.", 504) from exc
    except httpx.RequestError as exc:
        raise SatelliteProviderError("Sentinel-2 processing could not reach Copernicus Data Space.") from exc

    if response.status_code in (401, 403):
        raise SatelliteProviderError("Copernicus rejected the configured credentials for satellite processing. Check the backend OAuth client.", 503)
    if response.status_code == 429:
        raise SatelliteProviderError("Sentinel-2 processing is rate limited. Retry later.", 503)
    if response.is_error:
        raise SatelliteProviderError("Copernicus could not process this area and date range. Verify credentials and retry.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SatelliteProviderError("Copernicus returned an invalid statistics response.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data", []), list):
        raise SatelliteProviderError("Copernicus returned an invalid statistics response.")
    if payload.get("status") == "FAILED":
        raise SatelliteProviderError("Copernicus could not calculate statistics for this area and date range.")

    candidates: list[dict[str, Any]] = []
    for interval in payload.get("data", []):
        outputs = interval.get("outputs", {}) if isinstance(interval, dict) else {}
        ndvi_stats = _stats_for_output(outputs, "ndvi", "B0")
        valid_stats = _stats_for_output(outputs, "quality", "B0")
        cloud_stats = _stats_for_output(outputs, "quality", "B1")
        if not ndvi_stats or not valid_stats:
            continue
        try:
            mean = float(ndvi_stats["mean"])
            samples = int(ndvi_stats.get("sampleCount", 0))
            spatial_samples = int(valid_stats.get("sampleCount", 0))
            no_data_samples = int(valid_stats.get("noDataCount", 0))
            valid_mean = float(valid_stats.get("mean", 0))
            cloud_mean = float(cloud_stats.get("mean", 0)) if cloud_stats else 0.0
        except (KeyError, TypeError, ValueError):
            continue
        if not all(isfinite(value) for value in (mean, valid_mean, cloud_mean)):
            continue
        total_pixels = spatial_samples + no_data_samples
        spatial_coverage = spatial_samples / total_pixels * 100 if total_pixels else 0.0
        valid_coverage = max(0.0, min(100.0, valid_mean * spatial_coverage))
        observation_date = str(interval.get("interval", {}).get("from", ""))[:10]
        candidates.append({
            "observation_date": observation_date,
            "mean": mean,
            "minimum": ndvi_stats.get("min"),
            "maximum": ndvi_stats.get("max"),
            "sample_count": samples,
            "cloud_cover": max(0.0, min(100.0, cloud_mean * 100)),
            "valid_pixel_coverage": valid_coverage,
            "spatial_coverage": spatial_coverage,
        })

    candidates.sort(key=lambda item: item["observation_date"], reverse=True)
    for observation in candidates:
        if observation["cloud_cover"] > settings.copernicus_max_cloud_cover_percent:
            continue
        if observation["sample_count"] < 10 or observation["valid_pixel_coverage"] < MIN_VALID_PIXEL_COVERAGE:
            continue
        return {
            "location": location,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "source": PROVIDER,
            "available": True,
            "observation_found": True,
            "status": "processed",
            "message": "NDVI statistics were calculated from the latest suitable Sentinel-2 L2A observation in the requested range.",
            "observation_date": observation["observation_date"],
            "ndvi_mean": observation["mean"],
            "ndvi_min": observation["minimum"],
            "ndvi_max": observation["maximum"],
            "sample_count": observation["sample_count"],
            "cloud_cover": observation["cloud_cover"],
            "cloud_method": "Sentinel-2 Scene Classification Layer classes for cloud and shadow pixels.",
            "valid_pixel_coverage": observation["valid_pixel_coverage"],
            "spatial_coverage": observation["spatial_coverage"],
            "area_type": area_type,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "limitations": [
                "NDVI is a vegetation indicator, not a diagnosis of disease, crop type, or yield.",
                "Cloud, cloud-shadow, saturated, and snow pixels are excluded from NDVI statistics.",
                "A named demo location is summarized over a 500 m radius buffer; it is not a farm boundary.",
            ] if area_type in {"demo_location_buffer", "coordinate_buffer"} else [
                "NDVI is a vegetation indicator, not a diagnosis of disease, crop type, or yield.",
                "Cloud, cloud-shadow, saturated, and snow pixels are excluded from NDVI statistics.",
            ],
        }

    if not candidates:
        message = "No Sentinel-2 L2A acquisition with usable pixels was found in this date range."
    elif all(item["cloud_cover"] > settings.copernicus_max_cloud_cover_percent for item in candidates):
        message = f"Imagery was returned, but every observation exceeded the {settings.copernicus_max_cloud_cover_percent:g}% cloud and shadow limit."
    else:
        message = "Imagery was returned, but no observation had enough valid pixels after cloud and shadow masking."
    return _unavailable(location, date_from, date_to, "no_suitable_imagery", message, area_type)
