"""
SERVICES: SINGLETON
The 'Shared Brain' of the Organism.
Ensures that the Bot and API share the same service instances and memory.
"""
from app.services.repost_engine import RepostService

# Global singleton instance
repost_service = RepostService()
