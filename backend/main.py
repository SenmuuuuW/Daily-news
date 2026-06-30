from fastapi import FastAPI

from api.health import router as health_router
from api.webhook import router as webhook_router
from config import settings
from storage.db import init_db
from utils.logger import configure_logging


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    init_db()

    app = FastAPI(
        title="Daily WeCom Digest Bot",
        version="0.1.0",
        description="Backend MVP for personalized Enterprise WeChat daily digests.",
    )
    app.include_router(health_router)
    app.include_router(webhook_router, prefix="/api")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
