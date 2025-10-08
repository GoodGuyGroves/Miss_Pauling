from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from typing import Optional, List
from .database import Base

class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # User profile data
    name: Mapped[Optional[str]] = mapped_column(String(128))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    
    # Authentication providers - nullable as users may not have all providers
    steam_id64: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True) # SteamID64 format (17 digits)
    steam_id: Mapped[Optional[str]] = mapped_column(String(32))  # Legacy SteamID format (STEAM_0:X:XXXXXXXX)
    steam_id3: Mapped[Optional[str]] = mapped_column(String(32)) # SteamID3 format ([U:1:XXXXXXX])
    steam_profile_url: Mapped[Optional[str]] = mapped_column(Text) # Steam community profile URL
    discord_id: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True)
    
    # Relationship to user sessions
    sessions: Mapped[List["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        identifiers = []
        if self.steam_id64 is not None:
            identifiers.append(f"steam:{self.steam_id64}")
        if self.discord_id is not None:
            identifiers.append(f"discord:{self.discord_id}")
        
        ids = ", ".join(identifiers)
        return f"<User(id={self.id}, name={self.name}, {ids})>"
    
class UserSession(Base):
    """User session model for tracking login sessions"""
    __tablename__ = "user_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(20))  # 'steam' or 'discord'
    ip_address: Mapped[Optional[str]] = mapped_column(String(45)) # Supports IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationship to user
    user: Mapped["User"] = relationship(back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, provider={self.provider}, active={self.is_active})>"