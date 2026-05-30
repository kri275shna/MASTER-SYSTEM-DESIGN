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

You can run the application in two modes depending on your local environment:

### Option A: Zero-Install Local Demo (No Node.js, Redis, or Docker required)
Best for quick verification on machines without Node.js or Docker. The backend automatically falls back to an SQLite database (`store.db`) and an in-memory Redis mock.

1. **Activate Backend & Run FastAPI**:
   ```bash
   cd backend
   .\venv\Scripts\activate
   uvicorn app.main:app --port 8000
   ```
   *The database (`store.db`) is auto-initialized and seeded with default stores, cameras, and zones on startup.*
   *API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).*

2. **Serve or Open the Demo Frontend**:
   * **Via Local HTTP Server**: Run `python -m http.server 3000` in the workspace root and open [http://localhost:3000/localhost_demo.html](http://localhost:3000/localhost_demo.html).
   * **Direct File Load**: Simply double-click the `localhost_demo.html` file at the root to open it in your browser.

3. **Default Login Credentials**:
   * **Email**: `admin@purplle.com`
   * **Password**: `admin123`

---

### Option B: Full Stack Setup (Vite React + Redis + PostgreSQL)
Best for production deployment and component-based active development.

1. **Start API Backend**:
   ```bash
   cd backend
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
   *(Ensure local PostgreSQL and Redis services are running, or update configuration via `.env` file.)*

2. **Start React Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   *The Vite dashboard runs at [http://localhost:3000](http://localhost:3000).*

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
