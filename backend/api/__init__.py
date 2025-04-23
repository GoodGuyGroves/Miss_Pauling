from fastapi import APIRouter
from app.api.auth import router as auth_router

# Main API router that includes all sub-routers
api_router = APIRouter()

# Include all routers
api_router.include_router(auth_router)

# Add more routers here as needed
# api_router.include_router(users_router)
# api_router.include_router(other_router)