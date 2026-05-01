"""FastAPI application entry point."""
import sys
import time
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ── Ensure project scripts are importable ──
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "utils"))

from utils.db import init_db, close_db
from api.logging_config import setup_logging, api_logger

# ── Initialize logging ──
setup_logging()

# ── Request log middleware ──


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with full detail."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        # ── Read request body ──
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""

        # ── Log incoming request ──
        api_logger.info(
            ">>> REQUEST | %s %s | client=%s | query=%s",
            request.method,
            request.url.path + ("?" + str(request.query_params) if request.query_params else ""),
            client_ip,
            dict(request.query_params) if request.query_params else "-",
        )

        # Log headers (redact sensitive ones)
        headers = dict(request.headers)
        if "authorization" in headers:
            headers["authorization"] = "***REDACTED***"
        if "cookie" in headers:
            headers["cookie"] = "***REDACTED***"
        api_logger.debug("  Headers: %s", headers)

        # Log body for POST/PUT/PATCH
        if request.method in ("POST", "PUT", "PATCH") and body_str:
            # Truncate very long bodies
            display = body_str if len(body_str) <= 8000 else body_str[:8000] + f"...[truncated, total {len(body_str)} chars]"
            api_logger.info("  Body: %s", display)

        # Reconstruct request body for downstream consumption
        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive

        # ── Execute request ──
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            api_logger.error(
                "<<< ERROR %s %s | %s | %.0fms",
                request.method, request.url.path, repr(exc), elapsed,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000

        # ── Log response ──
        # Read response body for logging (only for JSON responses)
        resp_body = ""
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            try:
                # Collect body from StreamingResponse or plain Response
                if hasattr(response, "body"):
                    resp_body = response.body.decode("utf-8", errors="replace") if isinstance(response.body, bytes) else str(response.body)
            except Exception:
                resp_body = "[unable to read response body]"

        if resp_body:
            display_body = resp_body if len(resp_body) <= 4000 else resp_body[:4000] + f"...[truncated, total {len(resp_body)} chars]"
            api_logger.info(
                "<<< RESPONSE | %s %s | status=%d | %.0fms | body=%s",
                request.method, request.url.path,
                response.status_code, elapsed,
                display_body,
            )
        else:
            api_logger.info(
                "<<< RESPONSE | %s %s | status=%d | %.0fms",
                request.method, request.url.path,
                response.status_code, elapsed,
            )

        return response


# ── Lifespan ──

async def _midnight_scheduler():
    """Background task: run sync every day at 00:00."""
    while True:
        now = datetime.now()
        # Calculate seconds until next midnight
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (midnight - now).total_seconds()
        api_logger.info("Next auto-sync scheduled at %s (in %.0f minutes)", midnight.isoformat(), wait_seconds / 60)
        await asyncio.sleep(wait_seconds)

        # Run sync
        try:
            api_logger.info("=== Auto midnight sync triggered ===")
            from api.services.sync_service import run_sync
            # Run in thread to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_sync)
            api_logger.info("Auto-sync result: %s", result.get("message", result.get("status")))
        except Exception as e:
            api_logger.exception("Auto-sync failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB; Shutdown: close DB connections."""
    api_logger.info("=== Urban Signal Miner API starting ===")
    init_db()
    api_logger.info("Database initialized")

    # Start midnight sync scheduler
    scheduler_task = asyncio.create_task(_midnight_scheduler())

    yield

    # Cleanup
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    close_db()
    api_logger.info("=== Urban Signal Miner API shutting down ===")


# ── App ──

app = FastAPI(
    title="Urban Signal Miner API",
    description="Enterprise-grade news intelligence pipeline API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware (order matters: last added = outermost) ──

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging (innermost, so it captures actual processing time)
app.add_middleware(RequestLogMiddleware)


# ── Global error handler ──

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    api_logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "error": str(exc)},
    )


# ── Routers ──

from api.routers.dashboard import router as dashboard_router
from api.routers.news import router as news_router
from api.routers.reports import router as reports_router
from api.routers.meta import router as meta_router
from api.routers.sync import router as sync_router
from api.routers.pipeline import router as pipeline_router

app.include_router(dashboard_router)
app.include_router(news_router)
app.include_router(reports_router)
app.include_router(meta_router)
app.include_router(sync_router)
app.include_router(pipeline_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Urban Signal Miner API"}
