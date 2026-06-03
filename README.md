# Store Intelligence & Real-Time Analytics Platform

A complete Store Intelligence and Operational Analytics Platform that processes raw CCTV feeds, tracks visitors across camera fields of view using YOLOv8 + ByteTrack, unifies customer session profiles, and streams real-time retail performance indicators to an interactive live dashboard.

---

## 1. System Architecture

The platform consists of a distributed architecture designed for scalability and high-availability operations:

```
  +------------------+     +--------------------+     +---------------------+
  | CCTV Video Feed  | --> | Detection Pipeline | --> | Ingestion API Gate  |
  | (RTSP/Webcam)    |     | (YOLOv8/ByteTrack) |     | (FastAPI / Pydantic)|
  +------------------+     +--------------------+     +---------------------+
                                                                 |
                                                                 v
  +------------------+     +--------------------+     +---------------------+
  | Live Dashboard   | <-- | Redis PubSub WS    | <-- | Redis Stream Queue  |
  | (Next.js/Charts) |     | (WebSocket events) |     | (Async Buffering)   |
  +------------------+     +--------------------+     +---------------------+
            |                                                    |
            v                                                    v
  +------------------+                                +---------------------+
  | REST Metrics API | -----------------------------> | Postgres DB / Worker|
  | (Aggregations)   |                                | (Source of Truth)   |
  +------------------+                                +---------------------+
```

- **Computer Vision Pipeline**: Executes real-time YOLOv8 person detection, ByteTrack tracking, Re-ID embedding matching, OpenCV polygon zone tests, and billing queue occupancy mapping.
- **Asynchronous Ingestion**: Ingested events are validated and written to a Redis Stream (`store:events:stream`), decoupling client response time from database writes.
- **Background Worker**: Pulls events from the stream, deduplicates payloads, updates real-time counters, resolves visitor sessions, runs anomaly check rules, and writes to PostgreSQL.
- **Live Stream Broadcasting**: Emits updates to connected Next.js dashboard clients via WebSockets.

---

## 2. Project Directory Structure

```
MASTER SYSTEM DESIGN/
├── docs/
│   ├── GAP_ANALYSIS.md     # Architectural review and Roadmap gaps
│   ├── DESIGN.md           # Deep dive technical system mechanics
│   └── CHOICES.md          # Technology selection rationales & trade-offs
├── pipeline/
│   ├── detect.py           # YOLOv8 Person detector wrapper
│   ├── tracker.py          # IoU-based multi-object tracker
│   ├── reid.py             # Cosine similarity Re-ID & Staff filtering
│   ├── zones.py            # Point polygon mapping for store sections
│   ├── queue_detector.py   # Queue dwell and join detector
│   ├── emit.py             # Event sender client (HTTP/Redis stream)
│   └── run_pipeline.py     # Main Computer Vision pipeline orchestrator
├── backend/
│   ├── app/
│   │   ├── api/            # Route endpoints and request middlewares
│   │   ├── core/           # Config settings and databases connections
│   │   ├── models/         # SQLAlchemy PostgreSQL DB models
│   │   ├── schemas/        # Pydantic v2 event and response validation schemas
│   │   └── services/       # Ingestion services and Analytics metrics services
│   ├── alembic/            # Alembic schema migrations revisions
│   └── tests/              # Backend pytest test files
├── frontend/
│   ├── src/
│   │   ├── pages/          # Next.js Page Router entrypoints (index, _app)
│   │   ├── components/     # Recharts and tailwind dashboard panels
│   │   └── hooks/          # useWebsocket stream consumer hooks
│   └── Dockerfile          # Next.js multi-stage compiler Dockerfile
├── docker-compose.yml      # Orchestrations for DB, Redis, API, Worker, and Client
└── README.md               # Main project guide
```

---

## 3. Fast Setup & Launch (Using Docker Compose)

The entire environment is configured to run out-of-the-box using Docker Compose.

### Prerequisites:
- Docker and Docker Compose installed on your system.

### Build and Run:
Run the following command in the root folder of the project:
```bash
docker compose up --build
```

This starts:
1. **PostgreSQL** (`purplle-db`) on port `5432` - Stores relational data.
2. **Redis** (`purplle-redis`) on port `6379` - Buffers stream queue and caches metrics.
3. **FastAPI API** (`purplle-backend`) on port `8000` - Handles REST requests.
4. **Worker Daemon** (`purplle-worker`) - Asynchronously processes Redis stream events.
5. **Next.js Dashboard** (`purplle-frontend`) on port `3000` - Interactive charts.

---

## 4. API Documentation

### Event Ingestion Endpoint
- **URL**: `POST /api/v1/events/ingest`
- **Payload**: Accepts a single event object or a list of event objects.
- **Fields**:
  - `event_id`: string (UUID)
  - `store_id`: string
  - `camera_id`: string (optional)
  - `visitor_id`: string (resolved ReID)
  - `event_type`: string (`ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`, `QUEUE_JOIN`, `QUEUE_ABANDON`, `REENTRY`)
  - `timestamp`: string (ISO 8601)
  - `zone_id`: string (optional)
  - `dwell_ms`: integer (optional)
  - `is_staff`: boolean (optional)
  - `confidence`: float (optional)
  - `metadata`: object (optional)

- **Example Response (Batch Ingestion)**:
  ```json
  {
    "summary": {
      "total": 2,
      "accepted": 2,
      "success": 0,
      "duplicate": 0,
      "failed": 0
    },
    "results": [
      {
        "event_id": "evt-001",
        "status": "accepted",
        "detail": "Event accepted and buffered in Redis stream queue."
      },
      {
        "event_id": "evt-002",
        "status": "accepted",
        "detail": "Event accepted and buffered in Redis stream queue."
      }
    ]
  }
  ```

### Analytics Endpoints
- **GET** `/api/v1/stores/{id}/metrics`: Aggregates customer count, conversion rate, queue depth, repeat visitors, and abandonment rate.
- **GET** `/api/v1/stores/{id}/funnel`: Displays visitor transition statistics (`ENTRY -> ZONE -> BILLING -> PURCHASE`).
- **GET** `/api/v1/stores/{id}/heatmap`: Returns zone visit densities and normalized hotspot scores.
- **GET** `/api/v1/stores/{id}/anomalies`: Lists active store anomalies (`QUEUE_SPIKE`, `CONVERSION_DROP`, `DEAD_ZONE`).
- **GET** `/api/v1/health`: Diagnostic check for Postgres, Redis, and event stream latency.

---

## 5. Running the Computer Vision Pipeline

To stream events into the platform, run the pipeline orchestrator:

### Initialize Virtual Environment:
```bash
cd pipeline
# Install dependencies
pip install opencv-python numpy requests ultralytics
```

### Run Pipeline (In Simulation Mode):
If no video file is provided, the orchestrator generates synthetic frames representing visitors walking through different store zones.
```bash
python run_pipeline.py --source mock --gui
```
*Note: Include `--gui` to launch an OpenCV rendering window showing bounding boxes, tracked visitor paths, and configured zone boundary lines.*

---

## 6. Running Unit Tests

To run the unit test suite and check code statement coverage, execute:

```bash
cd backend
# Run all tests
venv\Scripts\pytest tests/ -v

# Run with coverage report
venv\Scripts\pytest tests/ --cov=app --cov-report=term-missing
```

The test coverage exceeds the **80%** challenge requirement.
