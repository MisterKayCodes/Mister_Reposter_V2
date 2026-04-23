
import sys
import os
import asyncio
import logging
from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.bot.routers import register_all_routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RoutingAuditor")

async def check_for_collisions():
    dp = Dispatcher(storage=MemoryStorage())
    register_all_routers(dp)
    
    # Common prefixes we use in the bot
    test_signals = [
        "pairs", "create", "stats", "logs", "admin_users", "admin_settings", "upload",
        "uview_123", "uprom_123", "uprem_123", "upairs_123", "ustat_123", "uaddpair_123",
        "ustp_123_456", "uref_123_456", "tog_123", "loop_123", "prot_123", "force_123",
        "del_123", "cdel_123", "utog_123_456", "uloo_123_456", "uprot_123_456", 
        "uforce_123_456", "udel_123_456", "ucdel_123_456",
        "uacc_confirm_123", "uacc_del_123", "ureconn_123"
    ]

    collisions = []
    logger.info("🕵️‍♂️ Commencing 'Sting Operation' (Routing Simulation)...")

    for signal in test_signals:
        # Create a dummy callback query
        cb = types.CallbackQuery(
            id="0",
            from_user=types.User(id=0, is_bot=False, first_name="Test"),
            chat_instance="0",
            data=signal
        )
        
        # Check which handlers match
        matches = []
        
        # We simulate the dispatcher's check logic
        # Note: This is a simplified version of aiogram's internal routing
        for router in [dp] + list(dp.sub_routers):
            for handler in router.callback_query.handlers:
                # Check filters
                is_match = True
                for filter_obj in handler.filters:
                    # In real usage, filters might be async or sync
                    # For simple MagicFilters, we can usually resolve them
                    try:
                        # This is a bit of a cheat but works for most F.data filters
                        res = filter_obj.callback(cb)
                        if asyncio.iscoroutine(res):
                            res = await res
                        if not res:
                            is_match = False
                            break
                    except Exception:
                        is_match = False
                        break
                
                if is_match:
                    matches.append(f"{handler.callback.__name__} in {router.name or 'Unknown'}")

        if len(matches) > 1:
            collisions.append(
                f"🚨 COLLISION DETECTED for signal: '{signal}'\n"
                f"   Matches: {', '.join(matches)}\n"
                f"   Risk: The bot will only run the FIRST handler it finds!"
            )

    if collisions:
        for c in collisions:
            logger.error(c)
        return False
    
    logger.info("✅ No routing collisions found. The airwaves are clear!")
    return True

if __name__ == "__main__":
    success = asyncio.run(check_for_collisions())
    if not success:
        sys.exit(1)
