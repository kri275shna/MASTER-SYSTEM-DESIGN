# Technical Decisions & Architectural Choices Rationale

This document outlines the rationale behind selecting the key technologies for the Store Intelligence Platform, detailing the options considered, trade-offs, and final decisions.

---

## 1. Computer Vision: Object Detection Model

### Options Considered:
- **YOLOv5 / YOLOv7**: Previous generations of the YOLO family.
- **SSD (Single Shot MultiBox Detector) / Faster R-CNN**: Standard detection models.
- **YOLOv8 Nano (Selected)**: The latest generation lightweight object detector.

### Technical Comparison & AI Recommendations:
Standard architectures like Faster R-CNN provide high localization accuracy but are computationally expensive, running at $< 10\text{ FPS}$ on standard CPU hardware. SSDs offer better speeds but struggle with small objects in wide-angle CCTV views.

AI recommendations suggested YOLOv8 Nano (`yolov8n.pt`) due to its anchor-free design, which improves the detection of overlapping objects (common in crowded retail lines). At 3.2 million parameters, it runs at $> 30\text{ FPS}$ on edge CPUs and $> 150\text{ FPS}$ on consumer GPUs.

### Final Decision & Trade-offs:
We selected **YOLOv8 Nano** for the person detection class (ID 0). 
- *Trade-off:* While larger models like YOLOv8 Medium or Large offer slightly better accuracy, they cannot run in real-time on edge devices without dedicated GPUs. YOLOv8 Nano provides the best balance of accuracy and processing speed for real-time tracking.

---

## 2. Multi-Object Tracking

### Options Considered:
- **SORT (Simple Online and Realtime Tracking)**: A baseline IoU and Kalman Filter tracker.
- **DeepSORT**: Integrates deep learning appearance descriptors into SORT.
- **ByteTrack (Selected)**: Associates almost every bounding box (including low-confidence ones) to maintain track continuity.

### Technical Comparison & AI Recommendations:
DeepSORT extracts feature embeddings for every bounding box on every frame. While accurate, this is computationally expensive and requires significant GPU resources at scale. SORT is fast but struggles with occlusions, leading to frequent ID switches when customers pass behind displays.

AI analysis recommended ByteTrack. Instead of discarding low-confidence detections (e.g. conf $< 0.45$), ByteTrack uses Kalman filters to project active tracks and matches them against low-confidence boxes. This maintains tracking continuity during temporary occlusions without the overhead of deep feature extraction on every frame.

### Final Decision & Trade-offs:
We selected **ByteTrack** for real-time person tracking.
- *Trade-off:* ByteTrack is dependent on the motion model. If a person stops moving and is occluded for an extended period, the track may still be lost. However, for retail environments with continuous foot traffic, it provides stable tracking at a fraction of the computational cost of DeepSORT.

---

## 3. Web Framework

### Options Considered:
- **Django**: A full-featured web framework.
- **Flask**: A lightweight WSGI web framework.
- **FastAPI (Selected)**: A high-performance ASGI framework built on Pydantic and Starlette.

### Technical Comparison & AI Recommendations:
Django is robust but is designed for synchronous, monolithic applications. Flask is flexible but lacks native support for asynchronous programming, which is critical for handling high-frequency event streams and persistent WebSocket connections.

AI analysis recommended FastAPI due to its native asynchronous event loop (`asyncio`) and compilation by `uvicorn` (using `uvloop` and `httptools`). Its integration with Pydantic v2 ensures strict schema validation at the API boundary.

### Final Decision & Trade-offs:
We selected **FastAPI** for the backend API.
- *Trade-off:* FastAPI has a smaller ecosystem of built-in plugins compared to Django (e.g., no built-in admin panel or ORM configuration). However, its performance gains and native asynchronous support make it the superior choice for high-throughput IoT and event-driven architectures.

---

## 4. Primary Relational Storage

### Options Considered:
- **MySQL / MariaDB**: Standard open-source relational databases.
- **MongoDB**: A document-based NoSQL database.
- **PostgreSQL (Selected)**: An advanced object-relational database.

### Technical Comparison & AI Recommendations:
MongoDB is highly scalable for unstructured JSON payloads but lacks support for complex relational queries, such as the multi-stage joins required for funnel analysis. MySQL supports these joins but has limited support for unstructured data types.

AI recommendations pointed to PostgreSQL. Its native `JSONB` support allows storing raw event payloads without schema migrations, while its relational engine provides strict ACID guarantees for transaction processing and funnel calculations.

### Final Decision & Trade-offs:
We selected **PostgreSQL** as the primary datastore.
- *Trade-off:* PostgreSQL requires more active configuration and database tuning (e.g., connection pooling, index optimization) at scale compared to NoSQL alternatives. We address this by using Redis as a caching layer to offload repetitive read queries.

---

## 5. Caching & Message Queue Broker

### Options Considered:
- **Apache Kafka**: A distributed streaming platform.
- **RabbitMQ**: A traditional message broker.
- **Redis (Selected)**: An in-memory data structure store supporting Pub/Sub and Streams.

### Technical Comparison & AI Recommendations:
Apache Kafka is highly scalable but introduces significant operational complexity and resource overhead. RabbitMQ is reliable for message routing but lacks support for in-memory caching and real-time counter increments.

AI recommendations suggested Redis. Redis Streams provide a lightweight, high-throughput message queue, while its core key-value engine serves as a fast caching layer and real-time counter (using `incr` and `decr` for queue depths and active visitor counts).

### Final Decision & Trade-offs:
We selected **Redis** to handle message queuing, caching, and pub/sub.
- *Trade-off:* Redis is an in-memory database, meaning data persistence is limited compared to Kafka. However, for transient event buffering and real-time state tracking where low latency is critical, Redis is the optimal choice.

---

## 6. Real-Time Ingestion Communication

### Options Considered:
- **HTTP Long Polling**: The client periodically requests updates.
- **Server-Sent Events (SSE)**: Unidirectional real-time updates from server to client.
- **WebSockets (Selected)**: Full-duplex communication over a single TCP connection.

### Technical Comparison & AI Recommendations:
HTTP Long Polling introduces significant network overhead from repeated header handshakes. SSE is efficient for server-to-client updates but does not support client-to-server messages over the same connection.

AI recommendations suggested WebSockets. WebSockets establish a single, persistent TCP connection, allowing full-duplex communication with minimal overhead, which is ideal for streaming high-frequency event tickers and anomaly alerts.

### Final Decision & Trade-offs:
We selected **WebSockets** for real-time dashboard updates.
- *Trade-off:* WebSockets require persistent connection state management on the server, which can exhaust port limits if not properly configured. We mitigate this by using Redis Pub/Sub to decouple connection state from the API workers.
