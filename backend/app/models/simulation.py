"""
simulation.py - Simulation session model

Tracks the state of a running or completed simulation:
agents, shocks injected, round history, and results.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid

from app.models.agent import HumanTwin, AgentTier
from app.models.shock import MacroShock


class SimulationStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


@dataclass
class AgentReaction:
    """
    The response of a single agent to a shock in a given round.
    """
    agent_id: str
    tier: AgentTier
    round_num: int
    shock_id: str

    # What the agent decided
    reasoning: str = ""              # LLM chain-of-thought
    action: str = ""                 # e.g. "buy USD", "hold", "increase mortgage payment"
    usd_delta: float = 0.0           # Change in USD exposure (percentage points)
    eur_delta: float = 0.0           # Change in EUR exposure
    sentiment: float = 0.0           # -1 (bearish USD) to +1 (bullish USD)

    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RoundResult:
    """Aggregate result of one simulation round across all agents."""
    round_num: int
    shock_id: str
    reactions: list[AgentReaction] = field(default_factory=list)

    # Emergent aggregate metrics
    avg_sentiment_by_tier: dict[str, float] = field(default_factory=dict)
    net_usd_flow: float = 0.0        # Aggregate USD buying pressure
    exchange_rate_delta: float = 0.0 # Implied EUR/USD change (basis points)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def compute_aggregates(self) -> None:
        """Compute tier-level sentiment and net flow from individual reactions."""
        by_tier: dict[str, list[float]] = {}
        net_flow = 0.0
        for r in self.reactions:
            tier_key = r.tier.value
            by_tier.setdefault(tier_key, []).append(r.sentiment)
            net_flow += r.usd_delta
        self.avg_sentiment_by_tier = {
            t: sum(v) / len(v) for t, v in by_tier.items()
        }
        self.net_usd_flow = net_flow


@dataclass
class Simulation:
    """
    A full simulation session.
    Created when a shock is injected. Tracks all rounds and results.
    """
    simulation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: SimulationStatus = SimulationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Inputs
    agents: list[HumanTwin] = field(default_factory=list)
    shocks: list[MacroShock] = field(default_factory=list)
    num_rounds: int = 10

    # Outputs
    round_results: list[RoundResult] = field(default_factory=list)
    final_report: str = ""

    @property
    def num_agents(self) -> int:
        return len(self.agents)

    @property
    def agents_by_tier(self) -> dict[str, list[HumanTwin]]:
        result: dict[str, list[HumanTwin]] = {}
        for agent in self.agents:
            result.setdefault(agent.tier.value, []).append(agent)
        return result

    def summary(self) -> dict:
        return {
            "simulation_id": self.simulation_id,
            "status": self.status.value,
            "num_agents": self.num_agents,
            "num_shocks": len(self.shocks),
            "rounds_completed": len(self.round_results),
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"Simulation(id={self.simulation_id[:8]}..., "
            f"status={self.status.value}, agents={self.num_agents}, "
            f"rounds={len(self.round_results)}/{self.num_rounds})"
        )
