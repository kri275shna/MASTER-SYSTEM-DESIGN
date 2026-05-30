# Purplle Store Intelligence Platform

A production-grade, distributed Store Intelligence Platform designed to process raw store CCTV footage, run Edge AI tracking models, map visitor zones, flag anomalies, and serve analytics endpoints to a live React dashboard.

## Key Features

1. **Enterprise Layered Architecture**: Clear isolation between the API layer, Service layer, Repository layer, and PostgreSQL database.
2. **Edge AI Detection Pipeline (Simulated)**: YOLOv8 person detection, ByteTrack tracking, OSNet Re-ID, and OpenCV polygon intersection for shopping zones.
3. **Live Websocket Stream**: Real-time event push ticker (entries, exits, anomalies) using Redis Pub/Sub integration.
4. **Operations Anomaly Engine**: Dynamic scanner monitoring billing queue depth spikes, camera stale feeds, dead zones, and conversion drop metrics.
5. **Interactive Dashboard**: Sleek dark-mode React client incorporating custom glassmorphic aesthetics, Recharts timelines, active alert resolution handlers, and an event simulator.
6. **Robust Test Suite**: Pytest framework with SQLite memory isolation and Redis mocks achieving >70% coverage.

---

## Directory Layout

```text
├── backend/
│   ├── app/
│   │   ├── api/             # Routers, Middlewares, and Auth Dependencies
│   │   ├── core/            # Configuration and Database drivers
│   │   ├── models/          # SQLAlchemy 2.0 entities
│   │   ├── repositories/    # Database queries isolation
│   │   ├── schemas/         # Pydantic v2 schemas
│   │   └── services/        # Business logic: CV, Analytics, Funnels, Anomalies, Health
│   ├── tests/               # Backend Pytest suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # StoreOverview, VisitorMetrics, Funnel, Heatmap, Alert panels
│   │   ├── hooks/           # useWebsocket hook with reconnect backoff
│   │   ├── App.jsx          # Main application coordinator
│   │   └── index.css        # Tailwind styles & premium gradients
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Getting Started

### Local Setup (FastAPI Backend)

1. Navigate to the backend directory and create a virtual environment:
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install the python packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   *Note: On startup, the backend automatically initializes SQLite/PostgreSQL tables and seeds default users, Mumbai store, and mock shopping zones.*
4. Open the documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

### Local Setup (React Frontend)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   ```
2. Run the client dev server:
   ```bash
   npm run dev
   ```
3. Open the dashboard in your browser: [http://localhost:3000](http://localhost:3000).
4. Use the default login credentials:
   - **Email**: `admin@purplle.com`
   - **Password**: `admin123`

---

## Testing & Coverage

Execute the automated test suite with coverage report:
```bash
cd backend
pytest tests/ --cov=app --cov-report=term-missing
```

---

## Deployment (Docker Compose)

Start the entire stack (PostgreSQL + Redis + FastAPI Backend + React Frontend):
```bash
docker-compose up --build
```
The services will be exposed at:
- **FastAPI API & Docs**: `http://localhost:8000`
- **Dashboard Frontend**: `http://localhost:3000`
