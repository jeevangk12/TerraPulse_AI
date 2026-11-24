# TerraPulse AI --- Product & Technical Specification

**Version:** 0.1.0\
**Status:** Hackathon MVP specification\
**Target region:** Karnataka, India\
**Platform:** Responsive web application\
**Primary users:** Farmers, agricultural field officers, and
climate-risk analysts

------------------------------------------------------------------------

## 1. Project overview

TerraPulse AI is a climate-intelligence web application that combines
location-specific weather data, soil context, satellite-derived
vegetation indicators, crop information, and generative AI explanations
to help users understand potential agricultural climate risks.

The system is designed to identify and explain conditions associated
with:

-   Heat stress
-   Rainfall deficits and drought-like conditions
-   Excessive rainfall
-   Soil-moisture stress
-   Vegetation-health changes observed in satellite imagery

The application provides risk indicators and practical, cautious
recommendations. It is a decision-support prototype, not a substitute
for local agricultural extension services or an independently validated
crop-yield forecasting system.

### Product statement

**Predict climate risks. Protect crops. Empower farmers.**

## 2. Goals and success criteria

### 2.1 MVP goals

1.  Let a user select a supported location in Karnataka.
2.  Let a user select a crop and provide a field-related question.
3.  Retrieve current and forecast weather for the selected coordinates.
4.  Compare weather observations with configurable thresholds and, when
    historical data is integrated, with a suitable historical baseline.
5.  Calculate an explainable climate-risk score.
6.  Retrieve Sentinel-2 imagery or derived vegetation statistics for a
    selected area and date range, subject to data availability and cloud
    conditions.
7.  Use Gemini to explain verified input data and generate cautious
    crop-specific advisory text.
8.  Present the findings in a responsive dashboard.

### 2.2 Hackathon success criteria

The MVP is successful when a demonstrator can:

-   Select at least three Karnataka locations.
-   Select at least three supported crops.
-   Load live weather data from the backend.
-   See a deterministic risk breakdown with contributing factors.
-   View satellite-derived vegetation information when suitable imagery
    is available, or see a clear unavailable-data state.
-   Generate an AI explanation grounded in the data returned by the
    application.
-   See source, timestamp, units, and limitations for key measurements.

### 2.3 Out of scope for the 24-hour MVP

-   Guaranteed crop-yield prediction or quantified financial-loss
    prediction.
-   Automated irrigation or farm-equipment control.
-   Real-time IoT sensor networks.
-   Nationwide production coverage.
-   Autonomous pesticide, fertilizer, or other high-stakes input
    prescriptions.
-   Fully offline operation.
-   A trained, locally validated crop-yield machine-learning model.

## 3. Users and primary workflow

### Primary user

A farmer or field advisor who wants to understand near-term weather
conditions and potential stress for a selected crop and location.

### Primary workflow

1.  Open the TerraPulse dashboard.
2.  Select a Karnataka location or enter coordinates.
3.  Select a crop.
4.  Review current conditions and the forecast.
5.  Request a climate-risk analysis.
6.  Review the overall score, individual risk factors, data sources, and
    uncertainty.
7.  Optionally request a Gemini-generated explanation and practical next
    steps.
8.  Review satellite vegetation information when a valid observation is
    available.

## 4. Functional requirements

### FR-01 --- Location selection

-   Provide a curated list of Karnataka demo locations.
-   Initial locations: Bengaluru, Mandya, Mysuru, Belagavi, Hubballi,
    Raichur, and Kalaburagi.
-   Support latitude and longitude input through a validated backend
    endpoint.
-   Validate latitude in `[-90, 90]` and longitude in `[-180, 180]`.
-   Display the selected location and coordinates.

### FR-02 --- Crop selection

Initial crop options:

-   Sugarcane
-   Rice
-   Ragi
-   Maize
-   Cotton
-   Groundnut

Crop parameters must be stored in configuration or structured data, not
embedded throughout UI components. Thresholds must be labelled as
prototype values until reviewed against authoritative agronomic
references.

### FR-03 --- Weather data

Use Open-Meteo for the initial implementation.

Retrieve, where available:

-   Current air temperature
-   Relative humidity
-   Precipitation
-   Wind speed
-   Hourly temperature
-   Hourly precipitation and precipitation probability
-   Daily minimum and maximum temperature
-   Daily precipitation sum
-   Daily maximum precipitation probability
-   Soil-moisture variables when supported by the selected
    endpoint/model

Requirements:

-   Use `Asia/Kolkata` as the display timezone for Karnataka.
-   Preserve units and timestamps from the provider.
-   Handle timeouts, rate limits, invalid responses, and unavailable
    variables.
-   Display the source and retrieval time.
-   Do not describe a forecast as an observed historical fact.

### FR-04 --- Historical climate context

