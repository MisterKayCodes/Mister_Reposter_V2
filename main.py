"""
MISTER_REPOSTER V2: MAIN SKELETON
The Birth of the Organism (Hybrid Architecture: Bot + API).
"""
import asyncio
import logging
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

from app.bot.middleware import SessionGuardMiddleware, NetworkRetryMiddleware
from app.core.config import config
from app.data.database import init_db
from app.bot.routers import register_all_routers
from app.services.singleton import repost_service
from app.api.server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def run_api_server():
    """Runs the FastAPI server as an async task."""
    api_app = create_app()
    config_uv = uvicorn.Config(api_app, host="0.0.0.0", port=5555, log_level="info")
    server = uvicorn.Server(config_uv)
    await server.serve()

async def main():
    # 1. GATEKEEPERS
    from app.infrastructure.checks.architecture_inspector import scan_organism
    if not scan_organism():
        logger.critical("Architecture Integrity Check FAILED.")
        return

    # 2. INITIALIZATION
    await init_db()
    
    # Rule 11: Schema Migration (Self-Healing)
    from app.data.repository import UserRepository
    from app.data.database import async_session
    async with async_session() as ds:
        repo = UserRepository(ds)
        await repo.ensure_schema_healed()
        
    # Rule 11: Cleanup Temp Files
    import shutil
    import os
    if os.path.exists("scratch/temp_media"):
        shutil.rmtree("scratch/temp_media")
        os.makedirs("scratch/temp_media")
        
    logger.info("Database initialized and healed.")

    session = AiohttpSession(timeout=60)
    bot = Bot(token=config.BOT_TOKEN.get_secret_value(), session=session)
    repost_service.set_bot(bot)
    await repost_service.recover_all_listeners()
    
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(NetworkRetryMiddleware())
    dp.message.outer_middleware(SessionGuardMiddleware())
    register_all_routers(dp)
    
    logger.info("Hybrid Organism is ready. Starting Bot + API...")

    # 3. HYBRID BOOT: Bot Polling + FastAPI
    try:
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            run_api_server()
        )
    except Exception as e:
        logger.critical(f"Organism failed: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Organism put to sleep.")
