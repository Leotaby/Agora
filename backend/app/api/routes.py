"""
api/routes.py

FastAPI endpoints - the HTTP interface used by the Vue frontend.

Endpoints:
  POST /api/simulate          - start a new simulation
  GET  /api/simulate/{id}     - poll simulation status + results
  GET  /api/simulate/{id}/stream - SSE stream of round results (live)
  GET  /api/agents/population - preview the agent population
  GET  /api/shocks/presets    - list available preset shocks
  GET  /api/world/graph       - world entity graph for D3
  GET  /api/health            - health check
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
    shock_russia_new_sanctions, shock_opec_cut,
    shock_nk_cyber_attack, shock_argentina_default,
)
from app.models.simulation import Simulation, SimulationStatus
from app.services.agent_factory import AgentFactory
from app.services.simulation_runner import SimulationRunner

router = APIRouter()

# In-memory caches
_simulations: dict[str, Simulation] = {}
_cached_world_graph: dict | None = None

# Shock factory lookup
SHOCK_FACTORIES = {
    "fed_hike_75":      fed_rate_hike_75bps,
    "ecb_cut_50":       ecb_surprise_cut_50bps,
    "russia_sanction":  shock_russia_new_sanctions,
    "nk_cyber":         shock_nk_cyber_attack,
    "oil_cut":          shock_opec_cut,
    "argentina_default": shock_argentina_default,
}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SimulationRequest(BaseModel):
    shock_preset: Optional[str] = Field(None, description="Preset shock id")
    shock_custom: Optional[dict] = Field(None, description="Custom shock definition")
    n_households: int = Field(default=100, ge=10, le=10_000)
    n_professional_retail: int = Field(default=20, ge=0, le=500)
    n_ordinary_retail: int = Field(default=40, ge=0, le=1_000)
    n_rounds: int = Field(default=5, ge=1, le=20)
    use_llm: bool = Field(default=False, description="Use real LLM calls")
    seed: int = Field(default=42)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def health_check():
    return {"status": "ok", "project": "NEXUS", "version": "0.1.0"}


@router.get("/world/graph")
def get_world_graph():
    """Return the world entity graph for D3 visualization."""
    global _cached_world_graph
    if _cached_world_graph is None:
        from app.services.world_factory import WorldFactory
        from app.utils.world_graph import world_to_graph
        factory = WorldFactory(seed=42)
        world = factory.build(n_households_per_major_country=0, verbose=False)
        _cached_world_graph = world_to_graph(world)
    return _cached_world_graph


@router.get("/shocks/presets")
def list_preset_shocks():
    """List all available preset macro shocks."""
    return {
        "presets": [
            {"id": "fed_hike_75",      "headline": "Fed raises rates +75bps",              "type": "rate_hike",        "source": "Federal Reserve"},
            {"id": "ecb_cut_50",       "headline": "ECB surprise cut -50bps",              "type": "rate_cut",         "source": "ECB"},
            {"id": "russia_sanction",  "headline": "USA + EU expand Russia sanctions",     "type": "sanctions",        "source": "Geopolitical"},
            {"id": "nk_cyber",         "headline": "Lazarus Group cyberattack on banks",   "type": "liquidity_crisis", "source": "Market Event"},
            {"id": "oil_cut",          "headline": "OPEC+ surprise 10% production cut",    "type": "trade_war",        "source": "Geopolitical"},
            {"id": "argentina_default","headline": "Argentina sovereign default",           "type": "currency_crisis",  "source": "Market Event"},
        ]
    }


@router.get("/agents/population")
def preview_population(n_households: int = 50, seed: int = 42):
    """Build and summarize an agent population without running a simulation."""
    factory = AgentFactory(seed=seed)
    agents = factory.build(n_households=n_households, n_professional_retail=10, n_ordinary_retail=20)
    summary = factory.summary(agents)
    from collections import defaultdict
    by_tier: dict[str, list] = defaultdict(list)
    for a in agents:
        if len(by_tier[a.tier.value]) < 2:
            by_tier[a.tier.value].append({
                "name": a.name, "country": a.country,
                "financial_literacy": a.financial_literacy,
                "risk_tolerance": a.risk_tolerance.value,
                "information_speed": a.information_speed,
                "usd_exposure": a.usd_exposure,
            })
    return {**summary, "sample_agents_by_tier": dict(by_tier)}


@router.post("/simulate")
async def start_simulation(request: SimulationRequest, background_tasks: BackgroundTasks):
    """Start a new simulation. Returns immediately with simulation_id."""
    # Build shock
    factory_fn = SHOCK_FACTORIES.get(request.shock_preset)
    if factory_fn:
        shock = factory_fn()
    elif request.shock_custom:
        try:
            shock = MacroShock(**request.shock_custom)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid shock definition: {e}")
    else:
        shock = fed_rate_hike_75bps()

    # Build population
    factory = AgentFactory(seed=request.seed)
    agents = factory.build(
        n_households=request.n_households,
        n_professional_retail=request.n_professional_retail,
        n_ordinary_retail=request.n_ordinary_retail,
    )

    simulation = Simulation(agents=agents, shocks=[shock], num_rounds=request.n_rounds)
    _simulations[simulation.simulation_id] = simulation

    runner = SimulationRunner(use_llm=request.use_llm)
    background_tasks.add_task(_run_simulation, runner, simulation)

    return {
        "simulation_id": simulation.simulation_id,
        "status": "pending",
        "num_agents": len(agents),
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
    """SSE endpoint - streams round results with sample agent reactions."""
    sim = _simulations.get(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    agent_country = {a.agent_id: a.country for a in sim.agents}

    async def event_generator():
        last_round = -1
        while True:
            for result in sim.round_results:
                if result.round_num > last_round:
                    # Sample up to 3 individual reactions for the agent feed
                    sample = []
                    for rx in result.reactions[:3]:
                        sample.append({
                            "tier": rx.tier.value,
                            "action": rx.action[:60],
                            "sentiment": round(rx.sentiment, 4),
                            "country": agent_country.get(rx.agent_id, "??"),
                        })
                    data = {
                        "round_num": result.round_num,
                        "sentiment_by_tier": result.avg_sentiment_by_tier,
                        "net_usd_flow": round(result.net_usd_flow, 4),
                        "sample_reactions": sample,
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
