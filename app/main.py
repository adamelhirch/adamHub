from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.calendar_feeds import public_router as public_calendar_feeds_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.scheduler import setup_scheduler, shutdown_scheduler
from app.mcp.server import build_mcp_app, mcp_server

settings = get_settings()

WEB_DIST_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
WEB_ASSETS_DIR = WEB_DIST_DIR / "assets"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    setup_scheduler()
    # The streamable-HTTP session manager needs an active task group for the
    # whole process lifetime (mcp_server.session_manager is only populated
    # once build_mcp_app() -> streamable_http_app() has run, which app.mount
    # below does at import time, before this lifespan ever executes).
    async with mcp_server.session_manager.run():
        yield
    shutdown_scheduler()


app = FastAPI(
    title="AdamHUB Life API",
    version="0.1.0",
    description="Unified API for life ops: tasks, finances, meals, pantry, groceries, Linear projects, and AI skill execution",
    lifespan=lifespan,
)

if WEB_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_ASSETS_DIR), name="assets")

allow_origins = ["*"] if settings.allow_origins == "*" else [origin.strip() for origin in settings.allow_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    # Accept localhost dev URLs AND any AdamHUB Connect Chrome extension origin.
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|chrome-extension://[a-z]+)$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "adamhub-life-api"}


app.include_router(api_router)
app.include_router(public_calendar_feeds_router)
# Mounted (not include_router-ed): the MCP SDK owns this sub-app's routing —
# tool listing/execution is auth-scoped per caller inside app/mcp/server.py,
# not per-route like the rest of the API. Must be registered before the SPA
# catch-all below so /mcp isn't swallowed by it.
app.mount("/mcp", build_mcp_app())


def _frontend_available() -> bool:
    return (WEB_DIST_DIR / "index.html").exists()


def _frontend_hint() -> HTMLResponse:
    return HTMLResponse(
        """
        <html><body style="font-family: sans-serif; padding: 24px;">
          <h2>AdamHUB frontend build not found</h2>
          <p>Use one of these options:</p>
          <ol>
            <li>Dev mode: <code>cd web && npm install && npm run dev</code> then open <a href="http://localhost:5173">http://localhost:5173</a></li>
            <li>Build mode: <code>cd web && npm run build</code> then refresh this page</li>
          </ol>
        </body></html>
        """.strip()
    )


@app.get("/", include_in_schema=False)
def frontend_root():
    if not _frontend_available():
        return _frontend_hint()
    return FileResponse(WEB_DIST_DIR / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    if full_path in {"openapi.json", "docs", "redoc", "health"}:
        raise HTTPException(status_code=404, detail="Not found")

    if full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Not found")

    if not _frontend_available():
        return _frontend_hint()

    return FileResponse(WEB_DIST_DIR / "index.html")
