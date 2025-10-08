from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.api import api_router
from app.db.database import engine, Base

# Initialize database tables
# Comment this out if using Alembic for migrations
Base.metadata.create_all(bind=engine)

# Load settings
settings = get_settings()

# Create FastAPI application instance
app = FastAPI(
    title="Miss Pauling",
    description="A minimal FastAPI application with Steam and Discord authentication",
    version="0.1.0"
)

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routes
app.include_router(api_router)

@app.get("/", response_model=dict)
async def root():
    """Show login screen or automatically log in if already authenticated"""
    # Create login instructions with Discord as the only option
    login_url = f"{settings.realm}/auth/discord/login"
    return {"message": f"Please log in with Discord: {login_url}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)