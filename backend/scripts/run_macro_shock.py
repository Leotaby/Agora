"""
NEXUS = HumanTwin
scripts/run_macro_shock.py

Full pipeline test:
  AgentFactory → MacroShock → SimulationRunner (stub) → Rich report

Run from /backend:
    uv run python scripts/run_macro_shock.py
    uv run python scripts/run_macro_shock.py --llm      # real Claude calls
    uv run python scripts/run_macro_shock.py --ecb      # ECB cut shock
    uv run python scripts/run_macro_shock.py --rounds 8
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from app.models.shock import fed_rate_hike_75bps, ecb_surprise_cut_50bps
from app.models.simulation import Simulation
from app.services.agent_factory import AgentFactory
from app.services.simulation_runner import SimulationRunner

console = Console()


def build_final_report(sim: Simulation) -> None:
    """Print a structured post-simulation report."""
    shock = sim.shocks[0]

    console.print(Panel.fit(
        f"[bold]NEXUS = HumanTwin — Simulation Report[/bold]\n"
        f"[dim]ID: {sim.simulation_id}[/dim]",
        border_style="cyan"
    ))

    # Shock summary
    console.print(f"\n[yellow]Shock:[/yellow] {shock.headline}")
    console.print(f"[dim]Source: {shock.source.value} | Type: {shock.shock_type.value}[/dim]\n")

    # Population summary
    factory = AgentFactory()
    pop = factory.summary(sim.agents)
    console.print("[bold]Population[/bold]")
    tier_table = Table(box=box.SIMPLE, show_header=False)
    tier_table.add_column("Tier", style="dim")
    tier_table.add_column("Count", justify="right")
    for tier, count in sorted(pop["by_tier"].items()):
        tier_table.add_row(tier.replace("_", " "), str(count))
    console.print(tier_table)

    # Round-by-round sentiment evolution
    console.print("\n[bold]Sentiment evolution by tier[/bold]")
    tiers = sorted({
        t for r in sim.round_results
        for t in r.avg_sentiment_by_tier.keys()
    })

    evo_table = Table(box=box.SIMPLE)
    evo_table.add_column("Round", justify="center", width=7)
    for t in tiers:
        short = t.split("_", 1)[-1][:14]
        evo_table.add_column(short, justify="right", width=12)
    evo_table.add_column("Net flow", justify="right", width=10)

    for result in sim.round_results:
        cells = []
        for t in tiers:
            s = result.avg_sentiment_by_tier.get(t, 0.0)
            color = "green" if s > 0.05 else "red" if s < -0.05 else "dim"
            cells.append(f"[{color}]{s:+.3f}[/{color}]")
        flow = result.net_usd_flow
        flow_color = "green" if flow > 0 else "red" if flow < 0 else "dim"
        evo_table.add_row(str(result.round_num), *cells, f"[{flow_color}]{flow:+.3f}[/{flow_color}]")

    console.print(evo_table)

    # Key insight
    if sim.round_results:
        r0 = sim.round_results[0]
        r_last = sim.round_results[-1]
        hh_sent_r0 = r0.avg_sentiment_by_tier.get("T7_household", 0.0)
        hh_sent_last = r_last.avg_sentiment_by_tier.get("T7_household", 0.0)
        hf_sent_r0 = r0.avg_sentiment_by_tier.get("T2_macro_hedge_fund", 0.0)

        console.print(f"\n[bold]Disconnect detection[/bold]")
        console.print(
            f"  Hedge funds at t=0:    [green]{hf_sent_r0:+.3f}[/green] (instant reaction)"
        )
        console.print(
            f"  Households at t=0:     [dim]{hh_sent_r0:+.3f}[/dim] (not yet processed)"
        )
        console.print(
            f"  Households at t={r_last.round_num}:    [yellow]{hh_sent_last:+.3f}[/yellow] (delayed response)"
        )
        console.print(
            f"\n  [italic]This gap — {hf_sent_r0 - hh_sent_r0:+.3f} sentiment units — is the "
            f"Meese-Rogoff disconnect window.[/italic]"
        )

    console.print(f"\n[dim]Completed in {sim.num_rounds} rounds | Status: {sim.status.value}[/dim]\n")


def main():
    parser = argparse.ArgumentParser(description="NEXUS macro shock simulation")
    parser.add_argument("--llm",    action="store_true", help="Use real LLM (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--ecb",    action="store_true", help="Use ECB cut shock instead of Fed hike")
    parser.add_argument("--rounds", type=int, default=6,  help="Number of simulation rounds")
    parser.add_argument("--hh",     type=int, default=100, help="Number of household agents")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    shock = ecb_surprise_cut_50bps() if args.ecb else fed_rate_hike_75bps()

    factory = AgentFactory(seed=args.seed)
    agents = factory.build(
        n_households=args.hh,
        n_professional_retail=20,
        n_ordinary_retail=50,
    )

    sim = Simulation(agents=agents, shocks=[shock], num_rounds=args.rounds)
    runner = SimulationRunner(use_llm=args.llm)

    asyncio.run(runner.run(sim, verbose=True))
    build_final_report(sim)


if __name__ == "__main__":
    main()
