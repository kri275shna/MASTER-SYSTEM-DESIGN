# PROMPT: Implement Redis Streams Event Consumer Daemon
# CHANGES MADE: Created event_consumer.py with stream subscriber loop, validation, deduplication, and database write operations

import os
import sys
import time
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Ensure parent directory is in path for standalone execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.database import SessionLocal, redis_client
from app.schemas.event import EventSchema
from app.services.ingestion import ingestion_service
from app.services.anomalies import anomaly_engine

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.services.event_consumer")

STREAM_NAME = "store:events:stream"
GROUP_NAME = "store_intelligence_consumers"
CONSUMER_NAME = "consumer_worker_01"

def initialize_stream():
    """Initializes the Redis Stream and Consumer Group if they don't exist."""
    try:
        # Check if stream exists, if not xgroup_create will fail. We create it by adding dummy/checking
        redis_client.xgroup_create(STREAM_NAME, GROUP_NAME, mkstream=True, id="0")
        logger.info(f"Created Redis Consumer Group {GROUP_NAME} on stream {STREAM_NAME}.")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            logger.info(f"Redis Consumer Group {GROUP_NAME} already exists.")
        else:
            logger.warning(f"Could not initialize Redis Stream Consumer Group: {e}. Worker will use XREAD instead.")

def process_message(db: Session, message_id: str, event_json: str):
    """Processes a single event message from the Redis stream."""
    try:
        event_dict = json.loads(event_json)
        
        # 1. Validation using Pydantic v2 EventSchema
        event_schema = EventSchema(**event_dict)
        
        # 2. Deduplication / Idempotency check
        # Use Redis set with 24h expiration to cache processed event IDs
        redis_key = f"event:processed:{event_schema.event_id}"
        if redis_client.get(redis_key):
            logger.info(f"Duplicate event detected and discarded: {event_schema.event_id}")
            return True
            
        # 3. DB Ingestion
        # We call the ingestion service to write to PostgreSQL and run session updates
        ingestion_service.ingest_event_schema(db, event_schema)
        
        # Mark event as processed in Redis cache
        redis_client.setex(redis_key, 86400, "1")
        
        # 4. Trigger Anomaly engine check for this store
        anomaly_engine.run_all_checks(db, event_schema.store_id)
        
        return True
    except Exception as e:
        logger.error(f"Error processing stream message {message_id}: {e}")
        return False

def start_worker():
    logger.info("Starting Redis Stream Consumer Worker...")
    
    # Check if we are running in testing environment or Redis is mocked
    if hasattr(redis_client, "store") or not hasattr(redis_client, "xreadgroup"):
        logger.warning("Redis client is in-memory mock or does not support streams. Worker shutting down.")
        return

    initialize_stream()
    
    db = SessionLocal()
    
    try:
        while True:
            try:
                # Read new messages from group
                # block=2000 means wait up to 2 seconds if no messages
                streams = redis_client.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_NAME: ">"},
                    count=10,
                    block=2000
                )
                
                if not streams:
                    continue
                    
                for stream_name, messages in streams:
                    for msg_id, payload in messages:
                        event_json = payload.get("event")
                        if event_json:
                            success = process_message(db, msg_id, event_json)
                            if success:
                                # Acknowledge message processing completed
                                redis_client.xack(STREAM_NAME, GROUP_NAME, msg_id)
                                
            except Exception as loop_error:
                logger.error(f"Error in consumer worker loop: {loop_error}")
                time.sleep(2)
                
    except KeyboardInterrupt:
        logger.info("Consumer worker stopped by user keyboard interrupt.")
    finally:
        db.close()
        logger.info("Consumer worker database session closed.")

if __name__ == "__main__":
    start_worker()
