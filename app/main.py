import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import flights, health

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("hp-backend")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(
        "Starting 'A Una Milla de Tu Destino' backend | Environment: %s | Allowed origins: %s",
        settings.ENVIRONMENT,
        settings.cors_origins
    )
    yield
    logger.info("Shutting down backend service.")


app = FastAPI(
    title="A Una Milla de Tu Destino API",
    description="Backend API for travel-hacking POC, flight search, and savings engine.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS configuration
# Allows communication with the React + Vite frontend (local dev and Vercel production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(flights.router)
