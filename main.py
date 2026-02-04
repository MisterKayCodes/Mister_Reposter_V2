"""
MISTER_REPOSTER V2: MAIN SKELETON
The Birth of the Organism. (Anatomy: Skeleton)
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from data.database import init_db
from bot.routers import register_all_routers
from services.repost_engine import RepostService

# Rule 10: Observability
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    # Initialize bot first so 'finally' block can always find it
    bot = Bot(token=config.BOT_TOKEN.get_secret_value())
    
    try:
        # 1. Initialize the Vault (Rule 1: Known State)
        await init_db()
        logger.info("Database initialized and tables created.")

        # 2. Wake up the Nervous System (Rule 7: Resilience)
        repost_service = RepostService()
        await repost_service.recover_all_listeners()
        logger.info("Startup Recovery complete: All active listeners resumed.")

        # 3. Setup the Mouth (Bot Interface)
        dp = Dispatcher(storage=MemoryStorage())
        register_all_routers(dp)
        logger.info("Bot routers registered successfully.")

        # 4. Start the Heartbeat
        logger.info("Mister_Reposter is now online. Polling...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.critical(f"Organism failed to boot: {e}")
    finally:
        # Rule 12: Handle errors explicitly
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Organism put to sleep by user.")
