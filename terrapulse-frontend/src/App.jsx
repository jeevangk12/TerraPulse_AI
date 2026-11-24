import { useEffect, useMemo, useState } from 'react';
import { useAsync } from './useAsync.js';
import * as api from './api.js';
import { CROPS, DEMO_LOCATIONS } from './config.js';
import { Privacy, Terms } from './pages/Legal.jsx';

const RISK_LABELS = { drought: 'Rainfall deficit', heat: 'Heat stress', excessive_rain: 'Excess rainfall', soil_moisture_stress: 'Soil moisture stress' };
const isNum = (value) => typeof value === 'number' && Number.isFinite(value);
const iso = (date) => date.toISOString().slice(0, 10);
const unwrap = (data) => data?.weather ?? data?.data ?? data ?? {};
const readValue = (value, unit = '') => value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? 'Unavailable' : `${Number(value)}${unit ? ` ${unit}` : ''}`;

function ist(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : `${date.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' })} IST`;
}

function displayDate(value) {
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
}

function normalizeLocations(data) {
  const raw = Array.isArray(data) ? data : Array.isArray(data?.locations) ? data.locations
    : data?.locations && typeof data.locations === 'object' ? Object.entries(data.locations).map(([name, value]) => ({ name, ...(value || {}) }))
      : data && typeof data === 'object' ? Object.entries(data).map(([name, value]) => ({ name, ...(value || {}) })) : [];
  return raw.map((loc) => typeof loc === 'string' ? { name: loc } : {
    name: loc.name ?? loc.location, latitude: loc.latitude ?? loc.lat, longitude: loc.longitude ?? loc.lon ?? loc.lng,
  }).filter((loc) => loc.name);
}

function State({ state, retry, label, children }) {
  if (state.status === 'loading') return <div className="inline-state" role="status"><span className="spinner" />Loading {label}…</div>;
  if (state.status === 'error') return <div className="error-state" role="alert"><span className="state-mark">!</span><div><strong>{label} could not load</strong><p>{state.error.message}</p></div>{retry && <button className="button button--quiet" type="button" onClick={retry}>Try again</button>}</div>;
  return state.status === 'ready' ? children(state.data) : null;
}

function Brand() {
  return <a className="brand" href="#/" aria-label="TerraPulse AI dashboard"><img src="/favicon.svg" alt="" width="30" height="30" /><span>TerraPulse <b>AI</b></span></a>;
}

function ServiceStatus() {
  const [state] = useAsync(() => api.getHealth(), []);
  if (state.status === 'loading' || state.status === 'idle') return <span className="service-status"><i className="status-dot status-dot--pending" />Checking services</span>;
  if (state.status === 'error') return <span className="service-status" title="Start the FastAPI backend to load live data"><i className="status-dot status-dot--off" />Backend unavailable</span>;
  const data = state.data || {};
  return <span className="service-status" title="Configuration only; provider availability is checked when data is requested."><i className={`status-dot ${data.status === 'healthy' ? 'status-dot--on' : 'status-dot--pending'}`} />Backend {data.status ?? 'unknown'}<span className="status-divider" />Weather {data.weather_api ?? 'unknown'}<span className="status-divider" />Gemini {data.gemini_configured ? 'configured' : 'not configured'}</span>;
}

function Sidebar({ active }) {
  const items = [['overview', 'Overview', '◫'], ['weather', 'Weather', '⌁'], ['history', 'Climate context', '↔'], ['risk', 'Climate risk', '◉'], ['satellite', 'Vegetation', '▤'], ['advisory', 'Field advisory', '✳'], ['sources', 'Data notes', '≡']];
  return <aside className="sidebar"><div className="sidebar-brand"><Brand /><span className="sidebar-kicker">Karnataka field monitor</span></div>
    <nav className="side-nav" aria-label="Dashboard sections"><p className="nav-label">Workspace</p>{items.map(([id, label, icon]) => <a key={id} className={`nav-item ${active === id ? 'is-active' : ''}`} href={`#${id}`} aria-current={active === id ? 'location' : undefined}><span className="nav-glyph" aria-hidden="true">{icon}</span>{label}</a>)}</nav>
    <div className="sidebar-bottom"><div className="sidebar-note"><span className="note-line" />Prototype thresholds<br />need local validation.</div><a href="#/privacy">Privacy</a><a href="#/terms">Terms</a><span className="sidebar-version">TerraPulse · MVP 0.1</span></div>
  </aside>;
}

