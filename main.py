"""
MISTER_REPOSTER V2: MAIN SKELETON
The Birth of the Organism. (Anatomy: Skeleton)
Refined for: Network Resilience and Global Error Handling.
"""
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession # Added for timeout control

from bot.middleware import SessionGuardMiddleware, NetworkRetryMiddleware # Added NetworkRetry
from config import config
from data.database import init_db
from bot.routers import register_all_routers
from utils.log_buffer import log_buffer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

logging.getLogger().addHandler(log_buffer)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Mister Reposter is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 5000)
    await site.start()
    logger.info("Web server started on port 5000")

async def main():
    # 1. ENHANCED SESSION: Increased timeout to 60s to survive "Semaphore Timeouts"
    session = AiohttpSession(timeout=60)
    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        session=session
    )

    await start_web_server()

    try:
        await init_db()
        logger.info("Database initialized and tables created.")

        from bot.handlers.utils import repost_service
        repost_service.set_bot(bot)
        await repost_service.recover_all_listeners()
        logger.info("Startup Recovery complete: All active listeners resumed.")

        dp = Dispatcher(storage=MemoryStorage())
        
        # 2. THE SHIELD: Register NetworkRetryMiddleware globally
        # We put it first so it catches errors from all handlers
        dp.update.outer_middleware(NetworkRetryMiddleware())
        dp.message.outer_middleware(SessionGuardMiddleware())
        
        register_all_routers(dp)
        logger.info("Bot routers registered successfully.")

        logger.info("Mister_Reposter is now online. Polling...")
        
        # 3. POLLING SETUP: Added allowed_updates for faster response
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except Exception as e:
        logger.critical(f"Organism failed to boot: {e}")
    finally:
        # Close session properly
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Organism put to sleep by user.")