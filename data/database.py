"""
DATA: DATABASE
The 'Concrete Mixer'. (Rule 2)
Sets up the asynchronous engine and session factory.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event
from .models import Base
from config import config

# Create the Async Engine
engine = create_async_engine(
    config.DATABASE_URL, 
    echo=False
)

# Rule 11: SQLite Resilience (The 'Conductor' Fix)
# We enable WAL mode and a busy timeout to prevent "Database is locked" at scale.
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

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
