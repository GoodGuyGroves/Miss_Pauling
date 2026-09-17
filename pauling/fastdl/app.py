"""
FastDL sub-application.

Mounted inside the website process via Starlette host-based routing, so it is
served for the hosts listed in fastdl/settings.json (e.g. fastdl.pugs.tf) while
sharing the website's process, virtualenv, database and session cookies.
"""
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from urllib.parse import urlencode
import aiofiles

from pauling.fastdl.core.config import settings, FASTDL_DIR
from pauling.fastdl.core.mapcycle import mapcycle_manager
from pauling.fastdl.core.auth import get_current_user, require_auth, require_helper_or_above, AuthenticatedUser
from pauling.fastdl.core.tf2_versions import tf2_sort_key
from pauling.db.database import get_db
from pauling.db.repositories import UserRepository
from pauling.auth.sessions import create_session_cookie, clear_session_cookie

app = FastAPI(title="pugs.tf FastDL", docs_url=None, redoc_url=None, openapi_url=None)

MAX_FILE_SIZE = settings.max_map_file_size * 1024 * 1024

templates = Jinja2Templates(directory=str(FASTDL_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(FASTDL_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """Serve the HTML frontend"""
    return templates.TemplateResponse(request, "index.html", {"request": request, "user": user})

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
        
        maps.sort(key=lambda x: tf2_sort_key(x["name"]))
        return maps
    except HTTPException:
        raise
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
    return templates.TemplateResponse(request, "tf_index.html", {"request": request})

@app.get("/tf/cfg/", response_class=HTMLResponse)
async def browse_cfg(request: Request):
    files = [f"mapcycle_{name}.txt" for name in settings.mapcycles]
    return templates.TemplateResponse(request, "cfg_index.html", {"files": files})

@app.get("/tf/cfg/mapcycle_{name}.txt", response_class=PlainTextResponse)
async def serve_mapcycle(name: str):
    """Serve a mapcycle file for TF2 servers to download (e.g. on startup or via a cron job)"""
    if name not in settings.mapcycles:
        raise HTTPException(status_code=404, detail="Mapcycle not found")
    return PlainTextResponse(mapcycle_manager.render_mapcycle(name))

@app.get("/tf/maps/", response_class=HTMLResponse)
async def browse_maps(request: Request):
    try:
        maps_path = Path(settings.maps_dir)
        files = []
        for file_path in maps_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in settings.allowed_map_extensions:
                files.append(file_path.name)
        
        files.sort(key=tf2_sort_key)
        return templates.TemplateResponse(request, "maps_index.html", {"request": request, "files": files})
    except HTTPException:
        raise
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
    user: AuthenticatedUser = Depends(require_helper_or_above)
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/maps/{filename}")
async def delete_map(
    filename: str,
    user: AuthenticatedUser = Depends(require_helper_or_above)
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/login")
async def login_redirect(request: Request):
    """Redirect to main website for login, with return URL back to FastDL"""
    # Get the current URL to return to after login
    return_url = f"{request.base_url}login/callback"
    
    # Redirect to main website login with return parameter
    base_url = str(settings.website_base_url).rstrip('/')
    website_login_url = f"{base_url}/auth/redirect-login?{urlencode({'return_to': return_url})}"
    return RedirectResponse(url=website_login_url)

@app.get("/login/callback")
async def login_callback(request: Request, session_token: str = None):
    """
    Handle login callback from the main website.

    In production the session cookie is shared across subdomains via
    MISS_PAULING_COOKIE_DOMAIN, so nothing needs to be done here. In development
    (no shared cookie domain) the website passes the session token as a query
    parameter and it is set as a cookie on the FastDL host.
    """
    response = RedirectResponse(url="/")
    if session_token:
        create_session_cookie(response, session_token)
    return response

@app.api_route("/logout", methods=["GET", "POST"])
async def logout(request: Request, db: Session = Depends(get_db)):
    """Logout user by clearing session and redirecting back to FastDL"""
    # Get current session token
    session_token = request.cookies.get("session_token")
    if session_token:
        # Invalidate session in database (shared with main website)
        UserRepository.invalidate_session(db, session_token)

    # Clear session cookie and redirect back to FastDL
    response = RedirectResponse(url="/?success=Logged out successfully")
    clear_session_cookie(response)
    return response

