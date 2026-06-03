# Gap Analysis - Purplle Store Intelligence Platform

This document presents a structured review of the existing repository against the requirements of the **Purplle Tech Challenge**.

---

## 1. Existing Features

The current repository contains a basic skeleton of the Store Intelligence Platform:
- **Backend Core**: FastAPI with Uvicorn server, SQLAlchemy ORM mappings, and SQLite/PostgreSQL configuration.
- **REST Endpoints**: Simple single-event ingestion, metadata configuration (Stores, Cameras, Zones), basic store metrics, funnel stages, and anomaly listings.
- **Role-Based Access Control**: Standard JWT user registration and login with roles (`Admin`, `Analyst`, `Viewer`).
- **Basic Analytics Services**: Rough calculations for visitor sessions, funnel stages, and heatmap coordinates.
- **Basic Dashboard**: A React frontend bundled with Vite, demonstrating standard Recharts visual components and basic WebSocket stream listeners.

---

## 2. Missing Features & Repository Gaps

| Challenge Requirement | Current State in Repository | Implementation Gap |
| :--- | :--- | :--- |
| **Production-Ready CV Detection Pipeline** | Simulative wrapper in `cv_pipeline.py`. No actual runner scripts or modular modules. | Missing real YOLOv8 inference, ByteTrack association, Re-ID OSNet features, point-polygon zone matching, queue occupancy tracking, and event emission scripts under `pipeline/`. |
| **Pydantic v2 Event Schema** | Standard models in `schemas.py`. | Missing dedicated, strict Pydantic v2 `app/schemas/event.py` with validation and challenge-exact field names (including confidence, dwell_ms, metadata, is_staff, etc.). |
| **Database Design** | Relational models in SQLAlchemy. | PostgreSQL migrations are incomplete, and tables need indexing for performance. |
| **Redis Streams Ingestion Layer** | Direct synchronous database insert on ingest. | Missing queue-based async pipeline (`event_producer.py` and `event_consumer.py` worker process) which decouples HTTP ingest from database write operations. |
| **Ingestion API Robustness** | Single event ingestion with no idempotency, validation schemas, or bulk capabilities. | Missing batch ingestion (`POST /events/ingest` accepting list of events), idempotency tracking, deduplication, and partial success response formats. |
| **Advanced Analytics Engine** | Simplistic metric queries. | Missing proper handling of edge conditions: empty store (division by zero), zero purchases, staff filtering, and re-entry visitor deduplication. |
| **Comprehensive Anomaly Detection** | Basic rule queries (hardcoded thresholds). | Missing dynamic calculations (Queue Spike using `Current Queue > Historical Avg * Threshold`, Conversion Drop using `7-day rolling average`, Dead Zone triggered at 30 minutes of no traffic). |
| **Next.js Live Dashboard** | Simple React/Vite development server. | Needs to be upgraded to a Next.js framework (re-implemented with tailwind and Recharts), with robust WebSocket streaming for live counters, metrics, charts, and active anomalies. |
| **Structured Logging** | Basic python-logging writing manual JSON dump. | Missing clean `structlog` setup logging trace_id, store_id, endpoint, latency, event count, and status code. |
| **Test Coverage (>80%)** | Basic coverage on auth and analytics (~65%). | Missing testing for duplicate events, re-entry session activation, staff exclusion, empty stores, queue spikes, dead zones, and funnel drop-offs. |

---

## 3. Assignment Compliance Score

* **Current Score:** **45 / 100**
* **Target Score:** **100 / 100**

---

## 4. Improvement Roadmap

1. **Phase 1: Schemas and Database**: Create Pydantic v2 schemas and execute database migrations.
2. **Phase 2: Detection Pipeline**: Create production-ready `pipeline/` scripts implementing YOLOv8, ByteTrack, Re-ID matching, and Event emission.
3. **Phase 3: Redis Streams Queue**: Write event producer and background event consumer worker daemon.
4. **Phase 4: API & Analytics Refactoring**: Complete all backend route logic (batch ingest, analytics, funnel, heatmap, health, stale feeds, structlog logging).
5. **Phase 5: Next.js Dashboard Upgrade**: Migrate the frontend to Next.js + Recharts + Tailwind + WebSockets.
6. **Phase 6: Testing & Quality Assurance**: Write tests covering all edge cases to exceed 80% coverage.
7. **Phase 7: Setup & Deploy**: Optimize Docker Compose configuration and rewrite documentation.
