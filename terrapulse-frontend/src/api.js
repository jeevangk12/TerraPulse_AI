const BASE = import.meta.env.VITE_API_BASE_URL || '';
const TIMEOUT_MS = 30000;

async function request(path, options = {}, timeoutMs = TIMEOUT_MS) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(BASE + path, { ...options, signal: ctrl.signal });
  } catch (e) {
    throw new Error(
      e.name === 'AbortError'
        ? 'The request timed out. Try again in a moment.'
        : 'The backend could not be reached. Check that it is running, then retry.'
    );
  } finally {
    clearTimeout(timer);
  }
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    let detail = body && body.detail;
    // FastAPI validation errors (HTTP 422) return a list of {msg, loc} objects.
    if (Array.isArray(detail)) detail = detail.map((d) => (d && d.msg ? String(d.msg).replace(/^Value error, /, '') : '')).filter(Boolean).join(' ');
    const fallback =
      res.status === 404 ? 'This resource was not found.'
      : res.status === 422 ? 'The request was not valid.'
      : res.status === 429 ? 'Too many requests. Wait a moment, then retry.'
      : `The service returned status ${res.status}.`;
    const err = new Error(typeof detail === 'string' && detail ? detail : fallback);
    err.status = res.status;
    throw err;
  }
  return body;
}

const post = (path, data, timeoutMs = TIMEOUT_MS) =>
  request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }, timeoutMs);

export const getHealth = () => request('/api/health');
export const getLocations = () => request('/api/locations');
export const getCrops = () => request('/api/crops');
export const getWeather = (loc) => request(`/api/weather/${encodeURIComponent(loc)}`);
export const getWeatherAt = (latitude, longitude) => request(`/api/weather?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`);
export const getHistorical = (loc) => request(`/api/history/${encodeURIComponent(loc)}`);
export const getRisk = (loc, crop) => request(`/api/risk/${encodeURIComponent(loc)}?crop=${encodeURIComponent(crop)}`);
export const getSatelliteStatus = () => request('/api/satellite/status');
export const analyzeSatellite = (location, date_from, date_to) => post('/api/satellite/analyze', { location, date_from, date_to });
export const getAdvisory = (location, crop, question) => post('/api/advisory', { location, crop, question }, 60_000);
