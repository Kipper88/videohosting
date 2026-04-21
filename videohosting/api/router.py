from fastapi import APIRouter

from .routes import auth, home, profiles, videos

api_router = APIRouter()
api_router.include_router(home.router)
api_router.include_router(videos.router)
api_router.include_router(profiles.router)
api_router.include_router(auth.router)
