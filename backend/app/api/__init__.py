from fastapi import APIRouter
from app.api.routes import router
from app.api.world_routes import world_router

__all__ = ["router", "world_router"]
