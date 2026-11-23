# TerraPulse AI

TerraPulse AI is a responsive climate-risk dashboard for selected crops and locations in Karnataka. The frontend is in `terrapulse-frontend`; the FastAPI service is in `backend`.

## Open the dashboard

In VS Code, select **Launch TerraPulse AI** in Run and Debug and press **F5**. It starts the backend on port 8000 and the frontend on port 8080, while reusing either service if it is already running.

- Dashboard: http://127.0.0.1:8080/
- API documentation: http://127.0.0.1:8000/docs

For manual startup, run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend`, then run `npm.cmd run dev -- --host 127.0.0.1 --port 8080` from `terrapulse-frontend`.

Weather and historical context use Open-Meteo. Risk scores are deterministic prototype calculations with configurable, unvalidated crop thresholds. Gemini advisories require a backend `GEMINI_API_KEY`. Sentinel-2 NDVI statistics use Copernicus Data Space's Statistical API when backend OAuth credentials are configured; otherwise, or when there is no suitable clear scene, the dashboard shows an explicit unavailable state.
