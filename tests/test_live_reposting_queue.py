import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
import time
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def test_live_queue():
    from services.repost_engine import RepostService
    from services.media_cache import MediaCache
    
    engine = RepostService()
    engine.media_cache = MagicMock()
    engine.media_cache.clear_pair = MagicMock()
    
    send_times = []
    
    async def mock_send(*args, **kwargs):
        logging.info(f"MOCK LIVE SEND EXECUTED at {time.time()}")
        send_times.append(time.time())
        return {"ok": True, "message": args[2]}
        
    engine._send_with_retry = AsyncMock(side_effect=mock_send)
    
    start_time = time.time()
    
    # Send a live message. Interval = 0.05 min (3 seconds)
    engine._enqueue_scheduled(
        pair_id=1, user_id=1, destination="dst", 
        messages=[{"id": 1, "message": "hello live"}], 
        interval_minutes=0.05
    )
    
    # 1 second later, send another one
    await asyncio.sleep(1)
    engine._enqueue_scheduled(
        pair_id=1, user_id=1, destination="dst", 
        messages=[{"id": 2, "message": "hello live 2"}], 
        interval_minutes=0.05
    )
    
    # Wait for completion (the timer should fire ~3 seconds after the FIRST message)
    await asyncio.sleep(4)
    
    # Validate
    diff = send_times[0] - start_time if send_times else -1
    print(f"Messages sent: {len(send_times)}")
    print(f"Time to send: {diff:.2f}s (Expected ~3.0s)")

if __name__ == "__main__":
    asyncio.run(test_live_queue())
