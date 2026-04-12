"""
INFRASTRUCTURE: UI INTEGRITY AUDIT
Automatically verifies all callback handlers for breakages after refactoring.
(Rule 11: Safety First)
"""
import sys
import os
import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Senior Fix: Ensure we can import from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

# Import all handlers to register them
from app.bot.handlers import menu, pairs, session, stats, logs

# Logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("UI_Audit")

async def run_audit():
    print("Starting UI Integrity Audit...")
    
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_routers(
        menu.router,
        pairs.router,
        session.router,
        stats.router,
        logs.router
    )
    
    # 1. Inspect Registration
    print("Mapping Callback Patterns...")
    callbacks = []
    for router in dp.sub_routers:
        for observer in router.observers.values():
            if observer.event_name == "callback_query":
                for handler in observer.handlers:
                    callbacks.append(handler)
    
    print(f"Found {len(callbacks)} callback handlers.")
    
    # 2. Simulated Firing
    test_payloads = [
        "main", "create", "pairs", "stats", "upload", "logs", "delall",
        "tog_1", "loop_1", "del_1", "cdel_1", "statp_1", "refr_1",
        "setfilt_1", "setsched_0", "skip_start_msg", "confirm_pair"
    ]
    
    failed = 0
    passed = 0
    
    # Mock Bot for feed_update
    mock_bot = AsyncMock()
    
    for payload in test_payloads:
        print(f"  Testing Payload: '{payload}'...", end=" ")
        try:
            # Create REAL Data objects so Pydantic validation passes
            user = types.User(id=999, is_bot=False, first_name="Tester")
            chat = types.Chat(id=999, type="private")
            message = types.Message(message_id=1, date=datetime.now(), chat=chat, text="test")
            
            callback = types.CallbackQuery(
                id="1", 
                from_user=user, 
                chat_instance="1", 
                data=payload, 
                message=message
            )
            
            update = types.Update(update_id=1, callback_query=callback)
            
            # Use propagate_event to avoid full model_dump serialization overhead
            # or just use feed_update if the structure is correct.
            # We use feed_update but we must ensure the objects are valid pydantic models.
            await dp.feed_update(bot=mock_bot, update=update)
            
            print("OK")
            passed += 1
        except Exception as e:
            # We only care about INTERNAL code errors (ImportError, AttributeError, etc.)
            # If it's a "Bot was not found" or similar from Aiogram internals, we might ignore.
            # But usually, it fails if a handler tries to call something that doesn't exist.
            print(f"FAIL: {type(e).__name__}")
            logger.error(f"Audit failure for '{payload}':", exc_info=True)
            failed += 1

    print("\n" + "="*30)
    print(f"AUDIT COMPLETE")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("="*30)

    if failed > 0:
        print("CRITICAL: UI inconsistencies detected! Fix imports/wiring before deployment.")
        return 1
    
    print("RESOLVED: UI Integrity is Senior-grade.")
    return 0

if __name__ == "__main__":
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///data/test_audit.db"
    asyncio.run(run_audit())
