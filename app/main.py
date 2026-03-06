from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AdamHUB Life API",
    version="0.1.0",
    description="Unified API for life ops: tasks, finances, meals, pantry, groceries, Linear projects, and AI skill execution",
    lifespan=lifespan,
)

web_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=web_dir), name="static")

allow_origins = ["*"] if settings.allow_origins == "*" else [origin.strip() for origin in settings.allow_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "adamhub-life-api"}


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(web_dir / "index.html")


app.include_router(api_router)
