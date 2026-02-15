"""
MISTER_REPOSTER V2: MAIN SKELETON
The Birth of the Organism. (Anatomy: Skeleton)
"""
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.middleware import SessionGuardMiddleware
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
    bot = Bot(token=config.BOT_TOKEN.get_secret_value())

    await start_web_server()

    try:
        await init_db()
        logger.info("Database initialized and tables created.")

        from bot.handlers.utils import repost_service
        repost_service.set_bot(bot)
        await repost_service.recover_all_listeners()
        logger.info("Startup Recovery complete: All active listeners resumed.")

        dp = Dispatcher(storage=MemoryStorage())
        register_all_routers(dp)
        dp.message.outer_middleware(SessionGuardMiddleware())
        logger.info("Bot routers registered successfully.")

        logger.info("Mister_Reposter is now online. Polling...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.critical(f"Organism failed to boot: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Organism put to sleep by user.")
