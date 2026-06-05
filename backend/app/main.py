"""FastAPI entrypoint — Phase 1 scaffold."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.vectorstore.client import health as os_health

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("Starting backend (env=%s)", settings.app_env)
    yield
    log.info("Shutting down backend")


settings = get_settings()
app = FastAPI(title="AI Agent Chatbot", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"name": "AI Agent Chatbot", "version": app.version, "phase": 4}


@app.get("/health")
async def health():
    cluster = os_health()
    return {
        "status": "ok",
        "opensearch": cluster.get("status") if cluster else "unreachable",
    }

