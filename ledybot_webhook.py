# ledybot_webhook.py
# FastAPI + python-telegram-bot (v20.3) webhook app for Render

import os
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- Config ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
BASE_URL = os.environ.get("BASE_URL", "").strip()  # e.g. https://ledybot-clean.onrender.com

VERSION = "1.0.0"
COMMIT_HASH = "dev"  # можно заменить на реальный commit id при деплое
START_TIME = datetime.utcnow().isoformat()

if not BOT_TOKEN:
    raise RuntimeError("ENV BOT_TOKEN is required.")

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("ledybot")

# ---------- FastAPI ----------
app = FastAPI(title="LEDYBOT Webhook", version=VERSION)

# PTB application (single global instance)
application = Application.builder().token(BOT_TOKEN).build()


# ---------- Handlers ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я LEDYBOT 🌸 — твоя быстрая, умная и надёжная помощница!\n"
        "Скажи, что ищешь — и я всё подберу красиво."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Я рядом: /start — приветствие, просто напиши, что искать.")


async def echo_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        q = update.message.text.strip()
        await update.message.reply_text(f"🔎 Ищу: «{q}»...\n(Пока тренировка, скоро — по-настоящему 🚀)")


# Register handlers
application.add_handler(CommandHandler("start", start_cmd))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_msg))


# ---------- Webhook routes ----------
@app.get("/")
async def root() -> Dict[str, Any]:
    return {"ok": True, "bot": "LEDYBOT", "mode": "webhook"}


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/version")
async def version() -> Dict[str, Any]:
    return {
        "version": VERSION,
        "commit": COMMIT_HASH,
        "started": START_TIME,
        "utc_now": datetime.utcnow().isoformat()
    }


@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request) -> Response:
    if token != BOT_TOKEN:
        return JSONResponse({"status": "forbidden"}, status_code=403)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "bad request"}, status_code=400)

    try:
        update = Update.de_json(data, application.bot)
        # Логируем тип апдейта и текст, если есть
        if update.message and update.message.text:
            log.info(f"Update: message from {update.effective_user.id} - {update.message.text}")
        elif update.callback_query:
            log.info(f"Update: callback from {update.effective_user.id} - {update.callback_query.data}")
        else:
            log.info(f"Update: type {update.update_id}")
        await application.process_update(update)
    except Exception as e:
        log.exception("Failed to process update: %s", e)
        return JSONResponse({"status": "error"}, status_code=500)

    return JSONResponse({"status": "ok"})


# ---------- Lifecycle ----------
@app.on_event("startup")
async def on_startup() -> None:
    await application.initialize()
    await application.start()

    try:
        if BASE_URL:
            url = f"{BASE_URL.rstrip('/')}/webhook/{BOT_TOKEN}"
            await application.bot.set_webhook(url=url, drop_pending_updates=True)
            log.info("Webhook set: %s", url)
        else:
            log.info("BASE_URL not set; skipping set_webhook.")
    except Exception as e:
        log.exception("Failed to set webhook: %s", e)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    try:
        await application.bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    await application.stop()
    await application.shutdown()