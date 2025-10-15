#!/usr/bin/env python3
"""
Admin script for managing users and roles in the Miss Pauling database.

Usage:
    python admin_roles.py list-users                    # List all users
    python admin_roles.py list-roles                    # List all available roles
    python admin_roles.py user-roles <user_id>          # Show roles for a user
    python admin_roles.py assign <user_id> <role>       # Assign role to user
    python admin_roles.py remove <user_id> <role>       # Remove role from user
    python admin_roles.py find-user <search_term>       # Find user by name/discord/steam
"""
import sys
import argparse
from pathlib import Path

# Add the root directory to sys.path
root_dir = str(Path(__file__).parent)
sys.path.append(root_dir)

from sqlalchemy.orm import sessionmaker
from shared.database import engine
from shared.models import User, Role, UserRole, RoleType
from shared.repositories import UserRepository


def list_users(db):
    """List all users in the database"""
    users = db.query(User).all()
    
    if not users:
        print("No users found in the database.")
        return
    
    print(f"Found {len(users)} users:")
    print("-" * 80)
    print(f"{'ID':<4} {'Name':<20} {'Discord ID':<20} {'Steam ID64':<20} {'Roles'}")
    print("-" * 80)
    
    for user in users:
        roles = UserRepository.get_user_roles(db, user.id)
        role_names = [role.name.value for role in roles]
        role_str = ", ".join(role_names) if role_names else "No roles"
        
        name = user.name or "N/A"
        discord = user.discord_id or "N/A"
        steam = user.steam_id64 or "N/A"
        
        print(f"{user.id:<4} {name:<20} {discord:<20} {steam:<20} {role_str}")


def list_roles(db):
    """List all available roles"""
    roles = UserRepository.get_all_roles(db)
    
    print(f"Available roles ({len(roles)}):")
    print("-" * 60)
    print(f"{'Role':<15} {'Description'}")
    print("-" * 60)
    
    for role in roles:
        print(f"{role.name.value:<15} {role.description}")


def show_user_roles(db, user_id):
    """Show roles for a specific user"""
    user = UserRepository.get_user_by_id(db, user_id)
    if not user:
        print(f"User with ID {user_id} not found.")
        return
    
    roles = UserRepository.get_user_roles(db, user_id)
    
    print(f"User: {user.name or 'N/A'} (ID: {user.id})")
    print(f"Discord: {user.discord_id or 'N/A'}")
    print(f"Steam: {user.steam_id64 or 'N/A'}")
    print(f"Roles ({len(roles)}):")
    
    if roles:
        for role in roles:
            print(f"  - {role.name.value}")
    else:
        print("  No roles assigned")


def assign_role(db, user_id, role_name):
    """Assign a role to a user"""
    user = UserRepository.get_user_by_id(db, user_id)
    if not user:
        print(f"User with ID {user_id} not found.")
        return
    
    # Validate role name
    try:
        RoleType(role_name)
    except ValueError:
        available_roles = [role.value for role in RoleType]
        print(f"Invalid role '{role_name}'. Available roles: {', '.join(available_roles)}")
        return
    
    # Check if user already has this role
    if UserRepository.user_has_role(db, user_id, role_name):
        print(f"User {user.name or user_id} already has the '{role_name}' role.")
        return
    
    # Assign the role
    success = UserRepository.assign_role(db, user_id, role_name)
    if success:
        print(f"✅ Successfully assigned '{role_name}' role to user {user.name or user_id}")
    else:
        print(f"❌ Failed to assign '{role_name}' role to user {user.name or user_id}")


def remove_role(db, user_id, role_name):
    """Remove a role from a user"""
    user = UserRepository.get_user_by_id(db, user_id)
    if not user:
        print(f"User with ID {user_id} not found.")
        return
    
    # Validate role name
    try:
        RoleType(role_name)
    except ValueError:
        available_roles = [role.value for role in RoleType]
        print(f"Invalid role '{role_name}'. Available roles: {', '.join(available_roles)}")
        return
    
    # Check if user has this role
    if not UserRepository.user_has_role(db, user_id, role_name):
        print(f"User {user.name or user_id} doesn't have the '{role_name}' role.")
        return
    
    # Remove the role
    success = UserRepository.remove_role(db, user_id, role_name)
    if success:
        print(f"✅ Successfully removed '{role_name}' role from user {user.name or user_id}")
    else:
        print(f"❌ Failed to remove '{role_name}' role from user {user.name or user_id}")


def find_user(db, search_term):
    """Find users by name, discord ID, or steam ID"""
    users = db.query(User).filter(
        (User.name.ilike(f"%{search_term}%")) |
        (User.discord_id.ilike(f"%{search_term}%")) |
        (User.steam_id64.ilike(f"%{search_term}%"))
    ).all()
    
    if not users:
        print(f"No users found matching '{search_term}'")
        return
    
    print(f"Found {len(users)} user(s) matching '{search_term}':")
    print("-" * 80)
    print(f"{'ID':<4} {'Name':<20} {'Discord ID':<20} {'Steam ID64':<20} {'Roles'}")
    print("-" * 80)
    
    for user in users:
        roles = UserRepository.get_user_roles(db, user.id)
        role_names = [role.name.value for role in roles]
        role_str = ", ".join(role_names) if role_names else "No roles"
        
        name = user.name or "N/A"
        discord = user.discord_id or "N/A"
        steam = user.steam_id64 or "N/A"
        
        print(f"{user.id:<4} {name:<20} {discord:<20} {steam:<20} {role_str}")


def main():
    parser = argparse.ArgumentParser(
        description="Admin tool for managing users and roles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python admin_roles.py list-users
  python admin_roles.py user-roles 1
  python admin_roles.py assign 1 administrator
  python admin_roles.py remove 1 moderator
  python admin_roles.py find-user "john"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List users command
    subparsers.add_parser('list-users', help='List all users')
    
    # List roles command
    subparsers.add_parser('list-roles', help='List all available roles')
    
    # User roles command
    user_roles_parser = subparsers.add_parser('user-roles', help='Show roles for a user')
    user_roles_parser.add_argument('user_id', type=int, help='User ID')
    
    # Assign role command
    assign_parser = subparsers.add_parser('assign', help='Assign role to user')
    assign_parser.add_argument('user_id', type=int, help='User ID')
    assign_parser.add_argument('role', help='Role name (e.g., administrator, moderator)')
    
    # Remove role command
    remove_parser = subparsers.add_parser('remove', help='Remove role from user')
    remove_parser.add_argument('user_id', type=int, help='User ID')
    remove_parser.add_argument('role', help='Role name (e.g., administrator, moderator)')
    
    # Find user command
    find_parser = subparsers.add_parser('find-user', help='Find user by name/discord/steam')
    find_parser.add_argument('search_term', help='Search term (name, discord ID, or steam ID)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create database session
    Session = sessionmaker(bind=engine)
    with Session() as db:
        try:
            if args.command == 'list-users':
                list_users(db)
            elif args.command == 'list-roles':
                list_roles(db)
            elif args.command == 'user-roles':
                show_user_roles(db, args.user_id)
            elif args.command == 'assign':
                assign_role(db, args.user_id, args.role)
            elif args.command == 'remove':
                remove_role(db, args.user_id, args.role)
            elif args.command == 'find-user':
                find_user(db, args.search_term)
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()