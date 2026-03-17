from fastapi import APIRouter
from app.api.routes import router
from app.api.banking_routes import banking_router

__all__ = ["router", "banking_router"]
