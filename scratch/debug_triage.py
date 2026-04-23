
import asyncio
import logging
from unittest.mock import MagicMock
from app.services.engine_utils import MessageClassifier, MessageClassification

logging.basicConfig(level=logging.DEBUG)

async def debug_classification():
    # Mock messages
    safe_msg = MagicMock()
    safe_msg.message = "Hello"
    safe_msg.media = None
    safe_msg.noforward = False
    
    result = MessageClassifier.classify(safe_msg)
    print(f"Result: {result}")
    
    # Check what getattr returns
    print(f"getattr message: {getattr(safe_msg, 'message', None)}")
    print(f"getattr media: {getattr(safe_msg, 'media', None)}")
    print(f"getattr noforward: {getattr(safe_msg, 'noforward', False)}")

if __name__ == "__main__":
    asyncio.run(debug_classification())