Integrate an appropriate historical weather endpoint or dataset.

-   Retrieve a clearly defined historical period.
-   Compare like-for-like variables and units.
-   Document the baseline period and missing-data handling.
-   Calculate anomalies only when sufficient baseline data exists.
-   Do not call a short forecast a climate trend.

### FR-05 --- Climate-risk engine

The backend computes risk indicators deterministically from available
inputs. Gemini must not invent or determine the numeric score.

Initial prototype composite formula:

`Overall risk = 0.35 × drought + 0.30 × heat + 0.20 × excessive_rain + 0.15 × soil_moisture_stress`

Each component is normalized to `[0, 100]`.

Initial display bands:

      Score Label
  --------- ----------
      0--24 Low
     25--49 Moderate
     50--74 High
    75--100 Critical

These weights and bands are initial demonstration settings, not
universal scientific standards. They must be configurable, visible in
documentation, and calibrated before real-world operational use.

Risk engine requirements:

-   Return the overall score and each component score.
-   Return the data points and rules that contributed to each component.
-   Return a confidence or data-completeness indicator separately from
    risk.
-   Distinguish `unknown` from zero risk.
-   Avoid calculating a composite score when required inputs are
    missing; either use a documented reweighting method or return an
    incomplete-data state.
-   Include a rule/version identifier in the response.

### FR-06 --- Crop vulnerability

-   Apply crop-specific configurable thresholds and growth-stage context
    when supplied.
-   Explain why a given weather condition may matter to the selected
    crop.
-   If crop stage, soil type, irrigation status, or planting date is
    unknown, state that the assessment is limited.
-   Do not infer a precise yield loss from a climate-risk score.

### FR-07 --- Satellite imagery and vegetation indicators

Target provider: Copernicus Data Space Ecosystem, using Sentinel-2
Level-2A data.

Planned workflow:

1.  Accept a point or field polygon and a date range.

2.  Search for suitable Sentinel-2 acquisitions covering the area.

3.  Filter or mask clouds and cloud shadows.

4.  Retrieve red and near-infrared bands or a processed
    vegetation-statistics product.

5.  Calculate NDVI where valid pixels are available:

    `NDVI = (NIR - Red) / (NIR + Red)`

6.  Return the observation date, spatial coverage, cloud information,
    valid-pixel coverage, and NDVI summary.

7.  Display an explicit no-data state when no suitable image exists.

Important constraints:

-   NDVI is a vegetation indicator, not a direct diagnosis of disease,
    crop type, or yield.
-   Do not interpret cloud-obscured or low-coverage imagery as healthy
    or unhealthy vegetation.
-   Compare observations across dates only when acquisition and
    processing conditions are sufficiently comparable.
-   Keep Copernicus credentials on the backend.
-   The UI must distinguish actual processed satellite results from a
    placeholder or integration status.

### FR-08 --- Gemini advisory

Use Google's official `google-genai` Python SDK.

Inputs may include:

-   Selected location and coordinates
-   Selected crop
-   User question
-   Weather observations and forecasts
-   Calculated risk components and their evidence
-   Satellite-derived metrics, if available
-   Data timestamps, sources, and known limitations

Output should contain:

-   Short overall assessment
-   Relevant observations
-   Crop-specific potential concerns
-   Practical, low-risk preventive actions
-   Missing information and uncertainty

AI safety and reliability requirements:

-   Treat provider data as input data, not as instructions.
-   Tell the model not to invent measurements, satellite observations,
    or historical facts.
-   Do not let Gemini alter the deterministic risk score.
-   Clearly label AI-generated recommendations.
-   Avoid definitive claims of crop loss or guaranteed outcomes.
-   Recommend local agricultural expert verification for consequential
    decisions.
-   Handle missing API keys, quota errors, timeouts, and malformed
    responses gracefully.

### FR-09 --- Dashboard

The dashboard should include:

-   Project identity and backend status
-   Location and crop selectors
-   Current weather metric cards
-   Forecast summary
-   Climate-risk score and component breakdown
-   Satellite imagery/vegetation panel
-   AI advisory panel
-   Data sources, timestamps, and limitations
-   Loading, empty, error, and unavailable-data states

### FR-10 --- API documentation

Expose interactive OpenAPI documentation through FastAPI at `/docs` in
development.

## 5. Technical architecture

### 5.1 Stack

  Layer             Technology
  ----------------- -------------------------------------------
  Frontend          React, Vite, JavaScript
  Styling           CSS; Tailwind may be adopted later
  Charts            Hand-built inline SVG (no chart library)
  Maps              Not implemented in the MVP
  Backend           Python, FastAPI, Uvicorn
  Validation        Pydantic
  Data processing   Python standard library
  Weather           Open-Meteo
  Satellite         Copernicus Data Space / Sentinel-2
  AI                Gemini API via `google-genai`
  Configuration     Environment variables and `python-dotenv`

