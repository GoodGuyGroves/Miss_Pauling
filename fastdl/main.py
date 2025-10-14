import sys
from pathlib import Path
# Add the repository root to Python path so we can import shared modules
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
from urllib.parse import urlencode
import aiofiles
from core.config import settings
from core.mapcycle import mapcycle_manager
from core.auth import get_current_user, require_auth, AuthenticatedUser
from shared.database import get_db
from shared.models import User, UserSession

app = FastAPI()

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

@app.middleware("http")
async def proxy_headers_middleware(request: Request, call_next):
    if request.headers.get("x-forwarded-proto") == "https":
        request.scope["scheme"] = "https"
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

print(settings)
for server in settings.servers:
    print(server.name, server.tf_dir)
print(f"Maps dir: {settings.maps_dir}")

MAX_FILE_SIZE = settings.max_map_file_size * 1024 * 1024

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """Serve the HTML frontend"""
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/maps")
async def list_maps():
    """List all maps in the maps folder"""
    try:
        maps = []
        maps_path = Path(settings.maps_dir)
        for file_path in maps_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in settings.allowed_map_extensions:
                stat = file_path.stat()
                maps.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "mapcycles": mapcycle_manager.get_map_mapcycle_status(file_path.name)
                })
        
        maps.sort(key=lambda x: x["modified"], reverse=True)
        return maps
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_map(file: UploadFile = File(...)):
    """Upload a new map file"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_map_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Only {', '.join(settings.allowed_map_extensions)} files are allowed."
        )
    
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB."
        )
    
    file_path = Path(settings.maps_dir) / file.filename
    
    if file_path.exists():
        return {
            "status": "skipped",
            "message": f"Map already exists",
            "filename": file.filename
        }
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(1024 * 1024):
                await f.write(chunk)
        
        return {
            "status": "success",
            "message": f"Uploaded successfully!",
            "filename": file.filename,
            "size": file_size
        }
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/tf/", response_class=HTMLResponse)
async def browse_tf(request: Request):
    return templates.TemplateResponse("tf_index.html", {"request": request})

@app.get("/tf/maps/", response_class=HTMLResponse)
async def browse_maps(request: Request):
    try:
        maps_path = Path(settings.maps_dir)
        files = []
        for file_path in maps_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in settings.allowed_map_extensions:
                files.append(file_path.name)
        
        files.sort()
        return templates.TemplateResponse("maps_index.html", {"request": request, "files": files})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tf/maps/{filename}")
async def serve_map(filename: str):
    file_path = Path(settings.maps_dir) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Map not found")
    
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Map not found")
    
    file_ext = file_path.suffix.lower()
    if file_ext not in settings.allowed_map_extensions:
        raise HTTPException(status_code=403, detail="File type not allowed")
    
    media_type = "application/octet-stream"
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

@app.post("/maps/{filename}/mapcycle")
async def toggle_map_mapcycle(
    filename: str, 
    name: str,
    user: AuthenticatedUser = Depends(require_auth)
):
    """Toggle a map's inclusion in a specific mapcycle (requires authentication)"""
    try:
        maps_path = Path(settings.maps_dir)
        file_path = maps_path / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Map not found")
        
        file_ext = file_path.suffix.lower()
        if file_ext not in settings.allowed_map_extensions:
            raise HTTPException(status_code=400, detail="Invalid map file")
        
        if name not in settings.mapcycles:
            raise HTTPException(status_code=400, detail=f"Unknown mapcycle: {name}")
        
        is_enabled = mapcycle_manager.toggle_map_in_mapcycle(filename, name)
        
        # Log the mapcycle activity
        action = "added to" if is_enabled else "removed from"
        print(f"MAPCYCLE TOGGLE: {filename} {action} {name} mapcycle by user {user.name} (ID: {user.user_id})")
        
        return {
            "status": "success",
            "filename": filename,
            "mapcycle": name,
            "in_mapcycle": is_enabled,
            "message": f"Map {'added to' if is_enabled else 'removed from'} {name} mapcycle"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/maps/{filename}")
async def delete_map(
    filename: str,
    user: AuthenticatedUser = Depends(require_auth)
):
    """Delete a map file (requires authentication)"""
    try:
        maps_path = Path(settings.maps_dir)
        file_path = maps_path / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Map not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")
        
        file_ext = file_path.suffix.lower()
        if file_ext not in settings.allowed_map_extensions:
            raise HTTPException(status_code=400, detail="Invalid map file")
        
        # Remove from all mapcycles first
        mapcycle_manager.remove_map_from_all_mapcycles(filename)
        
        # Delete the file
        file_path.unlink()
        
        # Log the deletion activity
        print(f"MAP DELETED: {filename} by user {user.name} (ID: {user.user_id})")
        
        return {
            "status": "success",
            "filename": filename,
            "message": f"Map {filename} deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/login")
async def login_redirect(request: Request):
    """Redirect to main website for login, with return URL back to FastDL"""
    # Get the current URL to return to after login
    return_url = str(request.url_for("login_callback"))
    
    # Redirect to main website login with return parameter
    base_url = str(settings.website_base_url).rstrip('/')
    website_login_url = f"{base_url}/auth/redirect-login?{urlencode({'return_to': return_url})}"
    return RedirectResponse(url=website_login_url)

# TODO: Roll back this development vs production hack once pugs.lumabyte.io and fastdl.pugs.lumabyte.io subdomains have propagated
# Note to self: make sure newt is forwarding the above subdomains to both the website and fastdl running processes locally
@app.get("/login/callback")
async def login_callback(request: Request, session_token: str = None):
    """Handle login callback from main website"""
    # For development: website can pass session token as query param
    # For production: this should work via shared domain cookies
    if session_token:
        # Set the session cookie on FastDL's domain
        response = RedirectResponse(url="/")
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=False,  # Development
            samesite="lax",
            max_age=24 * 7 * 3600  # 1 week
        )
        return response
    else:
        # Normal redirect without cookie
        return RedirectResponse(url="/")

@app.get("/logout")
async def logout_redirect(request: Request):
    """Redirect to main website for logout"""
    # Redirect to main website logout
    base_url = str(settings.website_base_url).rstrip('/')
    website_logout_url = f"{base_url}/auth/logout"
    return RedirectResponse(url=website_logout_url)

