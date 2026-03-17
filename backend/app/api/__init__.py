from fastapi import APIRouter
from app.api.routes import router
from app.api.world_routes import world_router
from app.api.agent_routes import agent_router
from app.api.intervention_routes import intervention_router

__all__ = ["router", "world_router", "agent_router", "intervention_router"]
