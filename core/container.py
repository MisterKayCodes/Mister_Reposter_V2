"""
CONTAINER: THE WIRING
Dependency Injection. (Anatomy: Skeleton)
Connects the Nervous System to the Mouth.
"""
from services.session_manager import SessionService
from services.repost_engine import RepostService

# Simple Singleton instances for testing
session_service = SessionService()
repost_service = RepostService()
