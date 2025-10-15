from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple, Literal, List
from shared import models
import uuid

# Auth provider type
AuthProvider = Literal["steam", "discord"]

class UserRepository:
    """Repository class for user database operations"""
    
    @staticmethod
    def get_user_by_auth_id(db: Session, provider: AuthProvider, auth_id: str) -> Optional[models.User]:
        """Get a user by authentication provider ID"""
        if provider == "steam":
            return db.scalar(select(models.User).where(models.User.steam_id64 == auth_id))
        elif provider == "discord":
            return db.scalar(select(models.User).where(models.User.discord_id == auth_id))
        return None
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
        """Get a user by database ID"""
        return db.scalar(select(models.User).where(models.User.id == user_id))
    
    @staticmethod
    def create_or_update_user(
        db: Session, 
        provider: AuthProvider, 
        auth_id: str, 
        name: Optional[str] = None, 
        avatar_url: Optional[str] = None,
        steam_data: Optional[Dict[str, Any]] = None
    ) -> models.User:
        """Create a new user or update an existing one based on auth provider"""
        # Check if user exists with this provider
        user = UserRepository.get_user_by_auth_id(db, provider, auth_id)
        
        if user:
            # Update existing user
            if name is not None:
                user.name = name
            if avatar_url is not None:
                user.avatar_url = avatar_url
                
            # Update Steam-specific data if provided
            if provider == "steam" and steam_data:
                if "steam_id" in steam_data:
                    user.steam_id = steam_data["steam_id"]
                if "steam_id3" in steam_data:
                    user.steam_id3 = steam_data["steam_id3"]
                if "steam_profile_url" in steam_data:
                    user.steam_profile_url = steam_data["steam_profile_url"]
                    
            user.last_login = datetime.now(timezone.utc)
            db.commit()
            db.refresh(user)
            return user
            
        # Create new user with this provider
        user_data = {
            "name": name,
            "avatar_url": avatar_url,
        }
        
        # Set the appropriate provider ID
        if provider == "steam":
            user_data["steam_id64"] = auth_id
            # Add additional Steam data if available
            if steam_data:
                if "steam_id" in steam_data:
                    user_data["steam_id"] = steam_data["steam_id"]
                if "steam_id3" in steam_data:
                    user_data["steam_id3"] = steam_data["steam_id3"]
                if "steam_profile_url" in steam_data:
                    user_data["steam_profile_url"] = steam_data["steam_profile_url"]
        elif provider == "discord":
            user_data["discord_id"] = auth_id
        
        user = models.User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Automatically assign "user" role to new users
        UserRepository.assign_role(db, user.id, "user")
        
        return user
    
    @staticmethod
    def link_account(
        db: Session,
        user_id: int,
        provider: AuthProvider,
        auth_id: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        steam_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[models.User], bool]:
        """
        Link an auth provider to an existing user account
        Returns (user, success) where success is False if the auth ID is already linked to another account
        """
        # First check if this auth ID is already used by a different user
        existing_user = UserRepository.get_user_by_auth_id(db, provider, auth_id)
        if existing_user and existing_user.id != user_id:
            # Auth ID already linked to a different user
            return existing_user, False
        
        # Get the target user
        user = UserRepository.get_user_by_id(db, user_id)
        if not user:
            return None, False
            
        # Link the account
        if provider == "steam":
            user.steam_id64 = auth_id
            # Add additional Steam data if available
            if steam_data:
                if "steam_id" in steam_data:
                    user.steam_id = steam_data["steam_id"]
                if "steam_id3" in steam_data:
                    user.steam_id3 = steam_data["steam_id3"]
                if "steam_profile_url" in steam_data:
                    user.steam_profile_url = steam_data["steam_profile_url"]
        elif provider == "discord":
            user.discord_id = auth_id
        
        # Update profile data if provided
        if name and not user.name:
            user.name = name
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
            
        db.commit()
        db.refresh(user)
        return user, True
        
    @staticmethod
    def create_session(
        db: Session, 
        user_id: int, 
        provider: AuthProvider,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_days: int = 30
    ) -> models.UserSession:
        """Create a new user session"""
        # Generate a unique session token
        session_token = str(uuid.uuid4())
        
        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        # Create session
        session = models.UserSession(
            user_id=user_id,
            session_token=session_token,
            provider=provider,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    
    @staticmethod
    def get_session(db: Session, session_token: str) -> Optional[models.UserSession]:
        """Get user session by token"""
        return db.scalar(
            select(models.UserSession).where(
                models.UserSession.session_token == session_token,
                models.UserSession.is_active == True,
                or_(
                    models.UserSession.expires_at > datetime.now(timezone.utc),
                    models.UserSession.expires_at == None
                )
            )
        )
    
    @staticmethod
    def invalidate_session(db: Session, session_token: str) -> bool:
        """Invalidate a user session (logout)"""
        session = db.scalar(
            select(models.UserSession).where(
                models.UserSession.session_token == session_token
            )
        )
        
        if not session:
            return False
            
        session.is_active = False
        db.commit()
        return True
        
    @staticmethod
    def unlink_account(
        db: Session,
        user_id: int,
        provider: AuthProvider
    ) -> Tuple[Optional[models.User], bool, bool]:
        """
        Unlink an auth provider from a user account
        Returns (user, success, requires_logout) where:
        - success is False if the user doesn't exist
        - requires_logout is True if this was the user's only authentication method
        """
        # Get the target user
        user = UserRepository.get_user_by_id(db, user_id)
        if not user:
            return None, False, False
        
        # Check if this would leave the user with no authentication methods
        has_steam = user.steam_id64 is not None
        has_discord = user.discord_id is not None
        
        # Determine if this will require a logout (unlinking the only auth method)
        requires_logout = False
        if (provider == "steam" and has_steam and not has_discord) or \
           (provider == "discord" and has_discord and not has_steam):
            # This is the only auth method, still unlink but flag for logout
            requires_logout = True
        
        # Unlink the account
        if provider == "steam" and user.steam_id64:
            user.steam_id64 = None
            user.steam_id = None
            user.steam_id3 = None
            user.steam_profile_url = None
        elif provider == "discord" and user.discord_id:
            user.discord_id = None
            
        db.commit()
        db.refresh(user)
        return user, True, requires_logout

    # Role Management Methods
    
    @staticmethod
    def get_user_roles(db: Session, user_id: int) -> List[models.Role]:
        """Get all roles for a user"""
        return db.scalars(
            select(models.Role)
            .join(models.UserRole)
            .where(models.UserRole.user_id == user_id)
        ).all()
    
    @staticmethod
    def user_has_role(db: Session, user_id: int, role_name: str) -> bool:
        """Check if a user has a specific role"""
        from shared.models import RoleType
        try:
            role_type = RoleType(role_name)
        except ValueError:
            return False
            
        return db.scalar(
            select(models.UserRole)
            .join(models.Role)
            .where(
                models.UserRole.user_id == user_id,
                models.Role.name == role_type
            )
        ) is not None
    
    @staticmethod
    def assign_role(
        db: Session, 
        user_id: int, 
        role_name: str, 
        assigned_by_user_id: Optional[int] = None
    ) -> bool:
        """Assign a role to a user"""
        from shared.models import RoleType
        try:
            role_type = RoleType(role_name)
        except ValueError:
            return False
        
        # Get the role
        role = db.scalar(select(models.Role).where(models.Role.name == role_type))
        if not role:
            return False
        
        # Check if user already has this role
        existing = db.scalar(
            select(models.UserRole).where(
                models.UserRole.user_id == user_id,
                models.UserRole.role_id == role.id
            )
        )
        if existing:
            return True  # Already has role
        
        # Assign the role
        user_role = models.UserRole(
            user_id=user_id,
            role_id=role.id,
            assigned_by=assigned_by_user_id
        )
        db.add(user_role)
        db.commit()
        return True
    
    @staticmethod
    def remove_role(db: Session, user_id: int, role_name: str) -> bool:
        """Remove a role from a user"""
        from shared.models import RoleType
        try:
            role_type = RoleType(role_name)
        except ValueError:
            return False
        
        # Find and remove the user role
        user_role = db.scalar(
            select(models.UserRole)
            .join(models.Role)
            .where(
                models.UserRole.user_id == user_id,
                models.Role.name == role_type
            )
        )
        
        if user_role:
            db.delete(user_role)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_role_by_name(db: Session, role_name: str) -> Optional[models.Role]:
        """Get a role by name"""
        from shared.models import RoleType
        try:
            role_type = RoleType(role_name)
        except ValueError:
            return None
        
        return db.scalar(select(models.Role).where(models.Role.name == role_type))
    
    @staticmethod
    def get_all_roles(db: Session) -> List[models.Role]:
        """Get all available roles"""
        return db.scalars(select(models.Role)).all()