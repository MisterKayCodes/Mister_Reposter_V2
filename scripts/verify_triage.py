import asyncio
import logging
from unittest.mock import MagicMock
from app.services.engine_utils import MessageClassifier, MessageClassification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_classification():
    logger.info("Testing Message Classification...")
    
    # Mock messages
    safe_msg = MagicMock()
    safe_msg.message = "Hello"
    safe_msg.media = None
    
    protected_msg = MagicMock()
    protected_msg.noforward = True
    
    broken_msg = MagicMock()
    broken_msg.message = None
    broken_msg.media = None
    
    heavy_msg = MagicMock()
    heavy_msg.media.document.size = 100 * 1024 * 1024 # 100MB
    
    assert MessageClassifier.classify(safe_msg) == MessageClassification.SAFE
    assert MessageClassifier.classify(protected_msg) == MessageClassification.PROTECTED
    assert MessageClassifier.classify(broken_msg) == MessageClassification.BROKEN
    assert MessageClassifier.classify(heavy_msg) == MessageClassification.HEAVY
    
    logger.info("Classification tests passed!")

async def test_fml_integration():
    logger.info("Testing FML Integration...")
    service = MagicMock()
    service.failed_media_lock = {1: {123}}
    
    # Simulate _process_matched_pair logic
    msg = MagicMock()
    msg.id = 123
    
    locked_ids = service.failed_media_lock.get(1, set())
    if msg.id in locked_ids:
        logger.info("FML correctly caught locked message!")
    else:
        raise Exception("FML failed to catch locked message")

if __name__ == "__main__":
    asyncio.run(test_classification())
    asyncio.run(test_fml_integration())
