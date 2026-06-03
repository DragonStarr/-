from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from operator_day.api.routes import router
from operator_day.bot.handlers import router as bot_router
from operator_day.config import get_settings
from operator_day.db import dispose_engine, ensure_local_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await ensure_local_database()
    if settings.telegram_bot_token:
        bot = Bot(token=settings.telegram_bot_token)
        dp = Dispatcher()
        dp.include_router(bot_router)
        app.state.bot = bot
        app.state.dispatcher = dp
    yield
    bot = getattr(app.state, "bot", None)
    if bot:
        await bot.session.close()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    app = FastAPI(title="Operator Day", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        return response

    app.include_router(router)

    @app.post("/telegram/webhook")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, str]:
        if settings.telegram_webhook_secret and (
            x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
        ):
            raise HTTPException(status_code=403, detail="Неверная подпись webhook")
        bot = getattr(request.app.state, "bot", None)
        dp = getattr(request.app.state, "dispatcher", None)
        if not bot or not dp:
            return {"status": "skipped", "reason": "telegram token is not configured"}
        update = Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot=bot, update=update)
        return {"status": "ok"}

    return app
