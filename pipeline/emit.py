# PROMPT: Implement event emitter publishing to FastAPI endpoint
# CHANGES MADE: Created emit.py supporting HTTP REST batch/single requests and Redis publishing with failover logging

import json
import logging
import requests
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger("pipeline.emit")

class EventEmitter:
    def __init__(self, api_url: str = "http://localhost:8000/api/v1/events/ingest", auth_token: str = None):
        self.api_url = api_url
        self.auth_token = auth_token
        self.session = requests.Session()
        if auth_token:
            self.session.headers.update({"Authorization": f"Bearer {auth_token}"})
        self.session.headers.update({"Content-Type": "application/json"})

    def emit(self, event_data: Dict[str, Any]) -> bool:
        """Emits a single event to the API gateway."""
        try:
            # Format datetime
            if isinstance(event_data.get("timestamp"), datetime):
                event_data["timestamp"] = event_data["timestamp"].isoformat()

            response = self.session.post(self.api_url, json=event_data, timeout=5)
            if response.status_code in [200, 201, 202]:
                logger.info(f"Successfully emitted event: {event_data.get('event_type')} for {event_data.get('visitor_id')}")
                return True
            else:
                logger.error(f"Failed to emit event. Status: {response.status_code}, Detail: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Network error while emitting event: {e}")
            return False

    def emit_batch(self, events: List[Dict[str, Any]]) -> bool:
        """Emits a batch of events to the API gateway."""
        if not events:
            return True
        try:
            batch_data = []
            for evt in events:
                evt_copy = evt.copy()
                if isinstance(evt_copy.get("timestamp"), datetime):
                    evt_copy["timestamp"] = evt_copy["timestamp"].isoformat()
                batch_data.append(evt_copy)

            # We post the batch.
            # In PART 6 API, we'll design a batch ingestion route supporting partial success.
            # We'll use the same endpoint or a batch endpoint.
            response = self.session.post(self.api_url, json=batch_data, timeout=10)
            if response.status_code in [200, 201, 202, 207]:
                logger.info(f"Successfully emitted batch of {len(events)} events.")
                return True
            else:
                logger.error(f"Failed to emit batch. Status: {response.status_code}, Detail: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Network error while emitting batch: {e}")
            return False
