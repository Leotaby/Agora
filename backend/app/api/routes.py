"""
NEXUS = HumanTwin
api/routes.py

FastAPI endpoints — the HTTP interface used by the Vue frontend.
Mirrors MiroFish's api/ structure but domain-specific.

Endpoints:
  POST /api/simulate          — start a new simulation
  GET  /api/simulate/{id}     — poll simulation status + results
  GET  /api/simulate/{id}/stream — SSE stream of round results (live)
  GET  /api/agents/population — preview the agent population
  GET  /api/shocks/presets    — list available preset shocks
  POST /api/shocks/custom     — define a custom shock
  GET  /api/health            — health check
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.models.shock import (
    MacroShock, ShockType, ShockSource,
    fed_rate_hike_75bps, ecb_surprise_cut_50bps,
)
from app.models.simulation import Simulation, SimulationStatus
from app.services.agent_factory import AgentFactory
from app.services.simulation_runner import SimulationRunner

router = APIRouter()

# In-memory store for simulation state (Phase 0; replace with DB in Phase 1)
_simulations: dict[str, Simulation] = {}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SimulationRequest(BaseModel):
    shock_preset: Optional[str] = Field(
        None,
        description="Name of a preset shock: 'fed_hike_75', 'ecb_cut_50'"
    )
    shock_custom: Optional[dict] = Field(
        None,
        description="Custom shock definition (if shock_preset is null)"
    )
    n_households: int = Field(default=100, ge=10, le=10_000)
    n_professional_retail: int = Field(default=20, ge=0, le=500)
    n_ordinary_retail: int = Field(default=40, ge=0, le=1_000)
    n_rounds: int = Field(default=5, ge=1, le=20)
    use_llm: bool = Field(default=False, description="Use real LLM calls (requires API key)")
    seed: int = Field(default=42)


class SimulationStatusResponse(BaseModel):
    simulation_id: str
    status: str
    num_agents: int
    num_rounds: int
    rounds_completed: int
    shock_headline: str
    created_at: str


class RoundSummaryResponse(BaseModel):
    round_num: int
    sentiment_by_tier: dict[str, float]
    net_usd_flow: float
    exchange_rate_delta: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def health_check():
    return {"status": "ok", "project": "NEXUS = HumanTwin", "version": "0.1.0"}


@router.get("/shocks/presets")
def list_preset_shocks():
    """List all available preset macro shocks."""
    return {
        "presets": [
            {
                "id": "fed_hike_75",
                "headline": "Fed raises rates +75bps",
                "type": ShockType.RATE_HIKE,
                "source": ShockSource.FED,
            },
            {
                "id": "ecb_cut_50",
                "headline": "ECB surprise cut -50bps",
                "type": ShockType.RATE_CUT,
                "source": ShockSource.ECB,
            },
        ]
    }


@router.get("/agents/population")
def preview_population(
    n_households: int = 50,
    seed: int = 42,
):
    """Build and summarize an agent population without running a simulation."""
    factory = AgentFactory(seed=seed)
    agents = factory.build(
        n_households=n_households,
        n_professional_retail=10,
        n_ordinary_retail=20,
    )
    summary = factory.summary(agents)

    # Include sample agents from each tier for the frontend preview
    from collections import defaultdict
    by_tier: dict[str, list] = defaultdict(list)
    for a in agents:
        if len(by_tier[a.tier.value]) < 2:
            by_tier[a.tier.value].append({
                "name": a.name,
                "country": a.country,
                "financial_literacy": a.financial_literacy,
                "risk_tolerance": a.risk_tolerance.value,
                "information_speed": a.information_speed,
                "usd_exposure": a.usd_exposure,
            })

    return {**summary, "sample_agents_by_tier": dict(by_tier)}


@router.post("/simulate")
async def start_simulation(
    request: SimulationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a new simulation. Returns immediately with simulation_id.
    Use GET /simulate/{id} to poll for results.
    Mirrors MiroFish's project creation + task queue pattern.
    """
    # Build shock
    if request.shock_preset == "fed_hike_75":
        shock = fed_rate_hike_75bps()
    elif request.shock_preset == "ecb_cut_50":
        shock = ecb_surprise_cut_50bps()
    elif request.shock_custom:
        try:
            shock = MacroShock(**request.shock_custom)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid shock definition: {e}")
    else:
        shock = fed_rate_hike_75bps()  # default

    # Build population
    factory = AgentFactory(seed=request.seed)
    agents = factory.build(
        n_households=request.n_households,
        n_professional_retail=request.n_professional_retail,
        n_ordinary_retail=request.n_ordinary_retail,
    )

    # Create simulation object
    simulation = Simulation(
        agents=agents,
        shocks=[shock],
        num_rounds=request.n_rounds,
    )
    _simulations[simulation.simulation_id] = simulation

    # Run in background
    runner = SimulationRunner(use_llm=request.use_llm)
    background_tasks.add_task(_run_simulation, runner, simulation)

    return {
        "simulation_id": simulation.simulation_id,
        "status": "pending",
        "num_agents": len(agents),
        "message": f"Simulation started. Poll GET /api/simulate/{simulation.simulation_id} for results.",
    }


@router.get("/simulate/{simulation_id}")
def get_simulation(simulation_id: str):
    """Poll simulation status and results."""
    sim = _simulations.get(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    result = sim.summary()
    result["shock_headline"] = sim.shocks[0].headline if sim.shocks else ""

    if sim.round_results:
        result["rounds"] = [
            {
                "round_num": r.round_num,
                "sentiment_by_tier": r.avg_sentiment_by_tier,
                "net_usd_flow": round(r.net_usd_flow, 4),
                "exchange_rate_delta": round(r.exchange_rate_delta, 4),
            }
            for r in sim.round_results
        ]

    return result


@router.get("/simulate/{simulation_id}/stream")
async def stream_simulation(simulation_id: str):
    """
    SSE endpoint — streams round results as they complete.
    The Vue frontend subscribes to this for live updates.
    Mirrors MiroFish's real-time simulation display.
    """
    sim = _simulations.get(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    async def event_generator():
        last_round = -1
        while True:
            # Emit any new completed rounds
            for result in sim.round_results:
                if result.round_num > last_round:
                    data = {
                        "round_num": result.round_num,
                        "sentiment_by_tier": result.avg_sentiment_by_tier,
                        "net_usd_flow": round(result.net_usd_flow, 4),
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_round = result.round_num

            if sim.status == SimulationStatus.COMPLETED:
                yield f"data: {json.dumps({'event': 'complete', 'simulation_id': simulation_id})}\n\n"
                break
            elif sim.status == SimulationStatus.FAILED:
                yield f"data: {json.dumps({'event': 'error'})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

async def _run_simulation(runner: SimulationRunner, simulation: Simulation) -> None:
    try:
        await runner.run(simulation, verbose=False)
    except Exception as e:
        simulation.status = SimulationStatus.FAILED
        simulation.final_report = str(e)
