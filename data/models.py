"""
DATA: MODELS
Defines the database structure for users and their reposting rules.
"""
from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Session management
    has_active_session: Mapped[bool] = mapped_column(Boolean, default=False)
    session_string: Mapped[str | None] = mapped_column(String)  # Path to .session file or Base64

class RepostPair(Base):
    """
    Stores the source/destination links and the user's specific filter settings.
    """
    __tablename__ = "repost_pairs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    source_id: Mapped[str] = mapped_column(String) 
    destination_id: Mapped[str] = mapped_column(String)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_reposted_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Filter settings:
    # 0 = No changes, 1 = Remove links/usernames, 2 = Replace with my link
    filter_type: Mapped[int] = mapped_column(Integer, default=1)
    replacement_link: Mapped[str | None] = mapped_column(String, nullable=True)