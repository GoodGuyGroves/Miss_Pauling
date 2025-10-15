"""
Pydantic models for admin dashboard functionality.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from shared.models import RoleType


class AdminUserRole(BaseModel):
    """Role information for admin user display"""
    id: int
    name: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True


class AdminUser(BaseModel):
    """User information for admin dashboard"""
    id: int
    name: Optional[str] = None
    discord_id: Optional[str] = None
    steam_id64: Optional[str] = None
    steam_id: Optional[str] = None
    steam_id3: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: datetime
    roles: List[AdminUserRole] = []
    
    class Config:
        from_attributes = True


class AdminUsersResponse(BaseModel):
    """Response model for admin users list"""
    users: List[AdminUser]
    total_count: int
    available_roles: List[AdminUserRole]
    current_user_roles: List[str]  # Role names of the current admin user
    current_user_role_hierarchy: int  # Hierarchy level of current user's highest role


class RoleAssignmentRequest(BaseModel):
    """Request model for role assignment/removal"""
    user_id: int = Field(..., description="ID of the user to modify")
    role_name: str = Field(..., description="Name of the role to assign/remove")
    action: str = Field(..., description="Either 'assign' or 'remove'")


class RoleAssignmentResponse(BaseModel):
    """Response model for role assignment operations"""
    success: bool
    message: str
    user_id: int
    role_name: str
    action: str


class AdminDashboardContext(BaseModel):
    """Context for admin dashboard template"""
    user: Optional[Any] = None  # Current user info
    csrf_token: str
    page_title: str = "Admin Dashboard"
    active_section: str = "users"


class AdminUsersPageContext(AdminDashboardContext):
    """Context for admin users page template"""
    users: List[AdminUser]
    available_roles: List[AdminUserRole]
    current_user_roles: List[str]
    current_user_role_hierarchy: int
    can_assign_roles: bool = False
    
    def __init__(self, **data):
        super().__init__(**data)
        # User can assign roles if they have moderator+ privileges
        self.can_assign_roles = self.current_user_role_hierarchy <= 2  # moderator or above


def get_role_hierarchy(role_name: str) -> int:
    """
    Get hierarchy level for a role (lower number = higher privilege).
    Returns 999 for unknown roles.
    """
    hierarchy = {
        "superadmin": 0,
        "administrator": 1,
        "moderator": 2,
        "helper": 3,
        "captain": 4,
        "user": 5
    }
    return hierarchy.get(role_name.lower(), 999)


def can_assign_role(assigner_highest_role: str, target_role: str) -> bool:
    """
    Check if a user can assign a specific role based on hierarchy.
    Users can only assign roles that are lower in hierarchy than their own highest role.
    """
    assigner_level = get_role_hierarchy(assigner_highest_role)
    target_level = get_role_hierarchy(target_role)
    
    # Can assign if target role is lower in hierarchy (higher number)
    return target_level > assigner_level


def get_assignable_roles(user_highest_role: str, all_roles: List[AdminUserRole]) -> List[AdminUserRole]:
    """
    Get list of roles that a user can assign to others.
    """
    assignable = []
    user_level = get_role_hierarchy(user_highest_role)
    
    for role in all_roles:
        role_level = get_role_hierarchy(role.name)
        if role_level > user_level:  # Can assign roles lower in hierarchy
            assignable.append(role)
    
    return assignable