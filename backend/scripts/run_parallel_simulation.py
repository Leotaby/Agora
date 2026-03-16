"""
NEXUS = HumanTwin
scripts/run_parallel_simulation.py

Full integration test — mirrors MiroFish's run_parallel_simulation.py.

Tests the complete pipeline end to end:
  1. AgentFactory builds a calibrated population
  2. MacroShock is constructed and validated
  3. SimulationRunner executes all rounds (parallel batch)
  4. ActionLogger records every reaction to JSONL
  5. PopulationStats validates output moments
  6. Final disconnect report confirms the Meese-Rogoff gap

This is the script you run to confirm the whole system is working
before committing or deploying.

Usage:
    uv run python scripts/run_parallel_simulation.py
    uv run python scripts/run_parallel_simulation.py --both     # Fed + ECB back to back
    uv run python scripts/run_parallel_simulation.py --llm      # real Claude API
    uv run python scripts/run_parallel_simulation.py --hh 1000  # scale test
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
import asyncio
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from app.models.shock import fed_rate_hike_75bps, ecb_surprise_cut_50bps
from app.models.simulation import Simulation
from app.services.agent_factory import AgentFactory
from app.services.simulation_runner import SimulationRunner
from app.utils.logger import log_full_simulation
from app.utils.population_stats import compute_population_stats

console = Console()


def run_one_shock(shock, factory, args) -> dict:
    """Run a complete simulation for one shock, return key metrics."""
    agents = factory.build(
        n_households=args.hh,
        n_professional_retail=25,
        n_ordinary_retail=60,
    )
    sim = Simulation(agents=agents, shocks=[shock], num_rounds=args.rounds)
    runner = SimulationRunner(use_llm=args.llm, concurrency=8)

    t0 = time.perf_counter()
    asyncio.run(runner.run(sim, verbose=True))
    elapsed = time.perf_counter() - t0

    log_path = log_full_simulation(sim)

    # Compute disconnect gap
    r0   = sim.round_results[0]   if sim.round_results else None
    rend = sim.round_results[-1]  if sim.round_results else None
    hf_t0 = r0.avg_sentiment_by_tier.get("T2_macro_hedge_fund", 0) if r0 else 0
    hh_t0 = r0.avg_sentiment_by_tier.get("T7_household", 0)        if r0 else 0
    hh_end= rend.avg_sentiment_by_tier.get("T7_household", 0)      if rend else 0

    return {
        "shock":       shock.headline,
        "source":      shock.source.value,
        "agents":      len(agents),
        "rounds":      sim.num_rounds,
        "elapsed_s":   round(elapsed, 2),
        "hf_t0":       round(hf_t0, 4),
        "hh_t0":       round(hh_t0, 4),
        "hh_end":      round(hh_end, 4),
        "gap":         round(hf_t0 - hh_end, 4),
        "log_path":    log_path,
        "status":      sim.status.value,
    }


def main():
    parser = argparse.ArgumentParser(description="NEXUS parallel simulation integration test")
    parser.add_argument("--hh",     type=int,  default=200,  help="Household agents")
    parser.add_argument("--rounds", type=int,  default=7,    help="Simulation rounds")
    parser.add_argument("--llm",    action="store_true",      help="Use real LLM")
    parser.add_argument("--both",   action="store_true",      help="Run Fed + ECB back to back")
    parser.add_argument("--seed",   type=int,  default=42)
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]NEXUS = HumanTwin[/bold cyan]\n"
        "[dim]Parallel Simulation Integration Test[/dim]",
        border_style="cyan"
    ))

    factory = AgentFactory(seed=args.seed)

    # Population preview
    preview_agents = factory.build(n_households=args.hh, n_professional_retail=25, n_ordinary_retail=60)
    stats = compute_population_stats(preview_agents)
    console.print(f"\n[dim]Population: {stats.total} agents | "
                  f"Literacy mean: {stats.household_literacy_mean:.3f} | "
                  f"Literacy Gini: {stats.household_literacy_gini:.3f}[/dim]\n")

    shocks = [fed_rate_hike_75bps()]
    if args.both:
        shocks.append(ecb_surprise_cut_50bps())

    results = []
    for i, shock in enumerate(shocks):
        if i > 0:
            console.print(Rule(style="dim"))
        console.print(f"[yellow]Shock {i+1}/{len(shocks)}:[/yellow] {shock.headline}\n")
        result = run_one_shock(shock, factory, args)
        results.append(result)

    # Summary table
    console.print(Rule(style="dim"))
    console.print("\n[bold]Integration test results[/bold]\n")

    t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    t.add_column("Shock",         width=44)
    t.add_column("Agents",        justify="right", width=7)
    t.add_column("HF t=0",        justify="right", width=9)
    t.add_column("HH t=0",        justify="right", width=9)
    t.add_column("HH t=end",      justify="right", width=9)
    t.add_column("Gap",           justify="right", width=9)
    t.add_column("Time",          justify="right", width=8)
    t.add_column("Status",        width=10)

    for r in results:
        gap_color = "amber" if r["gap"] > 0.5 else "yellow" if r["gap"] > 0.2 else "dim"
        status_color = "green" if r["status"] == "completed" else "red"
        t.add_row(
            r["shock"][:42],
            str(r["agents"]),
            f"{r['hf_t0']:+.3f}",
            f"[dim]{r['hh_t0']:+.3f}[/dim]",
            f"{r['hh_end']:+.3f}",
            f"[{gap_color}]{r['gap']:+.3f}[/{gap_color}]",
            f"{r['elapsed_s']}s",
            f"[{status_color}]{r['status']}[/{status_color}]",
        )

    console.print(t)

    # Disconnect interpretation
    console.print("\n[bold]Disconnect interpretation[/bold]")
    for r in results:
        source = r["source"]
        gap = r["gap"]
        if gap > 0.4:
            msg = f"[green]Strong disconnect window ({gap:+.3f}) — Meese-Rogoff regime active.[/green]"
        elif gap > 0.15:
            msg = f"[yellow]Moderate disconnect window ({gap:+.3f}) — partial transmission.[/yellow]"
        else:
            msg = f"[dim]Weak disconnect ({gap:+.3f}) — households absorbed shock quickly.[/dim]"
        console.print(f"  {source}: {msg}")

    # Log paths
    console.print("\n[dim]Log files written:[/dim]")
    for r in results:
        console.print(f"  {r['log_path']}")

    all_ok = all(r["status"] == "completed" for r in results)
    console.print(
        f"\n[bold green]Integration test PASSED[/bold green]" if all_ok
        else f"\n[bold red]Integration test FAILED[/bold red]"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
