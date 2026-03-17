"""
api/agent_routes.py

Agent perspective and messaging API endpoints.

Endpoints:
  GET  /api/agents/roles                  - List all agent roles
  GET  /api/agents/by_role/{role}         - Get agents of a specific role
  GET  /api/agents/{agent_id}/perspective - See the world through one agent's eyes
  GET  /api/agents/{agent_id}/messages    - Agent's message history
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.world_engine import get_engine

agent_router = APIRouter(prefix="/agents", tags=["agents"])


@agent_router.get("/roles")
def list_roles():
    """List all available agent roles with counts."""
    engine = get_engine()
    if engine._society is None:
        return {"roles": []}
    return {"roles": engine._society.get_all_roles()}


@agent_router.get("/by_role/{role}")
def get_agents_by_role(role: str):
    """Get all agents of a specific role type."""
    engine = get_engine()
    if engine.world is None:
        raise HTTPException(status_code=400, detail="World not initialized.")
    if engine._society is None:
        raise HTTPException(status_code=400, detail="Society not initialized.")

    agent_ids = engine._society.get_agents_by_role(role)
    if not agent_ids:
        return {"role": role, "agents": []}

    agents = []
    for aid in agent_ids:
        agent = engine._find_agent(aid)
        if agent:
            life = engine._society.lives.get(aid)
            agents.append({
                "agent_id": aid,
                "name": agent.name,
                "country": agent.country,
                "tier": agent.tier.value,
                "role": role,
                "financial_literacy": agent.financial_literacy,
                "beliefs": life.beliefs if life else {},
            })

    return {"role": role, "count": len(agents), "agents": agents}


@agent_router.get("/{agent_id}/perspective")
def get_agent_perspective(agent_id: str):
    """See the world through one agent's eyes."""
    engine = get_engine()
    if engine.world is None:
        raise HTTPException(status_code=400, detail="World not initialized.")
    if engine._society is None:
        raise HTTPException(status_code=400, detail="Society not initialized.")

    agent = engine._find_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    perspective = engine._society.get_perspective(agent_id, agent, engine.world)
    if not perspective:
        raise HTTPException(status_code=404, detail="No perspective data for this agent")

    return perspective


@agent_router.get("/{agent_id}/messages")
def get_agent_messages(agent_id: str, limit: int = Query(default=50, ge=1, le=200)):
    """Get message history for an agent."""
    engine = get_engine()
    if engine.world is None:
        raise HTTPException(status_code=400, detail="World not initialized.")
    if engine._society is None:
        raise HTTPException(status_code=400, detail="Society not initialized.")

    agent = engine._find_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    messages = engine._society.get_agent_messages(agent_id, limit=limit)
    return {"agent_id": agent_id, "name": agent.name, "messages": messages, "count": len(messages)}
