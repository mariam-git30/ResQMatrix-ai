# ResQMatrix AI

ResQMatrix AI is an emergency decision-support dashboard foundation for operators coordinating multiple emergencies and limited response resources.

## Step 3 scope

The current foundation includes:

- A modular Flask application
- Responsive landing page and operator dashboard
- Bootstrap 5 for base UI utilities
- Reusable layout, navigation, panel, metric, and empty-state patterns
- `GET /api/health` readiness endpoint
- Development configuration that works with Replit's `PORT` environment variable
- SQLite3 database initialization at `database/resqmatrix.db`
- Fictional demo emergencies and field resources seeded on a fresh database
- Emergency and resource CRUD REST APIs with input validation
- Prepared allocations table for a future optimization engine
- Response history records for operator-created and updated records
- Dashboard statistics sourced from SQLite
- Emergency intake and resource registry management forms
- Local AI Emergency Priority Engine for active and in-progress emergencies
- Explainable 0–100 priority scores with configurable weighted factors
- Priority ranking and operator-facing factor analysis

Step 3 is intentionally limited to transparent priority decision support. Resource optimization, resource allocation, dispatch, maps, simulation, analytics, and what-if analysis are not included.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` or visit `/dashboard`.

The database is created and seeded automatically when the Flask application starts.

## API

`GET /api/health`

```json
{
  "status": "success",
  "message": "ResQMatrix AI API is running"
}
```

Additional endpoints:

- `GET /api/dashboard/stats`
- `GET/POST /api/emergencies`
- `GET/PUT/PATCH/DELETE /api/emergencies/<id>`
- `GET/POST /api/resources`
- `GET/PUT/PATCH/DELETE /api/resources/<id>`
- `GET /api/allocations`
- `GET /api/history`
- `POST /api/priority/calculate`
- `GET /api/priority/emergencies`

## AI Emergency Priority Engine

The priority engine is a local Python rule-based weighted calculation. It does not call an external AI service, modify emergency severity, change resource quantities, create allocations, dispatch resources, or contact emergency services.

### Factors and weights

| Factor | Weight |
| --- | ---: |
| Severity | 25% |
| Critical injuries | 25% |
| People affected | 15% |
| Urgency | 15% |
| Injured | 10% |
| Time elapsed | 5% |
| Resource scarcity | 5% |

Severity and urgency use their stored 0–100 values. People affected and injured are normalized against the maximum value in the current emergency dataset. Critical injuries are normalized against the current dataset's maximum critical-injury count. Time elapsed is bounded to a configurable 24-hour window, so it cannot dominate the result; missing or invalid reported times contribute zero. Resource scarcity inspects compatible SQLite resource types and compares available quantities with total quantities. Missing compatible resources produce a high scarcity signal, while unknown emergency types use zero scarcity.

### Thresholds and explanation

Scores are clamped to 0–100 and rounded to two decimals:

- `0–24.99`: LOW
- `25–49.99`: MEDIUM
- `50–74.99`: HIGH
- `75–100`: CRITICAL

The API returns every factor score, its configured weight, the top three weighted contributors, and an explanation generated from the current emergency data. The ranking endpoint sorts active and in-progress emergencies by this prototype score only.

The priority score is a prototype decision-support calculation using configurable weighted factors. It is not a substitute for trained emergency professionals or official emergency protocols.

Human operators remain responsible for all operational decisions.

## Project layout

```text
resqmatrix-ai/
├── app.py
├── config.py
├── requirements.txt
├── routes/
├── services/
├── ai/
├── database/
├── templates/
└── static/
```