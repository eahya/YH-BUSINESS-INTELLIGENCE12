from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes import router
from app.config import get_settings
from app.db import Base, engine
from app import models  # noqa: F401 -- registers every mapped table before create_all

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.app_env.lower() == "production":
        if settings.jwt_secret == "replace-with-a-long-random-secret-before-use":
            raise RuntimeError("Set a unique JWT_SECRET before starting in production")
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    description="Multi-company finance, operations, and local analytics API.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Company-ID"],
)
app.include_router(router)


@app.exception_handler(IntegrityError)
async def relational_conflict(_request: Request, _exc: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={
        "detail": "The request conflicts with an existing record or a relational data rule."
    })


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
