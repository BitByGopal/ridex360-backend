# RideX360 Backend

Django + Django REST Framework backend implementing RideX360's **core transportation loop**:

```
Passenger scheduled → Trip created → Driver starts trip → GPS starts →
Parent sees vehicle → ETA calculated → Absence marked → Stop updated →
Route recalculated → Driver updated → Passenger boards → Trip completed
```

This is the V1 backend scoped for the **Meridian Schools pilot** (private day school, own bus fleet, Hyderabad) — but the data model is organization-type-agnostic by design, so the same engine can serve colleges, companies, hospitals, factories, hotels and industrial campuses later without a schema rewrite.

## What's implemented

- **Custom User model** with role-based access (`parent`, `driver`, `org_admin`)
- **Multi-tenant org structure**: `Organization → Branch → Route → Stop`, so one organization (e.g. Meridian) can have multiple branches, each running its own routes independently
- **Full trip lifecycle**: `Trip → TripStop → TripPassenger`, tracking per-day status separately from the reusable route/stop templates
- **The absence → recalculation workflow**: marking a passenger absent updates their `TripPassenger` status, then checks whether their pickup stop has any other active passenger left that day — if not, the `TripStop` is automatically marked `skipped`. This is verified working end-to-end (see Testing below), not simulated.
- **JWT authentication** (`djangorestframework-simplejwt`)
- **GPS ping ingestion** with a denormalized "last known position" cache on `Trip` for fast reads, plus a full `GPSPing` history table
- **Haversine-based ETA estimate** (`transport/eta.py`) — a placeholder for a real routing/traffic API, clearly isolated so it's a one-file swap later
- **Django Admin as the V1 organization dashboard** — full CRUD on organizations, branches, passengers, vehicles, routes, stops, trips, with inline stop/passenger editing on trips
- **Demo data seed command** modeled on the actual Meridian scenario (one branch, one route, 4 stops, 5 students/parents, 1 driver, today's trip)

## What's intentionally deferred

Per the roadmap, this is a 3-month solo-founder MVP scope, not the full production brief:

- **No WebSockets/Django Channels/Redis yet** — the mobile app will poll for GPS/status updates on an interval instead. Simpler to build and deploy solo; upgradeable to real-time push later without changing the data model.
- **No real routing/traffic API** — ETA is haversine-distance-based. Swap `transport/eta.py` for Google Routes (or similar) once there's budget and usage data to justify it.
- **No separate Organization web dashboard app yet** — Django Admin covers CRUD needs for the pilot. A dedicated React dashboard is a Phase 2/3 build once the mobile core loop is proven.
- **No push notifications yet** — Firebase Cloud Messaging integration is a later addition once the core loop is validated with a real pilot.

## Tech stack

- Django 6.1 + Django REST Framework
- SQLite for local development (zero setup) — switches to PostgreSQL via a `DATABASE_URL` env var for staging/production
- `djangorestframework-simplejwt` for auth
- `django-cors-headers` for the Expo/React Native app to call the API during development

## Project structure

```
ridex360-backend/
├── ridex360/            # Project settings, root URLs
├── accounts/            # Custom User model (role-based), admin
├── transport/           # Core domain: Organization, Branch, Passenger,
│                         Vehicle, Route, Stop, Trip, TripStop,
│                         TripPassenger, GPSPing, views, serializers,
│                         permissions, eta.py, admin, seed_demo command
├── requirements.txt
├── .env.example
├── .gitignore
└── manage.py
```

## Getting started

```bash
python3 -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env      # defaults work as-is for local dev (SQLite)

python manage.py migrate
python manage.py seed_demo        # loads the Meridian demo scenario
python manage.py createsuperuser  # for Django Admin access

python manage.py runserver
```

API is now live at `http://localhost:8000/api/`. Admin dashboard at `http://localhost:8000/admin/`.

**Demo login credentials** (created by `seed_demo`, password `ridex360demo` for all):
- Driver: `driver1`
- Parents: `parent1` through `parent5`

## API reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login/` | Obtain JWT access + refresh tokens |
| POST | `/api/auth/refresh/` | Refresh an access token |
| GET | `/api/me/` | Current user's role + profile (mobile app uses this to decide which screens to show) |

### Parent
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/parent/children/` | List passengers this parent is guardian of |
| GET | `/api/parent/children/<id>/today/` | Today's trip status for that passenger |
| POST | `/api/parent/children/<id>/mark-absent/` | Mark absent — triggers stop recalculation |

### Driver
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/driver/trips/today/` | Driver's trip(s) for today |
| POST | `/api/driver/trips/<id>/start/` | Start a trip |
| POST | `/api/driver/trips/<id>/complete/` | Complete a trip |
| POST | `/api/driver/trips/<id>/gps/` | Submit a GPS ping `{latitude, longitude}` |
| POST | `/api/driver/trips/<id>/stops/<stop_id>/arrived/` | Mark a stop arrived |
| POST | `/api/driver/trips/<id>/passengers/<id>/boarded/` | Mark passenger boarded |
| POST | `/api/driver/trips/<id>/passengers/<id>/dropped-off/` | Mark passenger dropped off |
| POST | `/api/driver/trips/<id>/passengers/<id>/no-show/` | Mark passenger no-show |

## Testing the core loop manually

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"parent1","password":"ridex360demo"}'

# Use the returned "access" token as a Bearer token for subsequent calls
curl http://localhost:8000/api/parent/children/ \
  -H "Authorization: Bearer <token>"
```

This full loop (login → view children → view today's trip → mark absent → confirm stop recalculation → driver view → start trip → GPS ping → ETA) has been verified working end-to-end against the seeded Meridian demo data.

## Deployment

Designed for Railway (or any host supporting a `DATABASE_URL` env var):

1. Provision a PostgreSQL instance, set `DATABASE_URL`.
2. Set `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS` to your real domain.
3. Run `python manage.py migrate` and `python manage.py createsuperuser` on first deploy.
4. Tighten `CORS_ALLOW_ALL_ORIGINS` to the actual Expo/web app origin before handling real passenger data.

## Next steps (per the roadmap)

This completes Weeks 1–4 of the 12-week solo roadmap (backend foundation + core APIs). Next: the Expo mobile app (Parent + Driver views) consuming this API with real data from day one — no mock data — so nothing built here gets thrown away.
