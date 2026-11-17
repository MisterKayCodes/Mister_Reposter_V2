"""
SERVICES: HYPE BRIDGE
Non-blocking social proof integration with Mister Simulator API.
Triggers views and reactions on destination channels immediately after reposting.
"""
import asyncio
import aiohttp
import logging
from app.core.config import config

logger = logging.getLogger(__name__)

SIMULATOR_API_URL = getattr(config, "SIMULATOR_API_URL", "http://127.0.0.1:8012")
SIMULATOR_API_KEY = getattr(config, "SIMULATOR_API_KEY", "") or getattr(config, "MISTER_SIMULATOR_API_KEY", "") or "msc_simulator_master_key_2026"
DEFAULT_HYPE_EMOJIS = ["🔥", "👀", "👏", "🚀", "❤️"]


async def trigger_simulator_hype(destination: str | int, message_id: int):
    """
    Fire-and-forget ping to Mister Simulator to view and react to newly reposted message.
    """
    if not message_id or not destination:
        return

    url = f"{str(SIMULATOR_API_URL).rstrip('/')}/api/v1/telethon/hype-post"
    headers = {
        "X-API-Key": str(SIMULATOR_API_KEY) if SIMULATOR_API_KEY else "",
        "Content-Type": "application/json"
    }
    payload = {
        "channel_id": str(destination),
        "message_id": int(message_id),
        "step_type": "repost_organic",
        "emojis": DEFAULT_HYPE_EMOJIS
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201, 202):
                    logger.info(f"🚀 [HYPE BRIDGE] Triggered Simulator hype for msg={message_id} in dest={destination}")
                else:
                    text = await resp.text()
                    logger.warning(f"[HYPE BRIDGE] Simulator returned HTTP {resp.status}: {text[:100]}")
    except Exception as e:
        logger.warning(f"[HYPE BRIDGE] Could not contact Simulator (non-fatal): {e}")
