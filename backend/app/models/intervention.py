"""
models/intervention.py — God Mode intervention types.

Each intervention immediately mutates world state and propagates
through the tick engine. They are the "hand of god" — instantaneous,
powerful, and historically logged for cause-effect analysis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class GodInterventionType(str, Enum):
    RATE_CHANGE        = "rate_change"          # Change any central bank's rate
    NATURAL_DISASTER   = "natural_disaster"     # GDP shock + displacement
    EPIDEMIC           = "epidemic"             # Spreads through social networks
    INFORMATION_LEAK   = "information_leak"     # Inject true/false info into agents
    MARKET_SHOCK       = "market_shock"         # Crash or spike any asset price
    SANCTIONS_CHANGE   = "sanctions_change"     # Add or remove sanctions
    WAR_DECLARATION    = "war_declaration"      # Conflict between two countries
    TAKE_AGENT_CONTROL = "take_agent_control"   # Human takes over an agent


# Parameter schemas per intervention type (for frontend validation hints)
INTERVENTION_SCHEMAS: dict[str, dict] = {
    "rate_change": {
        "label": "Rate Change",
        "icon": "🏦",
        "desc": "Immediately change a central bank's policy rate.",
        "params": {
            "country": {"type": "country", "label": "Country (ISO2)", "required": True},
            "rate_delta_bps": {"type": "number", "label": "Rate change (bps)", "min": -500, "max": 500, "required": True},
        },
    },
    "natural_disaster": {
        "label": "Natural Disaster",
        "icon": "🌊",
        "desc": "Hit a country with GDP destruction, displacement, and inflation.",
        "params": {
            "country": {"type": "country", "label": "Country (ISO2)", "required": True},
            "severity": {"type": "number", "label": "Severity (1-10)", "min": 1, "max": 10, "required": True},
        },
    },
    "epidemic": {
        "label": "Epidemic",
        "icon": "🦠",
        "desc": "Disease spreads through agent social networks, reducing productivity.",
        "params": {
            "origin_country": {"type": "country", "label": "Origin country (ISO2)", "required": True},
            "severity": {"type": "number", "label": "Severity (1-10)", "min": 1, "max": 10, "required": True},
            "transmissibility": {"type": "number", "label": "Transmissibility (0-1)", "min": 0, "max": 1, "required": False},
        },
    },
    "information_leak": {
        "label": "Information Leak",
        "icon": "📡",
        "desc": "Inject true or false information into specific agents.",
        "params": {
            "content": {"type": "text", "label": "Information content", "required": True},
            "target_role": {"type": "text", "label": "Target role (or 'all')", "required": False},
            "is_true": {"type": "boolean", "label": "Is this true info?", "required": False},
            "belief_key": {"type": "text", "label": "Belief to affect", "required": False},
            "belief_delta": {"type": "number", "label": "Belief change (-1 to 1)", "min": -1, "max": 1, "required": False},
        },
    },
    "market_shock": {
        "label": "Market Shock",
        "icon": "💥",
        "desc": "Crash or spike any asset price instantly.",
        "params": {
            "asset": {"type": "select", "label": "Asset", "options": ["oil", "gold", "bitcoin", "vix"], "required": True},
            "change_pct": {"type": "number", "label": "Change (%)", "min": -90, "max": 500, "required": True},
        },
    },
    "sanctions_change": {
        "label": "Sanctions Change",
        "icon": "🚫",
        "desc": "Add or remove sanctions between countries.",
        "params": {
            "sender_country": {"type": "country", "label": "Sender country (ISO2)", "required": True},
            "target_country": {"type": "country", "label": "Target country (ISO2)", "required": True},
            "action": {"type": "select", "label": "Action", "options": ["impose", "lift"], "required": True},
        },
    },
    "war_declaration": {
        "label": "War Declaration",
        "icon": "⚔️",
        "desc": "Trigger armed conflict between two countries.",
        "params": {
            "aggressor": {"type": "country", "label": "Aggressor (ISO2)", "required": True},
            "defender": {"type": "country", "label": "Defender (ISO2)", "required": True},
            "severity": {"type": "number", "label": "Severity (1-10)", "min": 1, "max": 10, "required": True},
        },
    },
    "take_agent_control": {
        "label": "Take Agent Control",
        "icon": "🎮",
        "desc": "Override an agent's next N decisions with your own.",
        "params": {
            "agent_id": {"type": "text", "label": "Agent ID", "required": True},
            "num_ticks": {"type": "number", "label": "Ticks to control", "min": 1, "max": 100, "required": True},
            "forced_action": {"type": "text", "label": "Forced action description", "required": True},
            "forced_usd_delta": {"type": "number", "label": "USD delta per tick", "min": -1, "max": 1, "required": False},
        },
    },
}


@dataclass
class GodIntervention:
    """A single God Mode intervention that was executed."""
    intervention_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intervention_type: GodInterventionType = GodInterventionType.MARKET_SHOCK
    params: dict[str, Any] = field(default_factory=dict)
    tick: int = 0
    simulation_date: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Observed effects (populated after execution)
    effects: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "intervention_id": self.intervention_id,
            "intervention_type": self.intervention_type.value,
            "params": self.params,
            "tick": self.tick,
            "simulation_date": self.simulation_date,
            "timestamp": self.timestamp.isoformat(),
            "effects": self.effects,
        }