function Metric({ label, value, unit, kind, note }) {
  const shown = value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? 'Unavailable' : `${Number(value)}${unit ? ` ${unit}` : ''}`;
  const icon = kind === 'temperature' ? '°' : kind === 'humidity' ? 'RH' : kind === 'rain' ? 'mm' : '↗';
  return <div className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-symbol metric-symbol--${kind}`} aria-hidden="true">{icon}</span></div><strong>{shown}</strong><small>{note}{unit ? '' : ' · unit not supplied'}</small></div>;
}

function WeatherChart({ daily, units }) {
  const dates = daily.time || [], highs = daily.temperature_2m_max || [], lows = daily.temperature_2m_min || [], rain = daily.precipitation_sum || [], chances = daily.precipitation_probability_max || [];
  const rows = dates.slice(0, 7).map((date, i) => ({ date, high: highs[i], low: lows[i], rain: rain[i], chance: chances[i] })).filter((d) => isNum(d.high) || isNum(d.low) || isNum(d.rain) || isNum(d.chance));
  if (!rows.length) return <div className="empty-chart"><span aria-hidden="true">⌁</span><p>Daily forecast data was not returned for this location.</p></div>;
  const values = rows.flatMap((d) => [d.high, d.low]).filter(isNum);
  const lowBound = values.length ? Math.min(...values) - 2 : 0, highBound = values.length ? Math.max(...values) + 2 : 1;
  const x = (i) => 38 + i * (624 / Math.max(1, rows.length - 1));
  const y = (value) => 153 - ((value - lowBound) / Math.max(1, highBound - lowBound)) * 112;
  const path = (key) => rows.map((d, i) => isNum(d[key]) ? `${i === 0 || !isNum(rows[i - 1]?.[key]) ? 'M' : 'L'} ${x(i)} ${y(d[key])}` : '').filter(Boolean).join(' ');
  const maxRain = Math.max(1, ...rows.map((d) => isNum(d.rain) ? d.rain : 0));
  return <div className="chart-wrap"><div className="chart-legend"><span><i className="legend-dot" />High temperature</span><span><i className="legend-dot legend-dot--low" />Low temperature</span><span><i className="legend-dot legend-dot--rain" />Rainfall</span></div>
    <svg className="forecast-chart" viewBox="0 0 700 220" role="img" aria-labelledby="forecast-title forecast-desc"><title id="forecast-title">Seven-day weather forecast</title><desc id="forecast-desc">Daily minimum and maximum temperatures and precipitation returned by the weather provider.</desc>
      {[48, 100, 153].map((lineY) => <line key={lineY} x1="20" x2="680" y1={lineY} y2={lineY} className="chart-grid" />)}
      {rows.map((d, i) => <rect key={`rain-${d.date}`} className="rain-column" x={x(i) - 13} y={153 - ((isNum(d.rain) ? d.rain : 0) / maxRain) * 40} width="26" height={((isNum(d.rain) ? d.rain : 0) / maxRain) * 40} rx="4" />)}
      {path('high') && <path d={path('high')} className="chart-line chart-line--high" />}{path('low') && <path d={path('low')} className="chart-line chart-line--low" />}
      {rows.map((d, i) => <g key={`day-${d.date}`}>{isNum(d.high) && <circle className="chart-point chart-point--high" cx={x(i)} cy={y(d.high)} r="4" />}{isNum(d.low) && <circle className="chart-point chart-point--low" cx={x(i)} cy={y(d.low)} r="4" />}<text x={x(i)} y="184" textAnchor="middle" className="chart-date">{displayDate(d.date)}</text>{isNum(d.high) && <text x={x(i)} y={y(d.high) - 10} textAnchor="middle" className="chart-value">{d.high}°</text>}</g>)}
    </svg><div className="chart-unit">Temperature ({units.temperature_2m_max || 'unit not supplied'}) · Precipitation ({units.precipitation_sum || 'unit not supplied'})</div>
    <div className="forecast-details" aria-label="Daily forecast values">{rows.map((day) => <article key={`detail-${day.date}`}><time>{displayDate(day.date)}</time><strong>{isNum(day.low) ? `${day.low}°` : '—'} / {isNum(day.high) ? `${day.high}°` : '—'}</strong><span>Rain {isNum(day.rain) ? readValue(day.rain, units.precipitation_sum) : 'Unavailable'}</span><small>Chance {isNum(day.chance) ? `${day.chance}%` : 'Unavailable'}</small></article>)}</div>
  </div>;
}

function WeatherPanel({ query, title }) {
  const [state, reload] = useAsync(query ? () => query.coordinates ? api.getWeatherAt(query.latitude, query.longitude) : api.getWeather(query.location) : null, [query?.key]);
  return <section className="panel weather-panel" id="weather" aria-labelledby="weather-title"><div className="panel-heading"><div><span className="eyebrow">Weather</span><h2 id="weather-title">Conditions and forecast</h2></div><button className="button button--quiet refresh-button" type="button" onClick={reload} disabled={!query || state.status === 'loading'}><span aria-hidden="true">↻</span> Refresh weather</button></div>
    <State state={state} retry={reload} label="weather data">{(response) => {
      const data = unwrap(response), current = data.current || data.current_weather || {}, currentUnits = data.current_units || data.current_weather_units || {}, daily = data.daily || {}, dailyUnits = data.daily_units || {}, hourly = data.hourly || {}, hourlyUnits = data.hourly_units || {};
      const source = response?.source ?? response?.provider ?? data.source ?? 'Open-Meteo', retrieved = response?.retrieved_at ?? response?.fetched_at ?? data.retrieved_at;
      const temperature = current.temperature_2m ?? current.temperature, rain = current.precipitation ?? current.rain, wind = current.wind_speed_10m ?? current.windspeed;
      const soilKeys = [['soil_moisture_0_to_7cm', 'Surface · 0–7 cm'], ['soil_moisture_7_to_28cm', 'Root zone · 7–28 cm'], ['soil_moisture_28_to_100cm', 'Soil · 28–100 cm']];
      const soilValues = soilKeys.map(([key, label]) => ({ key, label, value: data.soil_moisture_current?.[key]?.value ?? current[key], unit: data.soil_moisture_current?.[key]?.unit ?? currentUnits[key] ?? hourlyUnits[key] })).filter((item) => item.value !== null && item.value !== undefined && item.value !== '' && Number.isFinite(Number(item.value)));
      return <><div className="weather-context"><span className="weather-place"><i className="place-pin" aria-hidden="true" />{title || 'Selected location'}</span><span>Forecasts are predictions</span></div>
        <div className="metrics-grid"><Metric label="Air temperature" value={temperature} unit={currentUnits.temperature_2m ?? currentUnits.temperature} kind="temperature" note={current.time ? `Reading · ${String(current.time).replace('T', ' ')} IST` : 'Current reading'} /><Metric label="Relative humidity" value={current.relative_humidity_2m} unit={currentUnits.relative_humidity_2m} kind="humidity" note="Current reading" /><Metric label="Precipitation" value={rain} unit={currentUnits.precipitation} kind="rain" note="Current reading" /><Metric label="Wind speed" value={wind} unit={currentUnits.wind_speed_10m ?? currentUnits.windspeed} kind="wind" note="Current reading" /></div>
        {soilValues.length > 0 && <div className="soil-context"><div><strong>Soil moisture</strong><span>Modelled output · availability varies</span></div>{soilValues.map((item) => <div className="soil-value" key={item.key}><span>{item.label}</span><strong>{readValue(item.value, item.unit)}</strong></div>)}</div>}
        <div className="forecast-block"><div className="forecast-heading"><div><h3>7-day outlook</h3><p>Daily highs, lows and precipitation</p></div><span className="forecast-tz">Asia/Kolkata</span></div><WeatherChart daily={daily} units={dailyUnits} /></div>
        <p className="provenance">Source: {source}{retrieved ? ` · Retrieved ${ist(retrieved)}` : ' · Retrieval time not provided by the backend'}.</p></>;
    }}</State>
  </section>;
}

function HistoricalPanel({ location }) {
  const [requestedLocation, setRequestedLocation] = useState(null);
  const requested = Boolean(location && requestedLocation === location);
  const [state, reload] = useAsync(requested ? () => api.getHistorical(requestedLocation) : null, [requestedLocation, location]);
  useEffect(() => { setRequestedLocation(null); }, [location]);
  const signed = (value, unit) => !isNum(value) ? 'Unavailable' : `${value > 0 ? '+' : ''}${value} ${unit}`;
  return <section className="panel history-panel" id="history" aria-labelledby="history-title">
    <div className="panel-heading"><div><span className="eyebrow">Open-Meteo archive · ERA5</span><h2 id="history-title">Forecast vs historical context</h2></div><span className="rule-version">1991–2020 baseline</span></div>
    <p className="history-intro">Compare the seven-day forecast with the average for the same calendar dates in the historical baseline.</p>
    {!location && <p className="note-block">Historical comparison is available for a named Karnataka demo location.</p>}
    {!requested && location && <div className="history-start"><p>Differences are comparisons with the baseline, not a climate trend or a prediction of crop impact.</p><button className="button button--secondary" type="button" onClick={() => setRequestedLocation(location)}>Compare with historical normal</button></div>}
    {requested && <State state={state} retry={reload} label="historical context">{(data) => <>
      <div className="history-table-wrap"><table className="history-table"><thead><tr><th scope="col">Date</th><th scope="col">Forecast high</th><th scope="col">Baseline mean</th><th scope="col">Difference</th><th scope="col">Forecast rain</th><th scope="col">Baseline mean</th><th scope="col">Difference</th></tr></thead>
        <tbody>{(data.daily || []).map((day) => <tr key={day.date}><th scope="row">{displayDate(day.date)}</th><td>{isNum(day.forecast_temperature_2m_max) ? `${day.forecast_temperature_2m_max} °C` : 'Unavailable'}</td><td>{isNum(day.baseline_temperature_2m_max_mean) ? `${day.baseline_temperature_2m_max_mean} °C` : 'Unavailable'}</td><td>{day.anomaly_status === 'available' ? signed(day.temperature_max_anomaly, '°C') : 'Insufficient baseline'}</td><td>{isNum(day.forecast_precipitation_sum) ? `${day.forecast_precipitation_sum} mm` : 'Unavailable'}</td><td>{isNum(day.baseline_precipitation_sum_mean) ? `${day.baseline_precipitation_sum_mean} mm` : 'Unavailable'}</td><td>{day.anomaly_status === 'available' ? signed(day.precipitation_anomaly, 'mm') : 'Insufficient baseline'}</td></tr>)}</tbody>
      </table></div>
      {Array.isArray(data.limitations) && data.limitations.map((item) => <p className="note-block" key={item}>{item}</p>)}
      <p className="provenance">{data.source} · Baseline {data.baseline_period?.start} to {data.baseline_period?.end} · {data.note}</p>
    </>}</State>}
  </section>;
}

function componentScore(value) {
  const score = isNum(value) ? value : value?.score ?? value?.value;
  return isNum(score) ? score : null;
}

function RiskPanel({ request, stale }) {
  const [state, reload] = useAsync(request ? () => api.getRisk(request.location, request.crop) : null, [request?.key]);
  const [evidenceOpen, setEvidenceOpen] = useState(true);
  return <section className="panel risk-panel" id="risk" aria-labelledby="risk-title"><div className="panel-heading"><div><span className="eyebrow">Risk engine · rule-based</span><h2 id="risk-title">Climate risk</h2></div><span className="rule-version">Prototype rules</span></div>
    {!request && <div className="empty-inline"><span className="empty-orbit" aria-hidden="true">?</span><p>Choose a location and crop, then run a climate-risk analysis.</p></div>}{request && stale && <p className="selection-stale" role="status">The location or crop changed. Run the analysis again to update this result.</p>}
    {request && <State state={state} retry={reload} label="risk analysis">{(data) => {
      const score = isNum(data.overall_score) ? data.overall_score : null, parts = Object.entries(data.components || {});
      const level = data.risk_level || (score === null ? 'Incomplete data' : score < 25 ? 'Low' : score < 50 ? 'Moderate' : score < 75 ? 'High' : 'Critical');
      const levelClass = level.toLowerCase().replaceAll(' ', '-');
      return <><div className="risk-summary"><div className={`risk-gauge ${score === null ? 'risk-gauge--empty' : ''}`} style={score === null ? undefined : { '--score': `${Math.max(0, Math.min(100, score)) * 3.6}deg` }} role="img" aria-label={score === null ? 'Overall climate risk score unavailable' : `Overall climate risk score ${score} out of 100`}><div className="gauge-center"><strong>{score ?? '—'}</strong><span>out of 100</span></div></div>
        <div className="risk-copy"><span className={`risk-label risk-label--${levelClass}`}>{level}</span><h3>{score === null ? 'Score needs more data' : `${level} climate risk`}</h3><p>{request.crop} · {request.location}</p><div className="completeness">Data completeness <strong>{data.data_completeness ?? 'Not provided'}</strong></div></div></div>
        <div className="risk-components"><div className="subheading-row"><h3>Contributing factors</h3><button className="text-button" type="button" aria-expanded={evidenceOpen} onClick={() => setEvidenceOpen((open) => !open)}>{evidenceOpen ? 'Hide details' : 'Show details'}</button></div>
          {parts.length ? <ul className="factor-list">{parts.map(([key, item]) => { const value = componentScore(item), label = RISK_LABELS[key] ?? key.replaceAll('_', ' '), evidence = Array.isArray(item?.evidence) ? item.evidence : item?.evidence ? [item.evidence] : [];
            return <li className="factor" key={key}><div className="factor-row"><span>{label}</span><strong>{value === null ? 'Unknown' : `${value} / 100`}</strong></div><div className="factor-track" role="img" aria-label={`${label}: ${value === null ? 'unknown, not zero risk' : `${value} out of 100`}`}><span style={{ width: `${value === null ? 0 : Math.max(0, Math.min(100, value))}%` }} /></div>{evidenceOpen && evidence.length > 0 && <p className="factor-evidence">{evidence.join(' ')}</p>}</li>;
          })}</ul> : <p className="note-block">The service did not return component scores. Unknown inputs are not treated as zero risk.</p>}</div>
        <div className="risk-footnote"><span>Rule version {data.rule_version ?? 'not supplied'}</span><span>Bands: 0–24 low · 25–49 moderate · 50–74 high · 75–100 critical</span><span>Prototype values; not locally validated</span></div>
        {Array.isArray(data.limitations) && data.limitations.length > 0 && <div className="limitations"><h3>Data limitations</h3><ul>{data.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>}</>;
    }}</State>}
  </section>;
}

function SatellitePanel({ location }) {
  const today = useMemo(() => new Date(), []);
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 30 * 864e5))), [to, setTo] = useState(iso(today)), [request, setRequest] = useState(null);
  const [status] = useAsync(() => api.getSatelliteStatus(), []);
  const [state, reload] = useAsync(request ? () => api.analyzeSatellite(request.location, request.from, request.to) : null, [request?.key]);
  useEffect(() => { setRequest(null); }, [location]);
  const tooLong = (new Date(to) - new Date(from)) / 864e5 > 90, invalidRange = from > to || tooLong;
  return <section className="panel satellite-panel" id="satellite" aria-labelledby="satellite-title"><div className="panel-heading"><div><span className="eyebrow">Sentinel-2 · Copernicus</span><h2 id="satellite-title">Vegetation observation</h2></div><span className="satellite-mark">NDVI</span></div>
    <State state={status} label="satellite status">{(data) => <p className="integration-note"><i className={`status-dot ${data.configured ? 'status-dot--on' : 'status-dot--pending'}`} />Integration {String(data.status ?? (data.configured ? 'configured' : 'not configured'))}. Setup does not confirm a processed observation.</p>}</State>
    {!location && <p className="note-block">Select a demo location to request an imagery search.</p>}
    <form className="date-form" onSubmit={(event) => { event.preventDefault(); if (location && !invalidRange) setRequest({ location, from, to, key: `${location}-${from}-${to}-${Date.now()}` }); }}>
      <label>From<input type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} /></label><label>To<input type="date" value={to} min={from} max={iso(today)} onChange={(event) => setTo(event.target.value)} /></label>
      <button className="button button--secondary" type="submit" disabled={!location || invalidRange || state.status === 'loading'}>{state.status === 'loading' ? 'Searching…' : 'Get satellite data'}</button>
    </form>{invalidRange && <p className="field-error" role="alert">{tooLong ? 'Choose a range of 90 days or fewer.' : 'Choose a start date on or before the end date.'}</p>}
    <State state={state} retry={reload} label="satellite analysis">{(data) => { const ndvi = data.ndvi_mean ?? data.ndvi?.mean ?? data.ndvi_summary?.mean ?? (isNum(data.ndvi) ? data.ndvi : null);
      if (!isNum(ndvi)) return <div className="satellite-empty"><span className="satellite-empty-art" aria-hidden="true"><i /><i /><i /><b /></span><div><strong>No usable observation returned</strong><p>{data.message ?? data.reason ?? `No suitable Sentinel-2 scene was found for ${request.location} between ${request.from} and ${request.to}.`}</p><span>Cloud cover or low valid-pixel coverage can prevent a result.</span></div></div>;
      const image = data.thumbnail_url ?? data.image_url ?? data.preview_url;
      return <div className="satellite-result">{image && <img src={image} alt={`Processed Sentinel-2 vegetation image for ${request.location}`} />}<div className="ndvi-result"><span>Mean NDVI</span><strong>{ndvi.toFixed(2)}</strong><small>{data.observation_date ?? data.date ?? 'Observation date unavailable'}</small></div><dl className="satellite-facts"><div><dt>Cloud / shadow</dt><dd>{readValue(data.cloud_cover ?? data.cloud_cover_percent, '%')}</dd></div><div><dt>Valid pixels</dt><dd>{readValue(data.valid_pixel_coverage ?? data.valid_pixel_percent, '%')}</dd></div><div><dt>Coverage</dt><dd>{readValue(data.spatial_coverage ?? data.coverage, '%')}</dd></div></dl></div>;
    }}</State>
    <p className="provenance">NDVI indicates vegetation greenness. It does not diagnose disease, crop type or yield.</p>
  </section>;
}

function AdvisoryPanel({ location, crop }) {
  const [question, setQuestion] = useState('What weather risks should I prepare for this week?'), [request, setRequest] = useState(null);
  const [state, reload] = useAsync(request ? () => api.getAdvisory(request.location, request.crop, request.question) : null, [request?.key]);
  useEffect(() => { setRequest(null); }, [location, crop]);
  return <section className="panel advisory-panel" id="advisory" aria-labelledby="advisory-title"><div className="panel-heading"><div><span className="eyebrow">Gemini · grounded in available data</span><h2 id="advisory-title">Field advisory</h2></div><span className="ai-badge">AI</span></div>
    {!location && <p className="note-block">Select a demo location to request an advisory.</p>}
    <form className="advisory-form" onSubmit={(event) => { event.preventDefault(); if (location && question.trim()) setRequest({ location, crop, question: question.trim(), key: `${location}-${crop}-${Date.now()}` }); }}><label htmlFor="field-question">Your question</label><textarea id="field-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={500} rows={3} /><div className="form-bottom"><span>{crop}{location ? ` · ${location}` : ''}<small>Do not include personal information.</small></span><button className="button button--primary" type="submit" disabled={!location || !question.trim() || state.status === 'loading'}>{state.status === 'loading' ? 'Writing advisory…' : 'Generate advisory'}</button></div></form>
    <State state={state} retry={reload} label="AI advisory">{(data) => <div className="advisory-result"><div className="advisory-result-head"><span className="ai-badge">AI-generated</span><span>{data.ai_model ?? 'Model not supplied'}</span></div><p className="advisory-copy">{data.advisory || 'The service returned no advisory text.'}</p><p className="provenance">For {data.crop ?? request.crop} at {data.location ?? request.location} · Weather source: {data.weather_source ?? 'Unavailable'}</p><p className="advisory-caution">Review consequential decisions with a local agricultural extension expert. AI text does not change the deterministic risk score.</p></div>}</State>
    {!request && <p className="advisory-caution">Advisory text appears after a request. The model should not supply missing measurements or alter the risk score.</p>}
  </section>;
}

function SourcePanel() {
  const sources = [
    ['01', 'Weather', 'Open-Meteo observations and forecasts. A forecast is a prediction. Soil moisture, when returned, is modelled.'],
    ['02', 'Vegetation', 'Sentinel-2 Level-2A through Copernicus. Cloud cover and valid pixels affect whether an observation is usable.'],
    ['03', 'Climate risk', 'Prototype weights: rainfall deficit 35%, heat 30%, excess rain 20%, and soil-moisture stress 15%. Crop thresholds need local review.'],
    ['04', 'Field advisory', 'Google Gemini may explain returned data. AI text can be incomplete or mistaken and never guarantees an outcome.'],
  ];
  return <section className="panel sources-panel" id="sources" aria-labelledby="sources-title"><div className="panel-heading"><div><span className="eyebrow">Provenance and limits</span><h2 id="sources-title">Data notes</h2></div></div>
    <div className="source-grid">{sources.map(([num, title, copy]) => <article key={num}><span className="source-index">{num}</span><div><h3>{title}</h3><p>{copy}</p></div></article>)}</div>
    <div className="decision-note"><span aria-hidden="true">i</span><p>TerraPulse AI is a decision-support prototype. It is not a validated yield forecast or a substitute for local agricultural advice.</p></div>
  </section>;
}

function CoordinatesForm({ onSubmit, onCancel }) {
  const [latitude, setLatitude] = useState(''), [longitude, setLongitude] = useState(''), [error, setError] = useState('');
  return <form className="coordinates-form" onSubmit={(event) => { event.preventDefault(); const lat = Number(latitude), lon = Number(longitude);
    if (!latitude.trim() || !longitude.trim() || !Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) { setError('Enter a latitude from −90 to 90 and longitude from −180 to 180.'); return; }
    setError(''); onSubmit(lat, lon);
  }}><div className="coordinate-inputs"><label>Latitude<input inputMode="decimal" value={latitude} onChange={(e) => setLatitude(e.target.value)} aria-describedby={error ? 'coordinate-error' : undefined} /></label><label>Longitude<input inputMode="decimal" value={longitude} onChange={(e) => setLongitude(e.target.value)} aria-describedby={error ? 'coordinate-error' : undefined} /></label></div>
    {error && <p className="field-error" id="coordinate-error" role="alert">{error}</p>}<div className="coordinate-actions"><button className="button button--primary" type="submit">Load coordinates</button><button className="button button--quiet" type="button" onClick={onCancel}>Use demo location</button></div></form>;
}

function Dashboard() {
  const [locationsState, retryLocations] = useAsync(() => api.getLocations(), []), [cropsState] = useAsync(() => api.getCrops(), []), [selectedName, setSelectedName] = useState(''), [crop, setCrop] = useState(CROPS[0]);
  const crops = cropsState.status === 'ready' && Array.isArray(cropsState.data?.crops) && cropsState.data.crops.length ? cropsState.data.crops : CROPS;
  const [customCoordinates, setCustomCoordinates] = useState(null), [coordinatesOpen, setCoordinatesOpen] = useState(false), [analysis, setAnalysis] = useState(null), [activeSection, setActiveSection] = useState('overview');
  const fromApi = locationsState.status === 'ready' ? normalizeLocations(locationsState.data) : [];
  const locations = fromApi.length ? fromApi : DEMO_LOCATIONS.map((name) => ({ name }));
  useEffect(() => { if (!selectedName && locations.length && !['loading', 'idle'].includes(locationsState.status)) setSelectedName(locations[0].name); }, [locations, selectedName, locationsState.status]);
  useEffect(() => {
    const nodes = ['overview', 'weather', 'history', 'risk', 'satellite', 'advisory', 'sources'].map((id) => document.getElementById(id)).filter(Boolean);
    if (!('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver((entries) => { const item = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]; if (item) setActiveSection(item.target.id); }, { rootMargin: '-18% 0px -65% 0px', threshold: [0, .25, .5] });
    nodes.forEach((node) => observer.observe(node)); return () => observer.disconnect();
  }, []);
  const selected = locations.find((loc) => loc.name === selectedName), namedLocation = customCoordinates ? '' : selectedName;
  const locationLabel = customCoordinates ? `${customCoordinates.latitude.toFixed(4)}, ${customCoordinates.longitude.toFixed(4)}` : selectedName;
  const query = customCoordinates ? { coordinates: true, latitude: customCoordinates.latitude, longitude: customCoordinates.longitude, key: `coords-${customCoordinates.latitude}-${customCoordinates.longitude}` }
    : selectedName ? { location: selectedName, key: `location-${selectedName}` } : null;
  const stale = analysis && (analysis.location !== namedLocation || analysis.crop !== crop);
  const coordinateLabel = selected && Number.isFinite(Number(selected.latitude)) && Number.isFinite(Number(selected.longitude))
    ? `${Number(selected.latitude).toFixed(4)}° N, ${Number(selected.longitude).toFixed(4)}° E`
    : customCoordinates ? `${customCoordinates.latitude.toFixed(4)}°, ${customCoordinates.longitude.toFixed(4)}°` : 'Karnataka demo location';

  return <div className="app-shell"><Sidebar active={activeSection} /><main className="main-area" id="overview">
    <header className="topbar"><a className="skip-link" href="#weather">Skip to weather data</a><div className="topbar-left"><span className="topbar-label">Agricultural climate intelligence</span><ServiceStatus /></div><div className="topbar-right"><span className="location-tag"><i className="status-dot status-dot--on" />{customCoordinates ? 'Custom coordinates' : 'Karnataka, India'}</span><span className="timezone-tag">IST · UTC+5:30</span></div></header>
    <div className="page-content"><section className="intro-row" aria-labelledby="page-title"><div><span className="eyebrow eyebrow--main">TerraPulse field dashboard</span><h1 id="page-title">Climate risk for Karnataka crops</h1><p>Review weather, crop risk and vegetation data for a selected field location.</p></div><div className="coverage-note"><strong>7</strong><span>demo locations<br />across Karnataka</span></div></section>
      <section className="selection-panel" aria-label="Field selection"><div className="selection-main">{!coordinatesOpen ? <><label>Location<select value={customCoordinates ? '__coordinates' : selectedName} onChange={(event) => { if (event.target.value === '__coordinates') { setCoordinatesOpen(true); return; } setCustomCoordinates(null); setSelectedName(event.target.value); setAnalysis(null); }}>{locations.map((loc) => <option value={loc.name} key={loc.name}>{loc.name}</option>)}{customCoordinates && <option value="__coordinates">Custom coordinates</option>}</select></label><button className="text-button location-switch" type="button" onClick={() => setCoordinatesOpen(true)}>Use coordinates</button></> : <CoordinatesForm onCancel={() => setCoordinatesOpen(false)} onSubmit={(latitude, longitude) => { setCustomCoordinates({ latitude, longitude }); setCoordinatesOpen(false); setAnalysis(null); }} />}
        {!coordinatesOpen && <label>Crop<select value={crop} onChange={(event) => setCrop(event.target.value)}>{crops.map((name) => <option key={name}>{name}</option>)}</select></label>}{!coordinatesOpen && <div className="selection-location"><span>Selected field</span><strong>{locationLabel || 'Choose a location'}</strong><small>{coordinateLabel}</small></div>}</div>
        {!coordinatesOpen && <div className="selection-action"><button className="button button--primary run-button" type="button" disabled={!namedLocation} onClick={() => setAnalysis({ location: namedLocation, crop, key: `${namedLocation}-${crop}-${Date.now()}` })}><span aria-hidden="true">↗</span> Run risk analysis</button>{!namedLocation && <small>Risk, imagery and advisory requests currently require a named demo location.</small>}</div>}</section>
      {locationsState.status === 'error' && <div className="locations-warning" role="status"><span>Location list unavailable. Showing the seven demo names from the specification.</span><button type="button" onClick={retryLocations}>Retry locations</button></div>}
      <WeatherPanel query={query} title={locationLabel} /><HistoricalPanel location={namedLocation} /><div className="analysis-grid"><RiskPanel request={namedLocation ? analysis : null} stale={stale} /><SatellitePanel location={namedLocation} /></div><AdvisoryPanel location={namedLocation} crop={crop} /><SourcePanel />
      <footer className="dashboard-footer"><Brand /><span>Weather by Open-Meteo · Satellite programme by Copernicus</span><span>Climate risk is decision support, not a yield prediction.</span></footer>
    </div>
  </main></div>;
}

function AppFrame({ children, page }) {
  return <div className="legal-shell"><header className="legal-header"><Brand /><a className="back-link" href="#/">Back to dashboard <span aria-hidden="true">↗</span></a></header>{children}<footer className="legal-footer"><span>TerraPulse AI · MVP 0.1</span><span>Weather by Open-Meteo · Satellite data from Copernicus</span><nav aria-label="Legal pages"><a href="#/privacy" aria-current={page === 'privacy' ? 'page' : undefined}>Privacy</a><a href="#/terms" aria-current={page === 'terms' ? 'page' : undefined}>Terms</a></nav></footer></div>;
}

export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => { const change = () => { const next = window.location.hash; if (next.startsWith('#/')) { setHash(next); window.scrollTo(0, 0); } else if (hash && hash !== '#/' && !hash.startsWith('#/')) setHash(''); }; window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change); }, [hash]);
  const page = hash.replace('#/', '').replace('#', '');
  if (page === 'privacy') return <AppFrame page={page}><Privacy /></AppFrame>;
  if (page === 'terms') return <AppFrame page={page}><Terms /></AppFrame>;
  return <Dashboard />;
}
