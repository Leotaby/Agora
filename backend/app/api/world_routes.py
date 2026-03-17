"""
api/world_routes.py

Living world API endpoints.

Endpoints:
  POST /api/world/init                      - Initialize/reset world
  GET  /api/world/state                     - Full world snapshot
  POST /api/world/tick                      - Advance one tick manually
  POST /api/world/start                     - Start autonomous ticking
  POST /api/world/stop                      - Stop autonomous ticking
  POST /api/world/agent/{agent_id}/intervene - Human injects decision
  POST /api/world/shock/inject              - Manually inject a MacroShock
  GET  /api/world/events/stream             - SSE event stream (push-based)
  GET  /api/world/events/log                - Historical events
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models.shock import MacroShock
from app.models.world_event import HumanIntervention
from app.services.world_engine import get_engine
from app.api.routes import SHOCK_FACTORIES

world_router = APIRouter(prefix="/world", tags=["world"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class WorldInitRequest(BaseModel):
    seed: int = Field(default=42)
    n_households_per_country: int = Field(default=50, ge=0, le=500)
    use_llm: bool = Field(default=False)


class WorldStartRequest(BaseModel):
    tick_interval_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    days_per_tick: int = Field(default=1, ge=1, le=30)


class InterventionRequest(BaseModel):
    action: str = Field(..., min_length=1, description="Description of the action")
    usd_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    eur_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    equity_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    crypto_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    reasoning: str = Field(default="Human override")


class ShockInjectRequest(BaseModel):
    shock_preset: Optional[str] = Field(None, description="Preset shock id from SHOCK_FACTORIES")
    shock_custom: Optional[dict] = Field(None, description="Custom MacroShock kwargs")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@world_router.post("/init")
async def init_world(request: WorldInitRequest):
    """Initialize or reset the world. Stops ticking if running."""
    engine = get_engine()

    # Stop if running
    if engine._running:
        await engine.stop()

    world = engine.initialize(
        seed=request.seed,
        n_households_per_country=request.n_households_per_country,
        use_llm=request.use_llm,
    )
    return {
        "status": "initialized",
        "tick": world.tick,
        "date": str(world.simulation_date),
        "countries": world.num_countries,
        "agents": world.total_agents,
    }


@world_router.get("/state")
def get_world_state():
    """Full world snapshot + engine status."""
    engine = get_engine()
    return engine.get_state()


@world_router.post("/tick")
async def manual_tick():
    """Advance one tick manually. Fails if auto-running."""
    engine = get_engine()
    try:
        events = await engine.manual_tick()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "tick": engine.world.tick,
        "date": str(engine.world.simulation_date),
        "events": len(events),
        "event_summaries": [
            {"type": e.event_type.value, "severity": e.severity.value, "headline": e.headline}
            for e in events
            if e.event_type not in (EventType.TICK_START, EventType.TICK_END)
        ],
    }


@world_router.post("/start")
async def start_ticking(request: WorldStartRequest):
    """Start autonomous ticking."""
    engine = get_engine()
    if engine.world is None:
        raise HTTPException(status_code=400, detail="World not initialized. POST /api/world/init first.")

    await engine.start(
        tick_interval=request.tick_interval_seconds,
        days_per_tick=request.days_per_tick,
    )
    return {
        "status": "running",
        "tick_interval_seconds": request.tick_interval_seconds,
        "days_per_tick": request.days_per_tick,
    }


@world_router.post("/stop")
async def stop_ticking():
    """Stop autonomous ticking."""
    engine = get_engine()
    await engine.stop()
    return {
        "status": "stopped",
        "tick": engine.world.tick if engine.world else 0,
    }


@world_router.post("/agent/{agent_id}/intervene")
async def intervene_agent(agent_id: str, request: InterventionRequest):
    """Human injects a decision for a specific agent."""
    engine = get_engine()
    if engine.world is None:
        raise HTTPException(status_code=400, detail="World not initialized.")

    # Verify agent exists
    agent = engine._find_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    intervention = HumanIntervention(
        agent_id=agent_id,
        action=request.action,
        usd_delta=request.usd_delta,
        eur_delta=request.eur_delta,
        equity_delta=request.equity_delta,
        crypto_delta=request.crypto_delta,
        reasoning=request.reasoning,
    )

    event = await engine.inject_intervention(agent_id, intervention)
    return {
        "status": "queued",
        "event_id": event.event_id,
        "agent": {"name": agent.name, "tier": agent.tier.value, "country": agent.country},
    }


@world_router.post("/shock/inject")
async def inject_shock(request: ShockInjectRequest):
    """Manually inject a MacroShock into the world."""
    engine = get_engine()
    if engine.world is None:
        raise HTTPException(status_code=400, detail="World not initialized.")

    if request.shock_preset:
        factory_fn = SHOCK_FACTORIES.get(request.shock_preset)
        if not factory_fn:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown preset: {request.shock_preset}. Available: {list(SHOCK_FACTORIES.keys())}",
            )
        shock = factory_fn()
    elif request.shock_custom:
        try:
            shock = MacroShock(**request.shock_custom)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid shock definition: {e}")
    else:
        raise HTTPException(status_code=422, detail="Provide shock_preset or shock_custom")

    engine.world.inject_shock(shock)
    return {
        "status": "injected",
        "shock_id": shock.shock_id,
        "headline": shock.headline,
        "will_process_at_tick": engine.world.tick + 1,
    }


@world_router.get("/events/stream")
async def stream_events():
    """SSE stream of world events (push-based via asyncio.Queue)."""
    engine = get_engine()
    queue = engine.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event.to_sse_dict())}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'event': 'keepalive'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            engine.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@world_router.get("/events/log")
def get_event_log(since_tick: int = 0, limit: int = 100):
    """Return historical events."""
    engine = get_engine()
    events = engine.get_event_log(since_tick=since_tick, limit=limit)
    return {
        "events": [e.to_sse_dict() for e in events],
        "count": len(events),
        "total_logged": len(engine._event_log),
    }


# Need this import for the tick endpoint filter
from app.models.world_event import EventType
