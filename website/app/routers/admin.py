"""
Admin dashboard routes for user and role management.
"""
from typing import Annotated, List
from fastapi import APIRouter, Request, Depends, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import asyncio
import subprocess
import json

from shared.database import get_db
from shared.models import User, Role
from shared.repositories import UserRepository
from website.app.core.sessions import get_current_user_from_session, generate_csrf_token, set_csrf_cookie, validate_csrf_token
from website.app.core.roles import require_roles, get_highest_role, get_user_role_names
from website.app.core.config import settings
from website.app.models.admin import (
    AdminUser, AdminUserRole, AdminUsersPageContext, 
    RoleAssignmentRequest, RoleAssignmentResponse,
    get_role_hierarchy, can_assign_role, get_assignable_roles
)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)]
):
    """Admin dashboard home page"""
    user = get_current_user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check if user has admin privileges (moderator or above)
    user_roles = get_user_role_names(user, db)
    highest_role = get_highest_role(user, db)
    
    if not highest_role or get_role_hierarchy(highest_role) > 2:  # Only moderator+ can access
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    csrf_token = generate_csrf_token()
    is_admin = True  # User already verified as admin above
    
    context = {
        "request": request,
        "user": user,
        "csrf_token": csrf_token,
        "page_title": "Admin Dashboard",
        "user_roles": user_roles,
        "highest_role": highest_role,
        "is_admin": is_admin
    }
    
    response = templates.TemplateResponse("admin/dashboard.html", context)
    set_csrf_cookie(response, csrf_token)
    return response


