# PROMPT: Implement structlog structured logging middleware
# CHANGES MADE: Overwrote logging.py middleware using structlog, tracing latencies, status codes, and request event counts

import time
import uuid
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger("app.api.access")

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Bind context variables for log nesting
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            request_id=request_id
        )

        start_time = time.time()
        
        # Initialize default request state parameters
        request.state.event_count = 0
        
        # Process request
        response = await call_next(request)
        
        # Calculate latency metrics
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        # Attempt to capture store id context
        store_id = request.query_params.get("store_id") or request.path_params.get("id") or "global"
        
        # Log using structlog
        logger.info(
            "http_request",
            trace_id=trace_id,
            store_id=store_id,
            endpoint=request.url.path,
            latency_ms=latency_ms,
            event_count=getattr(request.state, "event_count", 0),
            status_code=response.status_code,
            method=request.method
        )
        
        # Append identifiers to client headers
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Request-ID"] = request_id
        
        return response
