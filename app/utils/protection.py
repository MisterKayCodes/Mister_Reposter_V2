import asyncio
import random
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AntiBanGuard:
    """
    A unified utility to protect worker accounts from Telegram bans.
    Implements jittered sleeps and intelligent flood-wait handling.
    """
    
    @staticmethod
    async def human_jitter(base_seconds: float = 2.0):
        """Adds a random jitter to simulate human delay."""
        jitter = random.uniform(0.5, 3.0)
        total = base_seconds + jitter
        logger.debug(f"AntiBan: Human jitter sleep for {total:.2f}s")
        await asyncio.sleep(total)

    @staticmethod
    async def throttle(pair_id: int, is_protected: bool = False):
        """
        Global throttle for media transfers.
        Protected mode requires much stricter delays to avoid being flagged.
        """
        if is_protected:
            # Protected media is highly sensitive to scraping behavior
            wait_time = random.randint(15, 45)
            logger.info(f"AntiBan [Pair #{pair_id}]: Throttling protected transfer for {wait_time}s")
        else:
            # Standard light throttle
            wait_time = random.randint(2, 8)
            logger.debug(f"AntiBan [Pair #{pair_id}]: Throttling standard transfer for {wait_time}s")
            
        await asyncio.sleep(wait_time)

    @staticmethod
    def calculate_cooldown(flood_seconds: int) -> datetime:
        """Calculates exact timestamp to resume after a FloodWait."""
        # Add extra buffer to ensure the server-side bucket is actually cleared
        buffer = random.randint(30, 120)
        return datetime.utcnow() + timedelta(seconds=flood_seconds + buffer)