@router.get("/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)]
):
    """Admin users management page"""
    user = get_current_user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check admin privileges
    user_roles = get_user_role_names(user, db)
    highest_role = get_highest_role(user, db)
    
    if not highest_role or get_role_hierarchy(highest_role) > 2:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    is_admin = True  # User already verified as admin above
    
    # Get all users with their roles
    all_users = db.query(User).all()
    admin_users = []
    
    for db_user in all_users:
        user_roles_db = UserRepository.get_user_roles(db, db_user.id)
        admin_roles = [
            AdminUserRole(
                id=role.id,
                name=role.name.value,
                description=role.description
            ) for role in user_roles_db
        ]
        
        admin_user = AdminUser(
            id=db_user.id,
            name=db_user.name,
            discord_id=db_user.discord_id,
            steam_id64=db_user.steam_id64,
            steam_id=db_user.steam_id,
            steam_id3=db_user.steam_id3,
            avatar_url=db_user.avatar_url,
            created_at=db_user.created_at,
            last_login=db_user.last_login,
            roles=admin_roles
        )
        admin_users.append(admin_user)
    
    # Get all available roles
    all_roles_db = UserRepository.get_all_roles(db)
    available_roles = [
        AdminUserRole(
            id=role.id,
            name=role.name.value,
            description=role.description
        ) for role in all_roles_db
    ]
    
    # Get assignable roles for current user
    assignable_roles = get_assignable_roles(highest_role, available_roles)
    
    csrf_token = generate_csrf_token()
    current_user_role_hierarchy = get_role_hierarchy(highest_role)
    
    context_data = AdminUsersPageContext(
        user=user,
        csrf_token=csrf_token,
        page_title="User Management",
        active_section="users",
        users=admin_users,
        available_roles=assignable_roles,  # Only show assignable roles
        current_user_roles=get_user_role_names(user, db),
        current_user_role_hierarchy=current_user_role_hierarchy
    )
    
    # Create template context with request included
    template_context = {
        "request": request,
        "is_admin": is_admin,
        **context_data.model_dump()
    }
    
    response = templates.TemplateResponse("admin/users.html", template_context)
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/users/assign-role")
async def assign_role_to_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_id: int = Form(...),
    role_name: str = Form(...),
    action: str = Form(...),
    csrf_token: str = Form(...)
):
    """Assign or remove a role from a user"""
    # Verify CSRF token  
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    
    current_user = get_current_user_from_session(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check admin privileges
    current_user_highest_role = get_highest_role(current_user, db)
    if not current_user_highest_role or get_role_hierarchy(current_user_highest_role) > 2:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Validate target user exists
    target_user = UserRepository.get_user_by_id(db, user_id)
    if not target_user:
        return JSONResponse(
            content={"success": False, "message": "User not found"},
            status_code=404
        )
    
    # Check if current user can assign this role
    if not can_assign_role(current_user_highest_role, role_name):
        return JSONResponse(
            content={
                "success": False, 
                "message": f"You cannot assign the '{role_name}' role. You can only assign roles lower than your own."
            },
            status_code=403
        )
    
    # Prevent users from modifying their own roles
    if current_user.id == user_id:
        return JSONResponse(
            content={
                "success": False,
                "message": "You cannot modify your own roles."
            },
            status_code=403
        )
    
    # Perform the action
    success = False
    message = ""
    
    if action == "assign":
        if UserRepository.user_has_role(db, user_id, role_name):
            message = f"User already has the '{role_name}' role"
        else:
            success = UserRepository.assign_role(db, user_id, role_name, current_user.id)
            if success:
                # Audit log
                print(f"ROLE ASSIGNED: User {current_user.name} (ID: {current_user.id}) assigned '{role_name}' role to user {target_user.name} (ID: {user_id})")
                message = f"Successfully assigned '{role_name}' role"
            else:
                message = f"Failed to assign '{role_name}' role"
    
    elif action == "remove":
        if not UserRepository.user_has_role(db, user_id, role_name):
            message = f"User doesn't have the '{role_name}' role"
        else:
            success = UserRepository.remove_role(db, user_id, role_name)
            if success:
                # Audit log
                print(f"ROLE REMOVED: User {current_user.name} (ID: {current_user.id}) removed '{role_name}' role from user {target_user.name} (ID: {user_id})")
                message = f"Successfully removed '{role_name}' role"
            else:
                message = f"Failed to remove '{role_name}' role"
    
    else:
        return JSONResponse(
            content={"success": False, "message": "Invalid action. Use 'assign' or 'remove'"},
            status_code=400
        )
    
    response_data = RoleAssignmentResponse(
        success=success,
        message=message,
        user_id=user_id,
        role_name=role_name,
        action=action
    )
    
    return JSONResponse(content=response_data.model_dump())


@router.get("/users/data")
async def get_users_data(
    request: Request,
    db: Annotated[Session, Depends(get_db)]
):
    """API endpoint to get users data for AJAX updates"""
    current_user = get_current_user_from_session(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check admin privileges
    highest_role = get_highest_role(current_user, db)
    if not highest_role or get_role_hierarchy(highest_role) > 2:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Get all users with roles
    all_users = db.query(User).all()
    users_data = []
    
    for db_user in all_users:
        user_roles_db = UserRepository.get_user_roles(db, db_user.id)
        role_names = [role.name.value for role in user_roles_db]
        
        users_data.append({
            "id": db_user.id,
            "name": db_user.name,
            "discord_id": db_user.discord_id,
            "steam_id64": db_user.steam_id64,
            "roles": role_names
        })
    
    return JSONResponse(content={"users": users_data})


@router.get("/logs", response_class=HTMLResponse)
async def admin_logs_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)]
):
    """Admin server logs page"""
    user = get_current_user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check admin privileges
    user_roles = get_user_role_names(user, db)
    highest_role = get_highest_role(user, db)
    
    if not highest_role or get_role_hierarchy(highest_role) > 2:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    is_admin = True  # User already verified as admin above
    
    # Get systemd services from settings
    systemd_services = getattr(settings, 'SYSTEMD_SERVICES', {})
    
    csrf_token = generate_csrf_token()
    
    context = {
        "request": request,
        "user": user,
        "csrf_token": csrf_token,
        "page_title": "Server Logs",
        "user_roles": user_roles,
        "highest_role": highest_role,
        "systemd_services": systemd_services,
        "is_admin": is_admin
    }
    
    response = templates.TemplateResponse("admin/logs.html", context)
    set_csrf_cookie(response, csrf_token)
    return response


