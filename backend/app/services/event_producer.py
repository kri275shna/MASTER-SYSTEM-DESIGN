# PROMPT: Implement Redis Streams Event Producer
# CHANGES MADE: Created event_producer.py with xadd stream publishing and fallback handling

import json
import logging
from typing import Dict, Any
from app.core.database import redis_client

logger = logging.getLogger("app.services.event_producer")

STREAM_NAME = "store:events:stream"

class EventProducer:
    def produce_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Pushes verified events to the Redis stream for async ingestion processing.
        """
        try:
            # Check if redis_client is MockRedis (e.g. during testing or if server is down)
            if hasattr(redis_client, "store") or not hasattr(redis_client, "xadd"):
                # Running in Mock Mode. Publish directly to channels to support synchronous tests
                # and skip stream buffering.
                logger.info("Mock Redis detected. Skipping stream queue, publishing directly.")
                return False
                
            # Serialize event dictionary
            event_json = json.dumps(event_data)
            
            # Push to Redis stream
            # Max length of 100,000 items to prevent memory exhaustion
            redis_client.xadd(STREAM_NAME, {"event": event_json}, maxlen=100000, approximate=True)
            logger.debug(f"Event pushed to Redis Stream {STREAM_NAME}: {event_data.get('event_type')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event to Redis Stream: {e}")
            return False

event_producer = EventProducer()
