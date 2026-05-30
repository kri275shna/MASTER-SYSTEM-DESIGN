import time
import uuid
import json
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("app.api.access")
# Configure json formatting for log aggregation
logging.basicConfig(level=logging.INFO)

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Start timer
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate latency
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        # Try to resolve store_id from query parameters or path
        store_id = request.query_params.get("store_id") or request.path_params.get("id") or "global"
        
        log_payload = {
            "trace_id": trace_id,
            "request_id": request_id,
            "store_id": store_id,
            "method": request.method,
            "endpoint": request.url.path,
            "latency_ms": latency_ms,
            "status_code": response.status_code
        }
        
        # Log in JSON format
        logger.info(json.dumps(log_payload))
        
        # Set trace headers in response
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Request-ID"] = request_id
        
        return response
