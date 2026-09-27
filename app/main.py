from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.scheduler import setup_scheduler, shutdown_scheduler
from app.mcp.server import build_mcp_app, mcp_server
from app.services.meal_planning import CalendarConflictError

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    setup_scheduler()
    async with mcp_server.session_manager.run():
        yield
    shutdown_scheduler()


app = FastAPI(
    title="AdamHUB API",
    version="2.0.0",
    description="API mobile-first pour courses, recettes, garde-manger et synchronisation supermarchés Drive",
    lifespan=lifespan,
)

allow_origins = ["*"] if settings.allow_origins == "*" else [origin.strip() for origin in settings.allow_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|exp://[a-zA-Z0-9\.\:\-]+)$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CalendarConflictError)
def calendar_conflict_error_handler(request: Request, exc: CalendarConflictError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": str(exc),
            "conflict": True,
            "colliding_items": getattr(exc, "colliding_items", []),
            "suggested_slots": getattr(exc, "suggested_slots", []),
        },
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "adamhub-api", "version": "2.0.0"}


app.include_router(api_router)
app.mount("/mcp", build_mcp_app())


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "AdamHUB API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "description": "Backend mobile-first pour gestion de courses, recettes et drives",
    }
