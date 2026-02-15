"""
DATA: DATABASE
The 'Concrete Mixer'. (Rule 2)
Sets up the asynchronous engine and session factory.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base
from config import config

# Create the Async Engine (Added connect_args for SQLite stability)
engine = create_async_engine(
    config.DATABASE_URL, 
    echo=False,
    connect_args={"timeout": 30}  # Tells SQLite to wait 30 seconds for locks to clear
)

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
