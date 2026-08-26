import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.bot.clock import ClockStopMiddleware, router as clock_router
from app.bot.quiz_engine import router as quiz_router
from app.bot.automation import router as automation_router
from app.bot.automation_lesson import router as automation_lesson_router
from app.bot.library import router as library_router
from app.bot.sections import router as sections_router
from app.bot.ai_quizzes import router as ai_quizzes_router
from app.bot.ai_navigation import router as ai_navigation_router
from app.bot.ai_pages import router as ai_pages_router
from app.bot import ui_fixes
from app.config_gemini import Settings
from app.database import Database
from app.services import AIService, FileExtractor, QuizGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

async def health(request: web.Request) -> web.Response:
    return web.json_response({"status":"ok","service":"TOFAN AI 2026"})

async def run_web_server(dp: Dispatcher, bot: Bot) -> web.AppRunner:
    app=web.Application(); app.router.add_get("/",health); app.router.add_get("/health",health)
    external_url=(os.getenv("TELEGRAM_WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    secret=os.getenv("TELEGRAM_WEBHOOK_SECRET") or None
    if not external_url: raise RuntimeError("TELEGRAM_WEBHOOK_URL or RENDER_EXTERNAL_URL is required in production.")
    path="/telegram/webhook"; url=f"{external_url}{path}"
    SimpleRequestHandler(dispatcher=dp,bot=bot,handle_in_background=True,secret_token=secret).register(app,path=path)
    await bot.set_webhook(url=url,secret_token=secret,drop_pending_updates=True,allowed_updates=dp.resolve_used_update_types())
    setup_application(app,dp,bot=bot)
    runner=web.AppRunner(app); await runner.setup(); await web.TCPSite(runner,"0.0.0.0",int(os.getenv("PORT","10000"))).start(); return runner

async def main() -> None:
    settings=Settings.from_env(); settings.ensure_directories()
    db=Database(settings.database_url or str(settings.database_path))
    extractor=FileExtractor(); ai_service=AIService(settings.gemini_api_key,settings.gemini_model,settings.database_path); quiz_generator=QuizGenerator(ai_service,settings.database_path)
    bot=Bot(token=settings.telegram_bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); dp=Dispatcher(storage=MemoryStorage())
    dp["db"]=db; dp["extractor"]=extractor; dp["ai_service"]=ai_service; dp["quiz_generator"]=quiz_generator
    dp.callback_query.outer_middleware(ClockStopMiddleware())

    dp.include_router(clock_router)
    dp.include_router(quiz_router)
    dp.include_router(sections_router)
    dp.include_router(ai_quizzes_router)
    dp.include_router(ai_navigation_router)
    dp.include_router(ai_pages_router)
    dp.include_router(library_router)
    dp.include_router(automation_lesson_router)
    dp.include_router(automation_router)

    external_url=os.getenv("TELEGRAM_WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if bool(os.getenv("RENDER_SERVICE_ID") or os.getenv("RENDER_EXTERNAL_URL") or external_url):
        runner=await run_web_server(dp,bot)
        try: await asyncio.Event().wait()
        finally: await runner.cleanup(); await bot.session.close()
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        try: await dp.start_polling(bot)
        finally: await bot.session.close()

if __name__ == "__main__": asyncio.run(main())
