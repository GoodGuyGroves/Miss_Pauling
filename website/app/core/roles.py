"""
Role-based access control utilities and decorators.
"""
from typing import List, Optional, Callable, Any
from functools import wraps
from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import User, RoleType
from shared.repositories import UserRepository
from website.app.core.sessions import get_current_user_from_session


def get_current_user_with_roles(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user with their roles loaded"""
    user = get_current_user_from_session(request, db)
    if user:
        # Load roles for the user
        user.roles = UserRepository.get_user_roles(db, user.id)
    return user


def require_roles(required_roles: List[str]):
    """
    Decorator to require specific roles for access to a route.
    
    Args:
        required_roles: List of role names that are allowed access
    
    Usage:
        @require_roles(["administrator", "moderator"])
        async def admin_only_route():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and db from function parameters
            request = None
            db = None
            
            # Look for Request and Session in the function's arguments
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif isinstance(arg, Session):
                    db = arg
            
            # Look in kwargs as well
            if not request:
                request = kwargs.get('request')
            if not db:
                db = kwargs.get('db')
            
            if not request or not db:
                raise HTTPException(status_code=500, detail="Authentication dependencies not found")
            
            # Get current user
            user = get_current_user_from_session(request, db)
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check if user has any of the required roles
            user_has_required_role = False
            for role_name in required_roles:
                if UserRepository.user_has_role(db, user.id, role_name):
                    user_has_required_role = True
                    break
            
            if not user_has_required_role:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Access denied. Required roles: {', '.join(required_roles)}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_role(required_roles: List[str]):
    """
    Decorator that requires the user to have ANY of the specified roles.
    Alias for require_roles for clarity.
    """
    return require_roles(required_roles)


def require_all_roles(required_roles: List[str]):
    """
    Decorator that requires the user to have ALL of the specified roles.
    
    Args:
        required_roles: List of role names that the user must have ALL of
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and db from function parameters
            request = None
            db = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif isinstance(arg, Session):
                    db = arg
            
            if not request:
                request = kwargs.get('request')
            if not db:
                db = kwargs.get('db')
            
            if not request or not db:
                raise HTTPException(status_code=500, detail="Authentication dependencies not found")
            
            # Get current user
            user = get_current_user_from_session(request, db)
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check if user has ALL required roles
            for role_name in required_roles:
                if not UserRepository.user_has_role(db, user.id, role_name):
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Access denied. Required roles: {', '.join(required_roles)}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def check_user_has_role(user: User, role_name: str, db: Session) -> bool:
    """Check if a user has a specific role"""
    return UserRepository.user_has_role(db, user.id, role_name)


def check_user_has_any_role(user: User, role_names: List[str], db: Session) -> bool:
    """Check if a user has any of the specified roles"""
    for role_name in role_names:
        if UserRepository.user_has_role(db, user.id, role_name):
            return True
    return False


def check_user_has_all_roles(user: User, role_names: List[str], db: Session) -> bool:
    """Check if a user has all of the specified roles"""
    for role_name in role_names:
        if not UserRepository.user_has_role(db, user.id, role_name):
            return False
    return True


def is_admin(user: User, db: Session) -> bool:
    """Check if user is an administrator or superadmin"""
    return check_user_has_any_role(user, ["administrator", "superadmin"], db)


def is_moderator_or_above(user: User, db: Session) -> bool:
    """Check if user is moderator, administrator, or superadmin"""
    return check_user_has_any_role(user, ["moderator", "administrator", "superadmin"], db)


def is_helper_or_above(user: User, db: Session) -> bool:
    """Check if user is helper, moderator, administrator, or superadmin"""
    return check_user_has_any_role(user, ["helper", "moderator", "administrator", "superadmin"], db)


def get_user_role_names(user: User, db: Session) -> List[str]:
    """Get list of role names for a user"""
    roles = UserRepository.get_user_roles(db, user.id)
    return [role.name.value for role in roles]


def get_highest_role(user: User, db: Session) -> Optional[str]:
    """Get the highest role for a user based on hierarchy"""
    role_hierarchy = ["superadmin", "administrator", "moderator", "helper", "captain", "user"]
    user_roles = get_user_role_names(user, db)
    
    for role in role_hierarchy:
        if role in user_roles:
            return role
    
    return None