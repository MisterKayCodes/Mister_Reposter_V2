import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import time
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def test_scheduler():
    from services.repost_engine import RepostService
    
    # Mock Telethon
    mock_telethon = AsyncMock()
    mock_telethon.get_total_messages.return_value = 100
    mock_telethon.start_listener = AsyncMock()
    
    # Mock messages
    class MockMsg:
        def __init__(self, msg_id):
            self.id = msg_id
            self.message = f"Test message {msg_id}"
            self.grouped_id = None
            self.media = None
    
    mock_telethon.fetch_messages_from.return_value = [MockMsg(i) for i in range(1, 6)]
    mock_telethon.get_message.return_value = MockMsg(1)
    
    engine = RepostService()
    engine.telethon = mock_telethon
    
    # Mock send_with_retry
    send_times = []
    
    async def mock_send(*args, **kwargs):
        logging.info(f"MOCK SEND EXECUTED at {time.time()}")
        send_times.append(time.time())
        return {"ok": True, "message": args[2]}
        
    engine._send_with_retry = AsyncMock(side_effect=mock_send)
    
    # Mock DB - we patch async_session
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
        
    async def mock_async_session():
        return MockSession()
        
    # We will test backfill with interval = 0.05 minutes (3 seconds)
    with patch("services.repost_engine.async_session", return_value=MockSession()) as mock_db, \
         patch("services.repost_engine.UserRepository", return_value=MockRepo()):
             
        task = asyncio.create_task(
            engine._backfill_from_message(
                user_id=1, source="src", destination="dst", 
                from_msg_id=1, filter_type=0, replacement_link=None, 
                interval_minutes=0.05, pair_id=1
            )
        )
        
        # Let it run for 10 seconds
        await asyncio.sleep(10)
        task.cancel()
        
    print("Test Complete.")
    print("Send times:")
    if len(send_times) > 1:
        diffs = [send_times[i] - send_times[i-1] for i in range(1, len(send_times))]
        print(f"Diffs between consecutive messages (should be ~3.0s): {diffs}")
    else:
        print(f"Messages sent: {len(send_times)}")

if __name__ == "__main__":
    asyncio.run(test_scheduler())