@router.websocket("/logs/stream/{service_name}")
async def logs_websocket(websocket: WebSocket, service_name: str):
    """WebSocket endpoint for streaming systemd logs"""
    await websocket.accept()
    
    # Get systemd services from settings
    systemd_services = getattr(settings, 'SYSTEMD_SERVICES', {})
    
    if service_name not in systemd_services:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Service '{service_name}' not found"
        }))
        await websocket.close()
        return
    
    service_config = systemd_services[service_name]
    journalctl_args = service_config.get('journalctl_args', [])
    
    # Build journalctl command
    cmd = ['journalctl'] + journalctl_args + ['-f', '--output=json']
    
    try:
        # Start journalctl process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Send initial success message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "service": service_name,
            "display_name": service_config.get('display_name', service_name)
        }))
        
        # Stream logs
        while True:
            try:
                # Check if websocket is still connected
                await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                # If we receive anything, client is still connected but we ignore the message
            except asyncio.TimeoutError:
                # Normal case - no message received, continue
                pass
            except WebSocketDisconnect:
                # Client disconnected
                break
            
            # Read line from journalctl
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=0.1)
                if not line:
                    break
                
                line_str = line.decode('utf-8').strip()
                if line_str:
                    try:
                        # Parse JSON log entry
                        log_entry = json.loads(line_str)
                        await websocket.send_text(json.dumps({
                            "type": "log",
                            "data": log_entry
                        }))
                    except json.JSONDecodeError:
                        # Send raw line if not valid JSON
                        await websocket.send_text(json.dumps({
                            "type": "log",
                            "data": {"MESSAGE": line_str}
                        }))
            except asyncio.TimeoutError:
                # No new log line, continue
                continue
                
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error", 
            "message": f"Error streaming logs: {str(e)}"
        }))
    finally:
        # Clean up process
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
        
        try:
            await websocket.close()
        except:
            pass


@router.post("/logs/restart/{service_name}")
async def restart_service(
    service_name: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)]
):
    """Restart a systemd service"""
    user = get_current_user_from_session(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check admin privileges
    highest_role = get_highest_role(user, db)
    if not highest_role or get_role_hierarchy(highest_role) > 2:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Get systemd services from settings
    systemd_services = getattr(settings, 'SYSTEMD_SERVICES', {})
    
    if service_name not in systemd_services:
        return JSONResponse(
            content={"success": False, "message": f"Service '{service_name}' not found"},
            status_code=404
        )
    
    service_config = systemd_services[service_name]
    journalctl_args = service_config.get('journalctl_args', [])
    
    # Extract service name from journalctl args (remove --user, -u flags)
    systemctl_service = None
    for i, arg in enumerate(journalctl_args):
        if arg == '-u' and i + 1 < len(journalctl_args):
            systemctl_service = journalctl_args[i + 1]
            break
    
    if not systemctl_service:
        return JSONResponse(
            content={"success": False, "message": "Could not determine systemctl service name"},
            status_code=400
        )
    
    # Build systemctl restart command
    cmd = ['systemctl']
    
    # Add --user flag if present in journalctl args
    if '--user' in journalctl_args:
        cmd.append('--user')
    
    cmd.extend(['restart', systemctl_service])
    
    try:
        # Execute systemctl restart command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Log the restart action
            print(f"SERVICE RESTART: User {user.name} (ID: {user.id}) restarted service '{systemctl_service}'")
            return JSONResponse(content={
                "success": True, 
                "message": f"Service '{systemctl_service}' restarted successfully"
            })
        else:
            error_msg = result.stderr.strip() or "Unknown error occurred"
            print(f"SERVICE RESTART FAILED: User {user.name} (ID: {user.id}) failed to restart '{systemctl_service}': {error_msg}")
            return JSONResponse(
                content={"success": False, "message": f"Failed to restart service: {error_msg}"},
                status_code=500
            )
            
    except subprocess.TimeoutExpired:
        return JSONResponse(
            content={"success": False, "message": "Service restart timed out"},
            status_code=500
        )
    except Exception as e:
        print(f"SERVICE RESTART ERROR: User {user.name} (ID: {user.id}) encountered error restarting '{systemctl_service}': {str(e)}")
        return JSONResponse(
            content={"success": False, "message": f"Error restarting service: {str(e)}"},
            status_code=500
        )