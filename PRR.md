# Production Readiness Review (PRR)

This document evaluates the platform's reliability, scalability, security, and operation readiness under heavy workloads (40+ stores, millions of daily events).

---

## 1. High Load & Scaling Strategies

### Database Optimization
- **Table Partitioning**: The `events` table will grow by millions of records weekly. We must partition `events` by **Range/List partitioning** on `store_id` or `timestamp` (e.g. monthly partitions). This ensures query executions for a specific store scan only the relevant partition instead of the entire database.
- **Indexes**:
  - `idx_events_store_timestamp` on `events(store_id, timestamp desc)` (speeds up metrics fetching).
  - `idx_session_visitor` on `visitor_sessions(unique_visitor_id)` (fast lookup for re-entry validation).
  - `idx_transactions_session` on `transactions(session_id)` (fast POS matching).

### Event Ingestion Throttling (Celery & RabbitMQ/Redis Queue)
- Processing frame crops, running Re-ID similarity matching, and writing transactions can cause bottleneck spikes.
- **Production Update**: Introduce an asynchronous task queue (e.g., Celery). Edge agents write to a lightweight broker (e.g., RabbitMQ or Redis List), and FastAPI returns a fast `202 Accepted`. Background celery workers consume messages and execute database matching asynchronously.

---

## 2. Fault Tolerance & Fallback Modes

### Redis Availability Failure
- *Risk*: If Redis drops, realtime queue depths and WebSocket broadcasts will fail.
- *Mitigation*: Fallback to direct database counting. Modify health handlers to bypass caching and run direct PostgreSQL count scans (`SELECT count(*) FROM visitor_sessions WHERE end_time IS NULL`) when Redis connection checks fail.

### Video Stream Network Disruption
- *Risk*: CCTV feeds dropped due to bandwidth loss or camera hardware failure.
- *Mitigation*: The Anomaly Engine monitors feed freshness. If `stale_feeds` flags a camera has not sent frame data for 15 minutes, it creates an active alert, which triggers immediate notifications to store managers.

---

## 3. Production Security Checklist

1. **Secure JWT Secrets**: Ensure `SECRET_KEY` is injected as a high-strength environment variable rather than using code defaults.
2. **CORS Restrictions**: Replace `allow_origins=["*"]` in `main.py` with the exact URLs of production dashboard servers (e.g., Vercel host address).
3. **Role-Based Access Control**: Enforce `RoleChecker(["Admin"])` on configuration routes (adding cameras, changing zones) and `RoleChecker(["Admin", "Analyst"])` on metric queries. Dashboard viewers are restricted from modifying metadata.
4. **HTTPS/WSS Enforcement**: Ensure all traffic is encrypted via TLS. Production clients must connect using HTTPS and secure WebSockets (`wss://`).

---

## 4. Observability & Monitoring Metrics

We define core Service Level Indicators (SLIs) for pipeline reliability:

| SLI Metric | Source | Target SLOT | Action if breached |
| :--- | :--- | :--- | :--- |
| **Ingestion Latency** | Access Log `latency_ms` | < 150ms (p95) | Spin up additional FastAPI app pods. |
| **Edge Stream Health** | Health API `last_event_age_seconds` | < 10 seconds | Alert network technicians (stale feed). |
| **Error Rate** | Access Log `status_code` | < 0.1% 5xx errors | Audit DB pool size and connection availability. |
| **Re-ID Query Speed** | OpenCV vector search | < 50ms | Scale vector index search engines. |
