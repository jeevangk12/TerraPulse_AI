# TerraPulse AI backend

FastAPI service for Karnataka demo locations, Open-Meteo weather, deterministic prototype risk scoring, historical context, Sentinel-2 statistics, and optional Gemini advisories.

## Run locally

From the `backend` directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The Vite frontend proxies `/api` to `http://127.0.0.1:8000`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

`GEMINI_API_KEY` is optional. Without it, health reports Gemini as unconfigured and `/api/advisory` returns a controlled 503 response. Satellite statistics use the Copernicus Data Space Statistical API and require `COPERNICUS_CLIENT_ID` and `COPERNICUS_CLIENT_SECRET`; without them, analysis returns an explicit no-data state. Credential presence does not imply provider reachability. Keep provider credentials only in this backend `.env` file.

## Endpoints

- `GET /api/health` — configuration state; it does not ping external providers.
- `GET /api/crops` — supported crops, rule version and threshold status.
- `GET /api/locations` — the seven demo points listed in `spec.md`.
- `GET /api/weather/{location}` — current weather, forecast, provider units, retrieval time, and modelled soil moisture when supported.
- `GET /api/weather?latitude=12.52&longitude=76.89` — validated coordinate weather query.
- `GET /api/risk/{location}?crop=Rice` — deterministic risk components, evidence, completeness, weights, thresholds, and limitations.
- `GET /api/history/{location}` — seven-day forecast compared with matching-calendar-day ERA5 normals for 1991–2020. Anomalies are withheld unless at least 20 baseline samples and a forecast value exist.
- `GET /api/satellite/status` and `POST /api/satellite/analyze` — daily Sentinel-2 L2A NDVI, cloud/shadow, valid-pixel, and spatial-coverage statistics when suitable data is returned.
- `POST /api/advisory` — Gemini-generated text grounded in returned weather and deterministic risk evidence.

Satellite analysis accepts a demo `location`, a coordinate pair, or a GeoJSON Point/Polygon. A point is summarized over a 500 m radius buffer; one-ring field polygons are limited to a 0.05-degree bounding box and date ranges to 90 days. An NDVI value is a vegetation indicator, not a diagnosis of disease, crop type, or yield.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```

## Risk rules

Crop thresholds and weights live in `app/config/crops.json`. They are marked `prototype_not_validated`, are not agronomic guidance, and need review by local agricultural experts. The API returns no composite score if a required factor is unknown; missing data is never converted to zero risk.
