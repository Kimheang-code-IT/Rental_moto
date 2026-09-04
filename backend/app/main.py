import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v2.router import api_router
from app.api.v2.health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import close_redis

setup_logging()
logger = logging.getLogger("hollywing")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.assert_safe_for_production()
    logger.info("HollyWing Motor API starting (%s)", settings.environment)
    yield
    await close_redis()
    logger.info("HollyWing Motor API stopped")


def create_app() -> FastAPI:
    docs_enabled = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    cors_kwargs: dict = {
        "allow_origins": settings.cors_origin_list,
        "allow_credentials": False,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.environment == "development" and settings.cors_allow_private_networks:
        cors_kwargs["allow_origin_regex"] = (
            r"https?://("
            r"localhost|127\.0\.0\.1"
            r"|192\.168\.\d{1,3}\.\d{1,3}"
            r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
            r")(:\d+)?$"
        )
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "Internal server error"}})

    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