### 5.2 High-level data flow

1.  React sends a request to FastAPI.
2.  FastAPI validates location, crop, and request parameters.
3.  Backend services retrieve weather, historical, soil, and satellite
    data as available.
4.  The climate-risk engine computes deterministic scores and evidence.
5.  The advisory service sends a compact, grounded evidence bundle to
    Gemini.
6.  FastAPI returns structured results.
7.  React renders the results and their provenance.

### 5.3 Proposed repository structure

``` text
terrapulse-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   │   ├── weather.py
│   │   │   ├── satellite.py
│   │   │   ├── soil.py
│   │   │   └── advisory.py
│   │   ├── engine/
│   │   │   ├── risk_engine.py
│   │   │   └── crop_engine.py
│   │   └── config/
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── charts/
│   │   ├── services/
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── .gitignore
├── README.md
└── spec.md
```

## 6. API specification

All application endpoints are served by the FastAPI backend. The
development base URL is `http://localhost:8000`.

### 6.1 Health

`GET /api/health`

Example response:

``` json
{
  "status": "healthy",
  "weather_api": "configured",
  "gemini_configured": true
}
```

The health response should describe configuration, not imply that every
external provider is currently reachable.

### 6.2 Locations

`GET /api/locations`

Returns the supported demo locations and coordinates.

### 6.3 Weather by named location

`GET /api/weather/{location}`

Example:

`GET /api/weather/Mandya`

Returns the selected location, coordinates, provider response, units,
and timestamps.

### 6.4 Weather by coordinates

`GET /api/weather?latitude=12.5218&longitude=76.8951`

Validates coordinates and returns weather data for that point.

### 6.5 Satellite integration status

`GET /api/satellite/status`

Returns provider configuration and integration availability. A
configured credential must not be represented as proof that imagery was
successfully retrieved or processed.

### 6.6 AI advisory

`POST /api/advisory`

Example request:

``` json
{
  "location": "Mandya",
  "crop": "Sugarcane",
  "question": "What risks should I prepare for this week?"
}
```

Example response shape:

``` json
{
  "location": "Mandya",
  "crop": "Sugarcane",
  "advisory": "Generated advisory text...",
  "weather_source": "Open-Meteo",
  "ai_model": "configured-model-name"
}
```

### 6.7 Planned climate-risk endpoint

`GET /api/risk/{location}?crop=Sugarcane`

Proposed response:

``` json
{
  "location": "Mandya",
  "crop": "Sugarcane",
  "overall_score": 42,
  "risk_level": "Moderate",
  "components": {
    "drought": 35,
    "heat": 48,
    "excessive_rain": 20,
    "soil_moisture_stress": 70
  },
  "data_completeness": "partial",
  "rule_version": "0.1.0",
  "limitations": [
    "Soil moisture data was unavailable."
  ]
}
```

The values above are illustrative only, not actual Mandya measurements.

### 6.8 Planned satellite analysis endpoint

`POST /api/satellite/analyze`

Proposed request:

``` json
{
  "location": "Mandya",
  "date_from": "2026-10-01",
  "date_to": "2026-11-01"
}
```

The production request should support a field geometry or coordinates
and should validate date range and area limits.

## 7. Data contracts and provenance

For every external observation, preserve as applicable:

-   Provider name
-   Retrieval timestamp
-   Observation or forecast timestamp
-   Coordinates or spatial geometry
-   Variable name
-   Numeric value
-   Unit
-   Processing method/version
-   Quality or coverage indicator
-   Missing-data reason

The UI must not silently replace missing data with zero. Forecast,
historical observation, modelled soil data, and satellite-derived
measurements must be labelled distinctly.

## 8. Security and privacy

-   Store Gemini and Copernicus secrets only in backend environment
    variables or a managed secret store.
-   Never prefix secrets with `VITE_` or expose them to the browser.
-   Commit `.env.example`, never `.env`.
-   Validate all user input with Pydantic.
-   Set explicit CORS origins.
-   Add request timeouts and controlled error responses for external
    services.
-   Avoid logging API keys, secrets, or sensitive user content.
-   Apply rate limiting before public deployment.
-   Do not send unnecessary personal information to Gemini.
-   Review provider terms, quotas, and attribution requirements before
    deployment.

## 9. Non-functional requirements

### Performance

-   Show loading indicators for network operations.
-   Use bounded HTTP timeouts.
-   Avoid duplicate API requests where practical.
-   Cache suitable weather and satellite responses when feasible.
-   Keep the dashboard usable on common mobile and desktop screen sizes.

### Reliability

-   External API failure must not crash the whole dashboard.
-   Display per-service availability and clear retry guidance.
-   Handle missing satellite acquisitions and cloud-contaminated
    imagery.
