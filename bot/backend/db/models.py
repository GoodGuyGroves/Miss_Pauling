from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey, Table
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # User profile data
    name = Column(String(128), nullable=True)
    avatar_url = Column(Text, nullable=True)
    
    # Authentication providers - nullable as users may not have all providers
    steam_id64 = Column(String(32), unique=True, nullable=True, index=True) # SteamID64 format (17 digits)
    steam_id = Column(String(32), nullable=True)  # Legacy SteamID format (STEAM_0:X:XXXXXXXX)
    steam_id3 = Column(String(32), nullable=True) # SteamID3 format ([U:1:XXXXXXX])
    steam_profile_url = Column(Text, nullable=True) # Steam community profile URL
    discord_id = Column(String(32), unique=True, nullable=True, index=True)
    
    # Relationship to user sessions
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        identifiers = []
        if self.steam_id64:
            identifiers.append(f"steam:{self.steam_id64}")
        if self.discord_id:
            identifiers.append(f"discord:{self.discord_id}")
        
        ids = ", ".join(identifiers)
        return f"<User(id={self.id}, name={self.name}, {ids})>"
    
class UserSession(Base):
    """User session model for tracking login sessions"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    provider = Column(String(20), nullable=False)  # 'steam' or 'discord'
    ip_address = Column(String(45), nullable=True) # Supports IPv6
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationship to user
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, provider={self.provider}, active={self.is_active})>"