"""
DATA: MODELS
The 'Vault Blueprint'. (Rule 2)
Defines the structure of long-term memory.
"""
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Linked session info
    has_active_session: Mapped[bool] = mapped_column(Boolean, default=False)
    session_string: Mapped[str | None] = mapped_column(String)  # Optional: Store string here or path to file

class RepostPair(Base):
    """
    Defines the relationship between a source and a destination.
    """
    __tablename__ = "repost_pairs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    source_id: Mapped[str] = mapped_column(String) # Channel username or ID
    destination_id: Mapped[str] = mapped_column(String)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_reposted_at: Mapped[datetime | None] = mapped_column(DateTime)
