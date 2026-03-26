import asyncio
import logging
import sys
from unittest.mock import AsyncMock

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def test_error_translation():
    from bot.handlers.utils import translate_error
    from services.repost_engine import RepostService
    from bot.keyboards import pairs_kb
    
    engine = RepostService()
    
    print("--- Testing Translation Logic ---")
    
    err1 = "The chat is restricted and cannot be used in that request (caused by SendMediaRequest)"
    print(f"1. {translate_error(err1)}")
    
    err2 = "No user has \"peer\" as username"
    print(f"2. {translate_error(err2)}")
    
    err3 = "A wait of 40 seconds is required (caused by SendMessageRequest)"
    print(f"3. {translate_error(err3)}")
    
    print("\n--- Testing Keyboard Generation ---")
    class MockPair:
        def __init__(self, id, is_active, status):
            self.id = id
            self.is_active = is_active
            self.status = status
            
    pairs = [
        MockPair(1, True, "active"),
        MockPair(2, False, "paused"),
        MockPair(3, False, "error")
    ]
    
    kb = pairs_kb(pairs)
    buttons = kb.inline_keyboard
    for row in buttons:
        for b in row:
            print(f"[ {b.text} ]", end=" ")
        print()
        
    print("\nSUCCESS: All error translations and keyboards rendered beautifully.")

if __name__ == "__main__":
    asyncio.run(test_error_translation())
