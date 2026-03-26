import asyncio
import logging
from unittest.mock import AsyncMock, patch
import time
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def test_queue_starve():
    from services.repost_engine import RepostService
    
    # Mock Telethon return values
    mock_telethon = AsyncMock()
    mock_telethon.get_total_messages.return_value = 100
    
    # Return fake messages
    class MockMsg:
        def __init__(self, id):
            self.id = id
            self.message = "test msg"
            self.grouped_id = None
            self.media = None
    
    mock_telethon.fetch_messages_from.return_value = [MockMsg(i) for i in range(1, 5)]
    
    engine = RepostService()
    engine.telethon = mock_telethon
    
    # Send mock
    send_times = []
    async def mock_send(*args, **kwargs):
        logging.info(f"MOCK SEND (Backfill Msg {args[2].id}) executed.")
        send_times.append(time.time())
        return {"ok": True, "message": args[2]}
    engine._send_with_retry = AsyncMock(side_effect=mock_send)
    
    # Mock DB
    class MockPair:
        def __init__(self):
            self.id = 1
            self.is_active = True
            self.status = "active"
            
    class MockRepo:
        async def update_pair_total_posts(self, *args): pass
        async def get_pair_by_id(self, *args): return MockPair()
        async def update_pair_start_id(self, *args): pass
    
    class MockSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    
    original_sleep = asyncio.sleep
    sleep_count = 0
    
    # We will simulate a fast queue interval so we can see multiple cycles
    engine.schedule_queue[1] = [{"user_id": 1, "destination": "dst", "messages": [MockMsg("live")]}]
    logging.info("Live message injected into schedule_queue[1]")
    
    async def mock_sleep(seconds):
        nonlocal sleep_count
        sleep_count += 1
        logging.info(f"MOCK SLEEP CALLED for {seconds}s")
        await original_sleep(0.1) # speed up
        
    with patch("services.repost_engine.async_session", return_value=MockSession()) as mock_db, \
         patch("services.repost_engine.UserRepository", return_value=MockRepo()), \
         patch("asyncio.sleep", side_effect=mock_sleep):
             
        task = asyncio.create_task(
            engine._backfill_from_message(
                user_id=1, source="src", destination="dst", 
                from_msg_id=1, filter_type=0, replacement_link=None, 
                interval_minutes=240, pair_id=1
            )
        )
        
        # We let the backfill spin for 1s.
        # If the bug exists, backfill won't send anything. It will just sleep(60) repeatedly.
        await original_sleep(1)
        task.cancel()
        
    print("Test Complete.")
    print(f"Total backfill messages processed alongside live queue: {len(send_times)}")
    if len(send_times) > 0:
        print("PASS: The backfill engine processed messages even while live messages were waiting in the queue!")
    else:
        print("FAIL: The backfill engine starved and sent no messages!")

if __name__ == "__main__":
    asyncio.run(test_queue_starve())
