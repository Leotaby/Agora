"""
NEXUS = HumanTwin
scripts/action_logger.py

Standalone action logger script — mirrors MiroFish's action_logger.py.

Runs a simulation and writes the full action log to JSONL.
The JSONL output is the raw material for:
  - Panel econometric analysis in Stata/Python
  - Backtesting against real EUR/USD data
  - Generating the synthetic dataset for Paper 1

Usage:
    uv run python scripts/action_logger.py
    uv run python scripts/action_logger.py --hh 500 --rounds 10
    uv run python scripts/action_logger.py --ecb --csv   # also export CSV
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
import asyncio
import csv

from rich.console import Console
from rich.panel import Panel

from app.models.shock import fed_rate_hike_75bps, ecb_surprise_cut_50bps
from app.models.simulation import Simulation
from app.services.agent_factory import AgentFactory
from app.services.simulation_runner import SimulationRunner
from app.utils.logger import log_full_simulation, LOG_DIR
from app.utils.population_stats import compute_population_stats, format_population_report

console = Console()


def export_csv(jsonl_path: str) -> str:
    """Convert the JSONL log to CSV for Stata/Excel."""
    import json
    csv_path = jsonl_path.replace(".jsonl", ".csv")
    rows = []
    with open(jsonl_path) as f:
        for line in f:
            try:
                rows.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    if not rows:
        return ""

    all_keys = list(rows[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def main():
    parser = argparse.ArgumentParser(description="NEXUS action logger")
    parser.add_argument("--hh",     type=int,  default=200,   help="Number of household agents")
    parser.add_argument("--rounds", type=int,  default=8,     help="Simulation rounds")
    parser.add_argument("--ecb",    action="store_true",       help="Use ECB cut shock")
    parser.add_argument("--llm",    action="store_true",       help="Use real LLM calls")
    parser.add_argument("--csv",    action="store_true",       help="Also export CSV")
    parser.add_argument("--seed",   type=int,  default=42)
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]NEXUS = HumanTwin[/bold cyan]\n[dim]Action Logger[/dim]",
        border_style="cyan"
    ))

    # Build population
    shock = ecb_surprise_cut_50bps() if args.ecb else fed_rate_hike_75bps()
    factory = AgentFactory(seed=args.seed)
    agents = factory.build(
        n_households=args.hh,
        n_professional_retail=25,
        n_ordinary_retail=60,
    )

    # Population statistics
    stats = compute_population_stats(agents)
    console.print(format_population_report(stats))

    # Run simulation
    simulation = Simulation(agents=agents, shocks=[shock], num_rounds=args.rounds)
    runner = SimulationRunner(use_llm=args.llm)
    asyncio.run(runner.run(simulation, verbose=True))

    # Log to JSONL
    log_path = log_full_simulation(simulation)
    console.print(f"\n[green]Log written:[/green] {log_path}")

    # Count entries
    with open(log_path) as f:
        n_lines = sum(1 for _ in f)
    console.print(f"  {n_lines} entries ({simulation.num_agents} agents × {args.rounds} rounds + aggregates)")

    # Optional CSV export
    if args.csv:
        csv_path = export_csv(log_path)
        if csv_path:
            console.print(f"[green]CSV exported:[/green] {csv_path}")

    console.print(f"\n[dim]Load in Python:[/dim]")
    console.print(f'  import pandas as pd')
    console.print(f'  df = pd.read_json("{log_path}", lines=True)')
    console.print(f'  df.groupby("tier")["sentiment"].describe()')


if __name__ == "__main__":
    main()
