"""
DATA: DATABASE
The 'Concrete Mixer'. (Rule 2)
Sets up the asynchronous engine and session factory.
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event, text
from .models import Base
from app.core.config import config

logger = logging.getLogger(__name__)

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

async def ensure_schema_healed():
    """
    Inspects database tables and applies non-destructive migrations
    for missing columns (e.g. Stars paywall & strategy preset columns).
    """
    async with engine.begin() as conn:
        try:
            result = await conn.execute(text("PRAGMA table_info('repost_pairs')"))
            existing_columns = {row[1] for row in result.fetchall()}
            
            new_columns = [
                ("stars_price_short", "INTEGER DEFAULT 0"),
                ("stars_price_long", "INTEGER DEFAULT 0"),
                ("stars_cadence", "INTEGER DEFAULT 4"),
                ("active_preset", "VARCHAR(64) DEFAULT 'custom'")
            ]
            
            for col_name, col_def in new_columns:
                if col_name not in existing_columns:
                    logger.info(f"Database migration: adding column {col_name} to repost_pairs.")
                    await conn.execute(text(f"ALTER TABLE repost_pairs ADD COLUMN {col_name} {col_def}"))

            # Heal users table
            user_res = await conn.execute(text("PRAGMA table_info('users')"))
            existing_user_cols = {row[1] for row in user_res.fetchall()}
            if "worker_niche" not in existing_user_cols:
                logger.info("Database migration: adding column worker_niche to users.")
                await conn.execute(text("ALTER TABLE users ADD COLUMN worker_niche VARCHAR(32)"))
        except Exception as e:
            logger.error(f"Error executing ensure_schema_healed on engine: {e}")

async def init_db():
    """
    Initializes the database. 
    Fulfills Rule 1 by ensuring the 'Memory' is ready before the bot starts.
    """
    async with engine.begin() as conn:
        # Create all tables defined in models.py
        await conn.run_sync(Base.metadata.create_all)
    await ensure_schema_healed()
