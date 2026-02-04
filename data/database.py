"""
DATA: DATABASE
The 'Concrete Mixer'. (Rule 2)
Sets up the asynchronous engine and session factory.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base
from config import config

# Create the Async Engine (Rule 13: Pinned style)
engine = create_async_engine(config.DATABASE_URL, echo=False)

# The 'Librarian's Desk' (Session Factory)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    """
    Initializes the database. 
    Fulfills Rule 1 by ensuring the 'Memory' is ready before the bot starts.
    """
    async with engine.begin() as conn:
        # Create all tables defined in models.py
        await conn.run_sync(Base.metadata.create_all)
