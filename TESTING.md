# Quality Assurance & Testing Plan

This document explains the testing strategy, mock configurations, and execution commands.

---

## 1. Test Suite Architecture

We isolate test execution environment to prevent dirtying production resources:
- **Database Isolation**: In `tests/conftest.py`, we override the FastAPI `get_db` dependency to use an in-memory SQLite engine (`sqlite:///./test.db`). Each test function executes within a transactional block that is rolled back on completion, ensuring database state reset.
- **Cache Isolation**: The production Redis client is replaced with a custom in-memory `MockRedis` helper that simulates hash tables, standard gets/sets, atomic increments/decrements, and Pub/Sub channel subscriptions.

---

## 2. Test Cases Covered

### Authentication & Authorization (`tests/test_auth.py`)
- Successful registration of new dashboard users.
- Validation that duplicate registrations fail with 400 Bad Request.
- Successful login using form data and JSON payloads (issuing Bearer tokens).
- Authentication failures on invalid password check.
- Verification of RBAC protections (Viewer, Analyst, Admin roles).

### Event Ingestion Pipeline (`tests/test_events.py`)
- Ingesting a standard `ENTRY` event creates a database `VisitorSession`.
- Ingesting an `EXIT` event sets the appropriate end timestamp and measures total duration.
- Re-entry checks: Entry of a visitor within 30 minutes of exit reactivates their session and logs a `REENTRY` trace.
- Staff filtering: Visitors with `is_staff: true` are correctly flagged in the session.

### Analytics & Funnel Calculations (`tests/test_metrics.py`)
- Correct calculation of offline store metrics:
  - Total Unique Visitors (ensuring staff sessions are excluded).
  - Conversion rates (measuring sessions marked as converted against the unique visitor count).
- Store Funnel progression counts:
  - Step drop-offs (from Entry -> Zone Visit -> Queue -> Purchase).
  - Average transition speeds.

---

## 3. Running Tests & Generating Reports

### Run All Tests
Execute tests with pytest command:
```bash
cd backend
venv\Scripts\pytest tests/ -v
```

### Check Coverage Report
Measure test coverage using the `pytest-cov` plugin:
```bash
venv\Scripts\pytest tests/ --cov=app --cov-report=term-missing
```

The terminal will output the code statement coverage report.
Ensure total package coverage exceeds the **70%** threshold.
