from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from seju_lite.bus.events import InboundMessage
from seju_lite.runtime.app import SejuApp, create_app
from seju_lite.runtime.runner import close_app

logger = logging.getLogger("seju_lite.api")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    user_id: str = Field(default="web-user", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


class HealthResponse(BaseModel):
    status: str
    app: str
    model: str


def _parse_csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_cors_config() -> dict[str, Any]:
    origins = _parse_csv_env("SEJU_API_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173")
    methods = _parse_csv_env("SEJU_API_CORS_METHODS", "GET,POST,OPTIONS")
    headers = _parse_csv_env("SEJU_API_CORS_HEADERS", "*")
    allow_credentials = os.getenv("SEJU_API_CORS_ALLOW_CREDENTIALS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return {
        "allow_origins": origins,
        "allow_methods": methods,
        "allow_headers": headers,
        "allow_credentials": allow_credentials,
    }


def build_api(config_path: str | Path = "config.json") -> FastAPI:
    state: dict[str, SejuApp | None] = {"app_ctx": None}
    api_key = os.getenv("SEJU_API_KEY", "").strip()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        app_ctx = await create_app(config_path)
        state["app_ctx"] = app_ctx
        try:
            yield
        finally:
            await close_app(app_ctx)
            state["app_ctx"] = None

    app = FastAPI(title="seju-lite API", version="0.1.0", lifespan=lifespan)
    cors_config = _build_cors_config()
    app.add_middleware(CORSMiddleware, **cors_config)

    @app.middleware("http")
    async def api_key_auth(request: Request, call_next):
        if api_key and request.url.path != "/health":
            auth = request.headers.get("authorization", "")
            expected = f"Bearer {api_key}"
            if auth != expected:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        logger.info(
            "request_id=%s method=%s path=%s status=%s elapsed_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        app_ctx = state["app_ctx"]
        if app_ctx is None:
            raise HTTPException(status_code=503, detail="App context is not ready")

        return HealthResponse(
            status="ok",
            app=app_ctx.config.app.name,
            model=app_ctx.config.provider.model,
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        app_ctx = state["app_ctx"]
        if app_ctx is None:
            raise HTTPException(status_code=503, detail="App context is not ready")

        inbound = InboundMessage(
            channel="web",
            sender_id=payload.user_id,
            chat_id=payload.conversation_id,
            content=payload.message,
            metadata=payload.metadata,
        )

        try:
            reply = await app_ctx.agent.process_message(inbound)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "-")
            logger.exception("chat_failed request_id=%s", request_id)
            raise HTTPException(status_code=500, detail="Failed to process message") from exc

        return ChatResponse(reply=reply, conversation_id=payload.conversation_id)

    return app
