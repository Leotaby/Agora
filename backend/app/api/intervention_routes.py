"""
api/intervention_routes.py — God Mode endpoints.

POST /api/intervene — Execute a god-mode intervention.
GET  /api/intervene/types — List available intervention types + param schemas.
GET  /api/intervene/history — Past interventions with observed effects.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.intervention import (
    GodIntervention,
    GodInterventionType,
    INTERVENTION_SCHEMAS,
)
from app.models.world_event import WorldEvent, EventType, EventSeverity
from app.models.shock import MacroShock, ShockType, ShockSource
from app.models.geopolitical import SanctionsRegime, SanctionMeasure
from app.models.agent_message import AgentMessage, MessageType
from app.services.world_engine import get_engine

intervention_router = APIRouter(prefix="/intervene", tags=["god_mode"])

# Persistent history (lives as long as the process)
_history: list[GodIntervention] = []


class InterventionRequest(BaseModel):
    intervention_type: str = Field(..., description="One of GodInterventionType values")
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@intervention_router.get("/types")
def list_intervention_types():
    """List all god-mode intervention types and their parameter schemas."""
    return {"types": INTERVENTION_SCHEMAS}


@intervention_router.get("/history")
def get_history(limit: int = 50):
    """Return past interventions with their observed effects."""
    return {
        "history": [h.to_dict() for h in _history[-limit:]],
        "count": len(_history),
    }


@intervention_router.post("")
async def execute_intervention(request: InterventionRequest):
    """Execute a god-mode intervention. Immediately mutates world state."""
    engine = get_engine()
    if engine.world is None:
        raise HTTPException(status_code=400, detail="World not initialized.")

    try:
        itype = GodInterventionType(request.intervention_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown type: {request.intervention_type}. Available: {[t.value for t in GodInterventionType]}",
        )

    world = engine.world
    tick = world.tick
    sim_date = str(world.simulation_date)
    params = request.params

    # Create the intervention record
    record = GodIntervention(
        intervention_type=itype,
        params=params,
        tick=tick,
        simulation_date=sim_date,
    )

    # Dispatch to handler
    handler = _HANDLERS.get(itype)
    if not handler:
        raise HTTPException(status_code=500, detail=f"No handler for {itype.value}")

    try:
        event, effects = handler(engine, params, tick, sim_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Missing parameter: {e}")

    record.effects = effects
    _history.append(record)

    # Broadcast the event via SSE
    engine._record_event(event)
    engine._broadcast(event)

    return {
        "status": "executed",
        "intervention_id": record.intervention_id,
        "intervention_type": itype.value,
        "event_id": event.event_id,
        "headline": event.headline,
        "effects": effects,
    }


# ---------------------------------------------------------------------------
# Intervention handlers — each returns (WorldEvent, effects_dict)
# ---------------------------------------------------------------------------

def _handle_rate_change(engine, params, tick, sim_date):
    world = engine.world
    country_iso = params["country"].upper()
    delta_bps = float(params["rate_delta_bps"])

    country = world.countries.get(country_iso)
    if not country:
        raise ValueError(f"Country {country_iso} not found")

    # Apply inflation impact: rate hike → lower inflation, rate cut → higher
    inflation_delta = -delta_bps * 0.005  # 100bps hike → -0.5% inflation
    country.economy.inflation_pct = max(0, country.economy.inflation_pct + inflation_delta)

    # VIX impact
    world.macro.vix += abs(delta_bps) * 0.02

    # Shock the system
    shock = MacroShock(
        shock_type=ShockType.RATE_HIKE if delta_bps > 0 else ShockType.RATE_CUT,
        source=ShockSource.FED if country_iso == "US" else ShockSource.ECB if country_iso in ("EU", "DE", "FR", "IT") else ShockSource.MARKET,
        magnitude_bps=delta_bps,
        direction=1 if delta_bps > 0 else -1,
        headline=f"GOD MODE: {country.name} rate {'hike' if delta_bps > 0 else 'cut'} {abs(delta_bps):.0f}bps",
        description=f"Immediate rate change imposed by god mode. Inflation impact: {inflation_delta:+.2f}%.",
    )
    world.inject_shock(shock)
    engine._critical_this_tick = True

    effects = {
        "inflation_after": round(country.economy.inflation_pct, 2),
        "inflation_delta": round(inflation_delta, 2),
        "vix_after": round(world.macro.vix, 2),
    }

    event = WorldEvent(
        event_type=EventType.STATE_MUTATION,
        severity=EventSeverity.CRITICAL,
        tick=tick, simulation_date=sim_date,
        headline=shock.headline,
        description=shock.description,
        actor_type="god_mode", actor_id="rate_change",
        mutations=effects,
    )
    return event, effects


def _handle_natural_disaster(engine, params, tick, sim_date):
    world = engine.world
    country_iso = params["country"].upper()
    severity = max(1, min(10, int(params["severity"])))

    country = world.countries.get(country_iso)
    if not country:
        raise ValueError(f"Country {country_iso} not found")

    # GDP destruction: severity 10 = -15% GDP
    gdp_loss_pct = severity * 1.5
    gdp_before = country.economy.gdp_usd_bn
    country.economy.gdp_usd_bn *= (1 - gdp_loss_pct / 100)

    # Inflation spike from supply disruption
    country.economy.inflation_pct += severity * 0.8

    # Unemployment spike
    country.economy.unemployment_pct = min(50, country.economy.unemployment_pct + severity * 1.2)

    # FX reserves drain (emergency spending)
    country.economy.fx_reserves_usd_bn *= max(0.5, 1 - severity * 0.05)

    # VIX spike
    world.macro.vix += severity * 1.5
    world.macro.geopolitical_risk_index = min(100, world.macro.geopolitical_risk_index + severity * 2)

    effects = {
        "gdp_before": round(gdp_before, 2),
        "gdp_after": round(country.economy.gdp_usd_bn, 2),
        "gdp_loss_pct": round(gdp_loss_pct, 1),
        "inflation_after": round(country.economy.inflation_pct, 2),
        "unemployment_after": round(country.economy.unemployment_pct, 2),
    }

    event = WorldEvent(
        event_type=EventType.STATE_MUTATION,
        severity=EventSeverity.CRITICAL,
        tick=tick, simulation_date=sim_date,
        headline=f"GOD MODE: Natural disaster strikes {country.name} (severity {severity}/10)",
        description=f"GDP -{gdp_loss_pct:.1f}%, inflation +{severity * 0.8:.1f}%, unemployment +{severity * 1.2:.1f}%.",
        actor_type="god_mode", actor_id=country_iso,
        mutations=effects,
    )
    engine._critical_this_tick = True
    return event, effects


def _handle_epidemic(engine, params, tick, sim_date):
    world = engine.world
    origin = params["origin_country"].upper()
    severity = max(1, min(10, int(params["severity"])))
    transmissibility = float(params.get("transmissibility", 0.5))

    country = world.countries.get(origin)
    if not country:
        raise ValueError(f"Country {origin} not found")

    # Spread through trade partners based on transmissibility
    affected_countries = [origin]
    if transmissibility > 0.3:
        for partner in country.trade_partners[:int(transmissibility * 10)]:
            if partner in world.countries:
                affected_countries.append(partner)

    total_gdp_loss = 0
    for iso2 in affected_countries:
        c = world.countries.get(iso2)
        if not c:
            continue
        # Origin takes full hit, partners take reduced
        factor = 1.0 if iso2 == origin else transmissibility * 0.5
        gdp_hit = severity * 0.8 * factor
        c.economy.gdp_usd_bn *= (1 - gdp_hit / 100)
        c.economy.unemployment_pct = min(40, c.economy.unemployment_pct + severity * 0.6 * factor)
        total_gdp_loss += gdp_hit

    # Inject fear messages into agent society
    if engine._society:
        for agent_id, life in engine._society.lives.items():
            agent = engine._find_agent(agent_id)
            if agent and agent.country in affected_countries:
                msg = AgentMessage(
                    sender_id="god_mode_epidemic",
                    receiver_id=agent_id,
                    content=f"Epidemic alert: disease spreading in {country.name}. Severity {severity}/10.",
                    message_type=MessageType.NEWS,
                    tick=tick, simulation_date=sim_date,
                    metadata={"epidemic": True, "severity": severity},
                )
                life.inbox.append(msg)
                # Directly shift beliefs
                life.beliefs["market_fear"] = min(1.0, life.beliefs.get("market_fear", 0.2) + severity * 0.06)

    world.macro.vix += severity * 2
    world.macro.geopolitical_risk_index = min(100, world.macro.geopolitical_risk_index + severity)

    effects = {
        "affected_countries": affected_countries,
        "total_countries": len(affected_countries),
        "origin_gdp_loss_pct": round(severity * 0.8, 1),
        "vix_after": round(world.macro.vix, 2),
    }

    event = WorldEvent(
        event_type=EventType.STATE_MUTATION,
        severity=EventSeverity.CRITICAL,
        tick=tick, simulation_date=sim_date,
        headline=f"GOD MODE: Epidemic originating in {country.name} (severity {severity}/10)",
        description=f"Spreads to {len(affected_countries)} countries. Transmissibility {transmissibility:.0%}.",
        actor_type="god_mode", actor_id=origin,
        mutations=effects,
    )
    engine._critical_this_tick = True
    return event, effects


def _handle_information_leak(engine, params, tick, sim_date):
    content = str(params["content"])
    target_role = params.get("target_role", "all")
    is_true = params.get("is_true", True)
    belief_key = params.get("belief_key", "market_fear")
    belief_delta = float(params.get("belief_delta", 0.2))

    if not engine._society:
        raise ValueError("Society not initialized")

    injected_count = 0
    for agent_id, life in engine._society.lives.items():
        role_val = engine._society.role_agents.get(agent_id)
        role_str = role_val.value if role_val else "generic"

        if target_role != "all" and role_str != target_role:
            continue

        # Deliver the message
        msg = AgentMessage(
            sender_id="god_mode_leak",
            receiver_id=agent_id,
            content=f"{'[VERIFIED] ' if is_true else '[UNVERIFIED] '}{content}",
            message_type=MessageType.RUMOR if not is_true else MessageType.NEWS,
            tick=tick, simulation_date=sim_date,
            metadata={"leak": True, "is_true": is_true},
        )
        life.inbox.append(msg)
        engine._society._mailboxes.setdefault(agent_id, []).append(msg)

        # Directly shift the target belief
        old_val = life.beliefs.get(belief_key, 0.5)
        life.beliefs[belief_key] = max(0, min(1, old_val + belief_delta))
        injected_count += 1

    effects = {
        "agents_reached": injected_count,
        "target_role": target_role,
        "belief_key": belief_key,
        "belief_delta": belief_delta,
        "is_true": is_true,
    }

    event = WorldEvent(
        event_type=EventType.STATE_MUTATION,
        severity=EventSeverity.WARNING,
        tick=tick, simulation_date=sim_date,
        headline=f"GOD MODE: Information {'leak' if is_true else 'disinformation'} injected into {injected_count} agents",
        description=f"Content: {content[:80]}. Target: {target_role}. Belief '{belief_key}' shifted by {belief_delta:+.2f}.",
        actor_type="god_mode", actor_id="information_leak",
        mutations=effects,
    )
    return event, effects


def _handle_market_shock(engine, params, tick, sim_date):
    world = engine.world
    asset = str(params["asset"]).lower()
    change_pct = float(params["change_pct"])

    factor = 1 + change_pct / 100

    asset_map = {
        "oil": ("oil_price_brent", "Oil (Brent)"),
        "gold": ("gold_price_usd", "Gold"),
        "bitcoin": ("bitcoin_price_usd", "Bitcoin"),
        "vix": ("vix", "VIX"),
    }

    if asset not in asset_map:
        raise ValueError(f"Unknown asset: {asset}. Available: {list(asset_map.keys())}")

    field_name, label = asset_map[asset]
    before = getattr(world.macro, field_name)
    new_val = max(0.01, before * factor)
    setattr(world.macro, field_name, new_val)

    # Oil shock cascades to inflation
    if asset == "oil" and abs(change_pct) > 10:
        for c in world.countries.values():
            c.economy.inflation_pct += change_pct * 0.02

    # VIX jump from any crash
    if asset != "vix" and change_pct < -15:
        world.macro.vix += abs(change_pct) * 0.15

    engine._critical_this_tick = True

    effects = {
        "asset": asset,
        "before": round(before, 2),
        "after": round(new_val, 2),
        "change_pct": round(change_pct, 1),
        "vix_after": round(world.macro.vix, 2),
    }

    event = WorldEvent(
        event_type=EventType.STATE_MUTATION,
        severity=EventSeverity.CRITICAL,
        tick=tick, simulation_date=sim_date,
        headline=f"GOD MODE: {label} {'crashes' if change_pct < 0 else 'spikes'} {change_pct:+.0f}%",
        description=f"{label}: ${before:.2f} → ${new_val:.2f}",
        actor_type="god_mode", actor_id="market_shock",
        mutations=effects,
    )
    return event, effects


def _handle_sanctions_change(engine, params, tick, sim_date):
    world = engine.world
    sender = params["sender_country"].upper()
    target = params["target_country"].upper()
    action = params["action"]  # "impose" or "lift"

    if sender not in world.countries:
        raise ValueError(f"Sender country {sender} not found")
    if target not in world.countries:
        raise ValueError(f"Target country {target} not found")

    target_country = world.countries[target]

    if action == "impose":
        # Create new sanctions regime
        regime = SanctionsRegime(
            regime_id=f"GOD_{sender}_{target}_{tick}",
            name=f"God Mode sanctions: {sender} → {target}",
            sender_countries=[sender],
            target_countries=[target],
            measures=[SanctionMeasure.TRADE_EMBARGO, SanctionMeasure.ASSET_FREEZE, SanctionMeasure.SWIFT_EXCLUSION],
            imposed_date=world.simulation_date,
            gdp_impact_annual_pct=-5.0,
            trade_reduction_pct=40.0,
            inflation_impact_pct=5.0,
        )
        world.sanctions_regimes.append(regime)
        target_country.politics.sanctions_target = True
        target_country.economy.inflation_pct += 5
        world.macro.geopolitical_risk_index = min(100, world.macro.geopolitical_risk_index + 8)

        effects = {"action": "imposed", "sender": sender, "target": target, "regime_id": regime.regime_id}
        headline = f"GOD MODE: {sender} imposes sanctions on {target}"

    elif action == "lift":
        removed = 0
        for regime in world.sanctions_regimes:
            if target in regime.target_countries and sender in regime.sender_countries and regime.active:
                regime.active = False
                removed += 1
        # Check if any active sanctions remain
        still_sanctioned = any(
            r.active and target in r.target_countries
            for r in world.sanctions_regimes
        )
        target_country.politics.sanctions_target = still_sanctioned
        if not still_sanctioned:
            target_country.economy.inflation_pct = max(0, target_country.economy.inflation_pct - 3)

        effects = {"action": "lifted", "sender": sender, "target": target, "regimes_deactivated": removed}
        headline = f"GOD MODE: {sender} lifts sanctions on {target} ({removed} regimes)"
    else:
        raise ValueError(f"Unknown action: {action}. Use 'impose' or 'lift'.")

    event = WorldEvent(
        event_type=EventType.SANCTIONS_ESCALATION,
        severity=EventSeverity.CRITICAL,
        tick=tick, simulation_date=sim_date,
        headline=headline,
        description=f"Sanctions {action} by {sender} targeting {target}.",
        actor_type="god_mode", actor_id=target,
        mutations=effects,
    )
    engine._critical_this_tick = True
    return event, effects


def _handle_war_declaration(engine, params, tick, sim_date):
    world = engine.world
    aggressor_iso = params["aggressor"].upper()
    defender_iso = params["defender"].upper()
    severity = max(1, min(10, int(params["severity"])))

    aggressor = world.countries.get(aggressor_iso)
    defender = world.countries.get(defender_iso)
    if not aggressor:
        raise ValueError(f"Aggressor {aggressor_iso} not found")
    if not defender:
        raise ValueError(f"Defender {defender_iso} not found")

    # GDP destruction for both sides
    agg_gdp_hit = severity * 0.8
    def_gdp_hit = severity * 1.5
    aggressor.economy.gdp_usd_bn *= (1 - agg_gdp_hit / 100)
    defender.economy.gdp_usd_bn *= (1 - def_gdp_hit / 100)

    # Inflation spike
    aggressor.economy.inflation_pct += severity * 0.5
    defender.economy.inflation_pct += severity * 1.0

    # Unemployment
    aggressor.economy.unemployment_pct = min(40, aggressor.economy.unemployment_pct + severity * 0.5)
    defender.economy.unemployment_pct = min(40, defender.economy.unemployment_pct + severity * 1.0)

    # Global macro impact
    world.macro.vix += severity * 3
    world.macro.geopolitical_risk_index = min(100, world.macro.geopolitical_risk_index + severity * 4)
    world.macro.oil_price_brent *= (1 + severity * 0.03)
    world.macro.gold_price_usd *= (1 + severity * 0.02)

    # Auto-impose sanctions from NATO if defender is in NATO
    nato_members = set()
    for alliance in world.alliances:
        if alliance.alliance_id == "NATO" and alliance.active:
            nato_members = set(alliance.members)
    if defender_iso in nato_members and aggressor_iso not in nato_members:
        senders = [m for m in nato_members if m != aggressor_iso and m in world.countries]
        regime = SanctionsRegime(
            regime_id=f"WAR_{aggressor_iso}_{tick}",
            name=f"War sanctions: NATO → {aggressor_iso}",
            sender_countries=senders,
            target_countries=[aggressor_iso],
            measures=[SanctionMeasure.TRADE_EMBARGO, SanctionMeasure.ASSET_FREEZE, SanctionMeasure.SWIFT_EXCLUSION],
            imposed_date=world.simulation_date,
            gdp_impact_annual_pct=-8.0,
            trade_reduction_pct=60.0,
            inflation_impact_pct=10.0,
        )
        world.sanctions_regimes.append(regime)
        aggressor.politics.sanctions_target = True

    # Inject fear into soldier agents
    if engine._society:
        for agent_id, life in engine._society.lives.items():
            agent = engine._find_agent(agent_id)
            if agent and agent.country in (aggressor_iso, defender_iso):
                life.beliefs["conflict_risk"] = min(1.0, life.beliefs.get("conflict_risk", 0.3) + severity * 0.08)
                life.beliefs["market_fear"] = min(1.0, life.beliefs.get("market_fear", 0.2) + severity * 0.05)

    effects = {
        "aggressor": aggressor_iso,
        "defender": defender_iso,
        "agg_gdp_loss_pct": round(agg_gdp_hit, 1),
        "def_gdp_loss_pct": round(def_gdp_hit, 1),
        "vix_after": round(world.macro.vix, 2),
        "geo_risk_after": round(world.macro.geopolitical_risk_index, 2),
        "nato_sanctions": defender_iso in nato_members and aggressor_iso not in nato_members,
    }

    event = WorldEvent(
        event_type=EventType.STATE_MUTATION,
        severity=EventSeverity.CRITICAL,
        tick=tick, simulation_date=sim_date,
        headline=f"GOD MODE: {aggressor.name} declares war on {defender.name} (severity {severity}/10)",
        description=f"GDP impact: {aggressor.name} -{agg_gdp_hit:.1f}%, {defender.name} -{def_gdp_hit:.1f}%. Oil +{severity * 3}%.",
        actor_type="god_mode", actor_id=aggressor_iso,
        mutations=effects,
    )
    engine._critical_this_tick = True
    return event, effects


def _handle_take_agent_control(engine, params, tick, sim_date):
    agent_id = str(params["agent_id"])
    num_ticks = max(1, min(100, int(params["num_ticks"])))
    forced_action = str(params["forced_action"])
    forced_usd_delta = float(params.get("forced_usd_delta", 0))

    agent = engine._find_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    # Store the override in the agent's memory buffer
    override_marker = f"GOD_OVERRIDE|{num_ticks}|{forced_action}|{forced_usd_delta}"
    agent.memory_buffer.append(override_marker)

    # Also apply the first tick's override immediately
    if forced_usd_delta:
        agent.usd_exposure = max(0, min(1, agent.usd_exposure + forced_usd_delta))
        agent.eur_exposure = max(0, min(1, 1.0 - agent.usd_exposure - agent.equity_exposure - agent.crypto_exposure))

    # Record in society
    if engine._society:
        life = engine._society.lives.get(agent_id)
        if life:
            life.recent_decisions.append({
                "action": f"[GOD OVERRIDE] {forced_action}",
                "reasoning": f"Human took control for {num_ticks} ticks",
                "usd_delta": forced_usd_delta,
            })

    effects = {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "num_ticks": num_ticks,
        "forced_action": forced_action,
        "forced_usd_delta": forced_usd_delta,
        "usd_exposure_after": round(agent.usd_exposure, 4),
    }

    event = WorldEvent(
        event_type=EventType.HUMAN_INTERVENTION,
        severity=EventSeverity.WARNING,
        tick=tick, simulation_date=sim_date,
        headline=f"GOD MODE: Taking control of {agent.name} for {num_ticks} ticks",
        description=f"Action: {forced_action}. USD delta: {forced_usd_delta:+.3f}/tick.",
        actor_type="god_mode", actor_id=agent_id,
        mutations=effects,
    )
    return event, effects


# Handler dispatch table
_HANDLERS = {
    GodInterventionType.RATE_CHANGE:        _handle_rate_change,
    GodInterventionType.NATURAL_DISASTER:   _handle_natural_disaster,
    GodInterventionType.EPIDEMIC:           _handle_epidemic,
    GodInterventionType.INFORMATION_LEAK:   _handle_information_leak,
    GodInterventionType.MARKET_SHOCK:       _handle_market_shock,
    GodInterventionType.SANCTIONS_CHANGE:   _handle_sanctions_change,
    GodInterventionType.WAR_DECLARATION:    _handle_war_declaration,
    GodInterventionType.TAKE_AGENT_CONTROL: _handle_take_agent_control,
}
