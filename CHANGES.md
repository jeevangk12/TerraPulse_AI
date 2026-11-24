# Review changes

**Security / hygiene**
- Removed `backend/.env` containing a live Gemini API key (rotate that key). `.env.example` has no secrets.
- Removed `.taste-skill/` (a Chrome profile with cookies/login databases, ~48 MB), `node_modules/`, stale `dist/`, `__pycache__/`.
- Added root `.gitignore`.

**Bugs fixed**
- Soil moisture used the first hourly value (midnight) instead of the current hour, in the risk engine and UI.
- Satellite: multi-band stats lookup could report the "valid" band as cloud cover; SCL class 7 (unclassified) was counted as cloud.
- `tzdata` was missing from requirements (ZoneInfo fails on Windows).
- Frontend: 90-day satellite range now validated client-side; 422 list errors show readable messages.
- Advisory: `thinking_level` only sent for Gemini 3 models.
- Satellite route refactored (possible unbound variables); unused import removed.

**Added**
- `GET /api/crops` (frontend crop list now comes from backend), 30 pytest tests, `requirements-dev.txt`, `package-lock.json`.
- Docs aligned with the code (spec stack, README setup, root package.json scripts).

**Not changed / still open**: rate limiting before public deploy; crop thresholds remain unvalidated prototypes; Copernicus flow not tested against the live API.