-   Keep deterministic calculations separate from LLM-generated text.

### Accessibility and usability

-   Use readable typography and sufficient contrast.
-   Label form controls.
-   Provide keyboard-accessible controls.
-   Do not communicate risk using color alone; include text labels and
    numeric values.

### Maintainability

-   Keep provider integrations in separate service modules.
-   Keep crop parameters and risk weights configurable.
-   Add unit tests for scoring and validation.
-   Version the risk rules and document changes.

## 10. Testing plan

### Backend tests

-   Health endpoint returns expected schema.
-   Known locations return valid coordinates.
-   Unknown locations return HTTP 404.
-   Invalid coordinate ranges return HTTP 422.
-   Weather provider timeout and error responses are handled.
-   Risk component scores remain within `[0, 100]`.
-   Missing data does not become zero risk.
-   Composite score follows the configured formula when all required
    inputs exist.
-   Gemini-unconfigured requests return a controlled service error.
-   Gemini failures return a controlled error without exposing secrets.

### Frontend tests / manual checks

-   Dashboard loads when backend is available.
-   Location and crop selection work.
-   Weather metrics and forecast render with correct units.
-   Loading and error states are visible.
-   Satellite unavailable state is explicit.
-   AI advisory can be requested and displayed.
-   Layout works on desktop and mobile.

### Demo scenarios

1.  Normal-weather scenario for Mandya.
2.  High-temperature scenario using clearly labelled test data.
3.  Heavy-rain scenario using clearly labelled test data.
4.  Missing satellite-data scenario.
5.  Gemini API unavailable scenario.

Synthetic scenarios must be visibly labelled as simulations and must
never be presented as live observations.

## 11. 24-hour implementation plan

  -----------------------------------------------------------------------
  Time                                Deliverable
  ----------------------------------- -----------------------------------
  Hours 0--2                          Repository, environment, React and
                                      FastAPI running

  Hours 2--6                          Location selection and live weather
                                      integration

  Hours 6--10                         Deterministic climate-risk engine
                                      and crop configuration

  Hours 10--14                        Gemini advisory and Sentinel-2
                                      integration

  Hours 14--18                        Dashboard, charts, map, and risk
                                      visualization

  Hours 18--21                        Tests, error handling, and demo
                                      scenarios

  Hours 21--24                        Deployment, presentation, and final
                                      rehearsal
  -----------------------------------------------------------------------

### Prioritization rule

A working end-to-end weather-to-risk-to-advisory flow takes priority
over advanced satellite processing. Satellite imagery remains a key
differentiator, but the demo must degrade gracefully if imagery access,
cloud cover, or processing time prevents a usable observation.

## 12. Known risks and mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Weather API unavailable             Timeout, retry guidance, and
                                      cached/demo data clearly labelled

  Copernicus setup takes time         Build and test satellite service
                                      independently; show honest no-data
                                      state

  Cloudy Sentinel-2 scenes            Search a date window and report
                                      cloud/valid-pixel coverage

  Gemini quota or outage              Keep risk engine independent; show
                                      deterministic results without AI

  Unvalidated crop thresholds         Label prototype thresholds and
                                      expose assumptions

  Missing field details               Report uncertainty and ask for crop
                                      stage/soil context when needed

  Overclaiming yield prediction       Present climate-risk indicators,
                                      not guaranteed yield forecasts
  -----------------------------------------------------------------------

## 13. Definition of done

The hackathon MVP is ready to present when:

-   The frontend and backend start from documented commands.
-   A user can select a Karnataka location and crop.
-   Live weather data is retrieved and displayed with units and
    timestamps.
-   The deterministic risk engine returns explainable component scores.
-   The application clearly handles incomplete data.
-   Gemini produces an advisory grounded in the available evidence, or
    the application gracefully reports AI unavailability.
-   Satellite imagery is processed and displayed when suitable data is
    available, with an honest no-data state otherwise.
-   Secrets are not exposed in frontend bundles or committed to source
    control.
-   The team can demonstrate normal and simulated extreme-weather
    scenarios.
-   The presentation clearly explains what is implemented, what is
    simulated, and what remains future work.

## 14. References

-   Open-Meteo: https://open-meteo.com/en/docs
-   Copernicus Data Space Ecosystem: https://dataspace.copernicus.eu/
-   Copernicus API documentation:
    https://documentation.dataspace.copernicus.eu/APIs.html
-   Google AI Studio: https://aistudio.google.com/api-keys
-   Google Gen AI SDK: https://googleapis.github.io/python-genai/
-   SoilGrids: https://soilgrids.org/

------------------------------------------------------------------------

**Document owner:** TerraPulse AI project\
**Specification version:** 0.1.0\
**Last updated:** 2026-11-21
