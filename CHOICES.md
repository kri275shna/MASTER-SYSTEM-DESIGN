# Technology & Architectural Choices Rationale

This document contains justifications for selecting specific models, databases, and structural architectures in the Purplle Store Intelligence Platform.

---

## 1. Computer Vision Model Selection

| Phase | Selected Technology | Alternative Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **Person Detection** | **YOLOv8 Nano** | YOLOv5, YOLOv7 | YOLOv8 is anchor-free, has better accuracy-to-latency ratios, and integrates directly with ByteTrack. Nano version (3.2M params) runs comfortably at ~30 FPS on edge CPUs. |
| **Object Tracking** | **ByteTrack** | DeepSORT, SORT | DeepSORT extracts appearance features on every frame, which is highly GPU-intensive. ByteTrack performs association on almost all bounding boxes (including low-score occluded ones) using Kalman Filters and IoU matching, saving substantial computing overhead. |
| **Re-Identification** | **OSNet** | ResNet-50, MobileNet | Standard ResNets are designed for classification, not instance matching. OSNet is a lightweight network explicitly designed for Person Re-ID. It features omni-scale learning which captures both local details (shoes, bags) and global context (clothes colors). |

---

## 2. Infrastructure Choices

### Data Layer: PostgreSQL + Redis
- **PostgreSQL**: Serving as the source of truth. Structured relationships between Stores, Zones, Cameras, VisitorSessions, and Transactions require strong ACID guarantees and transaction mapping (funnel computation). JSONB support enables flexible event payloads without schema migrations.
- **Redis**: Used for high-frequency buffering and pub/sub:
  1. *Real-time Counter Increment*: Ingress agents update queue depth and active visitors inside Redis. Fetching dashboards runs in $\mathcal{O}(1)$ instead of executing heavy SQL `COUNT` operations.
  2. *Live Dashboard Stream*: Pushes real-time events to WebSockets.

### Web Server: FastAPI (Python 3.12+)
- High performance due to asynchronous event loop (`asyncio`) and compilation by `uvicorn` (based on `uvloop` and `httptools`).
- Automatic Pydantic v2 validation ensures payload types are validated at the router boundaries.
- Auto-generation of OpenAPI documentation.

---

## 3. Structural Code Architecture

### Layered Enterprise Architecture
To ensure scalability across 40+ stores, a modular design is used:
- **Routers**: Thin layers dealing only with HTTP parameters, status codes, and serialization.
- **Services**: Contain all domain business logic (funnels, tracking calculations, anomaly triggers). Routers cannot access database layers directly.
- **Repositories**: Encapsulate SQL queries. Prevents leaking database-specific implementation details (e.g. SQLAlchemy dependencies) into high-level business models.
- **Schemas**: Decoupled from SQL models. Prevents leaking database column internals to public JSON formats.
