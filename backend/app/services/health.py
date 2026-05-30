from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import redis_client
from app.models.models import Event

logger = logging.getLogger(__name__)

class HealthService:
    def get_system_health(self, db: Session, store_id: str = None) -> dict:
        """
        Runs comprehensive system checks on database, Redis, and event pipeline latency.
        """
        health_status = {
            "status": "HEALTHY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "postgres": {"status": "UP", "latency_ms": 0.0},
                "redis": {"status": "UP", "latency_ms": 0.0},
                "ingestion_pipeline": {"status": "UP", "last_event_age_seconds": 0.0}
            }
        }

        # 1. Test PostgreSQL connection and measure query speed
        try:
            start_time = datetime.now(timezone.utc)
            db.execute(text("SELECT 1"))
            end_time = datetime.now(timezone.utc)
            health_status["components"]["postgres"]["latency_ms"] = round((end_time - start_time).total_seconds() * 1000, 2)
        except Exception as e:
            logger.error(f"PostgreSQL Health Check Failed: {e}")
            health_status["components"]["postgres"]["status"] = "DOWN"
            health_status["status"] = "DEGRADED"

        # 2. Test Redis connection and measure ping speed
        try:
            start_time = datetime.now(timezone.utc)
            redis_client.ping()
            end_time = datetime.now(timezone.utc)
            health_status["components"]["redis"]["latency_ms"] = round((end_time - start_time).total_seconds() * 1000, 2)
        except Exception as e:
            logger.error(f"Redis Health Check Failed: {e}")
            health_status["components"]["redis"]["status"] = "DOWN"
            health_status["status"] = "DEGRADED"

        # 3. Test Ingestion Pipeline lag / age of last event
        try:
            query = db.query(Event)
            if store_id:
                query = query.filter(Event.store_id == store_id)
            
            last_event = query.order_by(Event.timestamp.desc()).first()
            
            if last_event:
                age_sec = (datetime.now(timezone.utc).replace(tzinfo=None) - last_event.timestamp.replace(tzinfo=None)).total_seconds()
                health_status["components"]["ingestion_pipeline"]["last_event_age_seconds"] = max(0.0, round(age_sec, 1))
                
                # If last event is older than 30 minutes in an active store, tag as warning
                if age_sec > 1800:
                    health_status["components"]["ingestion_pipeline"]["status"] = "WARNING (Feed Idle)"
            else:
                health_status["components"]["ingestion_pipeline"]["status"] = "WARNING (No events recorded)"
        except Exception as e:
            logger.error(f"Pipeline Age Check Failed: {e}")
            health_status["components"]["ingestion_pipeline"]["status"] = "ERROR"
            health_status["status"] = "DEGRADED"

        # If any core component is down, mark system status as unhealthy
        if (health_status["components"]["postgres"]["status"] == "DOWN" or 
            health_status["components"]["redis"]["status"] == "DOWN"):
            health_status["status"] = "UNHEALTHY"

        return health_status

health_service = HealthService()
