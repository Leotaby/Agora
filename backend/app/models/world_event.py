"""
world_event.py - Event system for the living world tick engine.

WorldEvent is the unit of SSE broadcast. Every discrete change in the world
(threshold trigger, agent decision, human intervention) produces one or more events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class EventType(str, Enum):
    # Tick lifecycle
    TICK_START           = "tick_start"
    TICK_END             = "tick_end"

    # Threshold-triggered
    CURRENCY_DEVALUATION = "currency_devaluation"
    CYBER_ATTACK         = "cyber_attack"
    APPROVAL_DROP        = "approval_drop"
    SOCIAL_UNREST        = "social_unrest"
    IMF_INTERVENTION     = "imf_intervention"
    RISK_OFF_CASCADE     = "risk_off_cascade"
    SOVEREIGN_DOWNGRADE  = "sovereign_downgrade"
    SANCTIONS_ESCALATION = "sanctions_escalation"
    ELECTION_TRIGGERED   = "election_triggered"
    CAPITAL_FLIGHT       = "capital_flight"
    OIL_PRICE_SHOCK      = "oil_price_shock"

    # Agent actions
    AGENT_DECISION       = "agent_decision"
    HUMAN_INTERVENTION   = "human_intervention"

    # Shock lifecycle
    SHOCK_GENERATED      = "shock_generated"
    SHOCK_INJECTED       = "shock_injected"

    # Generic state change
    STATE_MUTATION       = "state_mutation"


class EventSeverity(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


@dataclass
class WorldEvent:
    """A discrete event that occurred during a world tick."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.STATE_MUTATION
    severity: EventSeverity = EventSeverity.INFO
    tick: int = 0
    simulation_date: str = ""

    # What happened
    headline: str = ""
    description: str = ""

    # Who caused it
    actor_type: str = ""    # country | agent | institution | nonstate_actor | system
    actor_id: str = ""

    # State changes (key-value)
    mutations: dict[str, Any] = field(default_factory=dict)

    # Linked shock if this event generated one
    generated_shock_id: Optional[str] = None

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_sse_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "tick": self.tick,
            "simulation_date": self.simulation_date,
            "headline": self.headline,
            "description": self.description,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "mutations": self.mutations,
            "generated_shock_id": self.generated_shock_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HumanIntervention:
    """A human observer's manual decision injected into an agent."""
    agent_id: str = ""
    action: str = ""
    usd_delta: float = 0.0
    eur_delta: float = 0.0
    equity_delta: float = 0.0
    crypto_delta: float = 0.0
    reasoning: str = "Human override"
    submitted_at: datetime = field(default_factory=datetime.utcnow)
