"""
NEXUS = HumanTwin
utils/logger.py

Action logger — records every agent decision to disk as JSONL.
Mirrors MiroFish's action_logger.py pattern but structured
for economic data: each log entry is a timestamped AgentReaction
with the full agent profile snapshot.

Log file format: one JSON object per line (JSONL)
Location: logs/simulation_{id}_{date}.jsonl

Used for:
- Post-simulation analysis in pandas / Stata
- Backtesting against real FX data
- Building the calibration feedback loop (Phase 1)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.agent import HumanTwin
from app.models.shock import MacroShock
from app.models.simulation import AgentReaction, Simulation


LOG_DIR = Path("logs")


def _ensure_log_dir() -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    return LOG_DIR


def _log_path(simulation_id: str) -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return _ensure_log_dir() / f"simulation_{simulation_id[:8]}_{date_str}.jsonl"


def _agent_snapshot(agent: HumanTwin) -> dict:
    """Minimal serializable snapshot of agent state at decision time."""
    return {
        "agent_id":          agent.agent_id,
        "tier":              agent.tier.value,
        "country":           agent.country,
        "age":               agent.age,
        "income":            round(agent.income_annual_eur, 2),
        "wealth":            round(agent.net_wealth_eur, 2),
        "literacy":          agent.financial_literacy,
        "risk_tolerance":    agent.risk_tolerance.value,
        "loss_aversion":     agent.loss_aversion,
        "info_speed":        agent.information_speed,
        "usd_exposure":      agent.usd_exposure,
        "eur_exposure":      agent.eur_exposure,
        "crypto_exposure":   agent.crypto_exposure,
        "social_influence":  agent.social_influence,
        "media_exposure":    agent.media_exposure,
    }


class ActionLogger:
    """
    Writes agent reactions to a JSONL log file.

    Usage:
        logger = ActionLogger(simulation_id)
        logger.log_reaction(agent, reaction, shock)
        logger.close()
    """

    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id
        self.path = _log_path(simulation_id)
        self._file = open(self.path, "a", encoding="utf-8")
        self._count = 0

    def log_reaction(
        self,
        agent: HumanTwin,
        reaction: AgentReaction,
        shock: MacroShock,
    ) -> None:
        entry = {
            "ts":            datetime.now(timezone.utc).isoformat(),
            "simulation_id": self.simulation_id,
            "round":         reaction.round_num,
            "shock_type":    shock.shock_type.value,
            "shock_source":  shock.source.value,
            "shock_mag_bps": shock.magnitude_bps,
            "action":        reaction.action,
            "usd_delta":     reaction.usd_delta,
            "sentiment":     reaction.sentiment,
            "reasoning_len": len(reaction.reasoning),
            **_agent_snapshot(agent),
        }
        self._file.write(json.dumps(entry) + "\n")
        self._count += 1

    def log_round_aggregate(
        self,
        round_num: int,
        sentiment_by_tier: dict[str, float],
        net_usd_flow: float,
    ) -> None:
        entry = {
            "ts":              datetime.now(timezone.utc).isoformat(),
            "simulation_id":   self.simulation_id,
            "record_type":     "round_aggregate",
            "round":           round_num,
            "net_usd_flow":    round(net_usd_flow, 6),
            "sentiment_by_tier": sentiment_by_tier,
        }
        self._file.write(json.dumps(entry) + "\n")

    def close(self) -> None:
        self._file.flush()
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def entries_written(self) -> int:
        return self._count

    @property
    def log_file(self) -> str:
        return str(self.path)


def log_full_simulation(simulation: Simulation) -> str:
    """
    Convenience function: log every reaction in a completed simulation.
    Returns the path to the log file.
    """
    if not simulation.shocks:
        return ""

    shock = simulation.shocks[0]

    # Build agent lookup map
    agent_map = {a.agent_id: a for a in simulation.agents}

    with ActionLogger(simulation.simulation_id) as logger:
        for result in simulation.round_results:
            for reaction in result.reactions:
                agent = agent_map.get(reaction.agent_id)
                if agent:
                    logger.log_reaction(agent, reaction, shock)
            logger.log_round_aggregate(
                result.round_num,
                result.avg_sentiment_by_tier,
                result.net_usd_flow,
            )

    return logger.log_file
