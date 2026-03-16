"""
Orchestrates a full simulation:
  1. Build population (AgentFactory)
  2. For each round: filter agents by tier delay, call LLMEngine in batch
  3. Aggregate results into RoundResult
  4. Return completed Simulation

Reusable service callable from scripts and the API.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from app.config import settings
from app.models.agent import HumanTwin
from app.models.shock import MacroShock
from app.models.simulation import (
    Simulation, SimulationStatus, AgentReaction, RoundResult
)
from app.services.agent_factory import AgentFactory
from app.services.llm_engine import LLMEngine

console = Console()


class SimulationRunner:
    """
    Runs a complete NEXUS simulation end to end.
    Supports both stub mode (no LLM) and live mode (real language model calls).
    """

    def __init__(self, use_llm: bool = True, concurrency: int = 8):
        self.use_llm = use_llm
        self.concurrency = concurrency
        self.engine = LLMEngine() if use_llm else None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        simulation: Simulation,
        verbose: bool = True,
    ) -> Simulation:
        """
        Run all rounds of the simulation.
        Modifies simulation in place, returns it completed.
        """
        simulation.status = SimulationStatus.RUNNING
        shock = simulation.shocks[0]  # Phase 0: single shock per simulation

        if verbose:
            console.print(f"\n[cyan]Starting simulation {simulation.simulation_id[:8]}...[/cyan]")
            console.print(f"  Agents: {simulation.num_agents}")
            console.print(f"  Shock:  {shock.headline}")
            console.print(f"  Rounds: {simulation.num_rounds}\n")

        for round_num in range(simulation.num_rounds):
            if verbose:
                console.print(f"[bold]Round {round_num}[/bold]", end=" ")

            # Filter agents active in this round (respect tier delay)
            active_agents = self._get_active_agents(simulation.agents, shock, round_num)

            # Reset progress for this round
            simulation.progress = {
                "round_num": round_num,
                "agents_total": len(active_agents),
                "agents_done": 0,
                "agents_failed": 0,
                "errors": [],
            }

            if verbose:
                console.print(f"[dim]({len(active_agents)} active agents)[/dim]")

            # Get reactions
            if self.use_llm and self.engine:
                reactions = await self.engine.react_batch(
                    active_agents, shock, round_num, self.concurrency,
                    progress=simulation.progress,
                )
            else:
                reactions = self._stub_reactions(active_agents, shock, round_num)
                simulation.progress["agents_done"] = len(active_agents)

            # Build round result
            result = RoundResult(
                round_num=round_num,
                shock_id=shock.shock_id,
                reactions=reactions,
            )
            result.compute_aggregates()
            simulation.round_results.append(result)

            if verbose:
                self._print_round_summary(result)

        simulation.status = SimulationStatus.COMPLETED
        simulation.completed_at = datetime.utcnow()
        return simulation

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_active_agents(
        agents: list[HumanTwin],
        shock: MacroShock,
        round_num: int,
    ) -> list[HumanTwin]:
        """Return agents whose tier delay has been reached by this round."""
        active = []
        for agent in agents:
            delay = shock.tier_delay_rounds.get(agent.tier.value, 0)
            if round_num >= delay:
                active.append(agent)
        return active

    @staticmethod
    def _stub_reactions(
        agents: list[HumanTwin],
        shock: MacroShock,
        round_num: int,
    ) -> list[AgentReaction]:
        """
        Deterministic stub reactions (no LLM calls).
        Used for testing and CI validation.
        Mirrors the logic from run_forex_simulation.py.
        """
        reactions = []
        for agent in agents:
            salience = shock.tier_salience.get(agent.tier.value, 0.5)
            if shock.direction > 0:
                sentiment = salience * agent.financial_literacy
                usd_delta = sentiment * 0.08 * (1 - agent.loss_aversion / 12)
            else:
                sentiment = -salience * agent.financial_literacy
                usd_delta = sentiment * 0.08

            action = (
                "buy USD aggressively" if usd_delta > 0.04 else
                "buy USD cautiously"   if usd_delta > 0.01 else
                "hold"                 if abs(usd_delta) < 0.01 else
                "reduce USD exposure"
            )
            reactions.append(AgentReaction(
                agent_id=agent.agent_id,
                tier=agent.tier,
                round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=f"[STUB] tier={agent.tier.value} salience={salience:.2f}",
                action=action,
                usd_delta=round(usd_delta, 4),
                sentiment=round(sentiment, 4),
            ))
        return reactions

    @staticmethod
    def _print_round_summary(result: RoundResult) -> None:
        from rich.table import Table
        from collections import Counter

        tier_actions: dict[str, list[str]] = {}
        for r in result.reactions:
            tier_actions.setdefault(r.tier.value, []).append(r.action)

        table = Table(show_header=True, header_style="dim", box=None)
        table.add_column("Tier", width=24)
        table.add_column("n", justify="right", width=5)
        table.add_column("Avg sentiment", justify="right", width=14)
        table.add_column("Flow", justify="right", width=10)

        for tier, sentiment in result.avg_sentiment_by_tier.items():
            actions = tier_actions.get(tier, [])
            dominant = Counter(actions).most_common(1)[0][0] if actions else "—"
            color = "green" if sentiment > 0.05 else "red" if sentiment < -0.05 else "dim"
            short = tier.split("_", 1)[-1].replace("_", " ")
            table.add_row(
                short,
                str(len(actions)),
                f"[{color}]{sentiment:+.3f}[/{color}]",
                dominant[:18],
            )
        console.print(table)
        console.print(f"  [dim]Net USD flow: {result.net_usd_flow:+.3f}[/dim]\n")


# ------------------------------------------------------------------
# Convenience builder - quick simulation from a shock
# ------------------------------------------------------------------

def quick_simulation(
    shock: MacroShock,
    n_households: int = 100,
    n_rounds: int = 5,
    use_llm: bool = False,
    seed: int = 42,
) -> Simulation:
    """
    Build a population, attach a shock, run the simulation, return results.
    use_llm=False uses stub reactions (no API keys needed).
    use_llm=True fires real LLM calls per agent.
    """
    factory = AgentFactory(seed=seed)
    agents = factory.build(
        n_households=n_households,
        n_professional_retail=20,
        n_ordinary_retail=40,
    )
    simulation = Simulation(
        agents=agents,
        shocks=[shock],
        num_rounds=n_rounds,
    )
    runner = SimulationRunner(use_llm=use_llm)
    return asyncio.run(runner.run(simulation, verbose=True))
