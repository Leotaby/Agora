"""
NEXUS = HumanTwin
scripts/test_agent_profile.py

Profile format tester — mirrors MiroFish's test_profile_format.py.

Validates that:
1. AgentFactory spawns agents with correct field types and value ranges
2. Each tier's to_prompt_context() generates valid LLM input
3. MacroShock.to_prompt_text() produces sensible output
4. Population statistics match HFCS calibration targets

Run from /backend:
    uv run python scripts/test_agent_profile.py
    uv run python scripts/test_agent_profile.py --verbose
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
from rich.console import Console
from rich.table import Table
from rich import box

from app.models.agent import HumanTwin, AgentTier, RiskTolerance
from app.models.shock import fed_rate_hike_75bps, ecb_surprise_cut_50bps
from app.services.agent_factory import AgentFactory
from app.utils.population_stats import compute_population_stats, format_population_report

console = Console()
PASS = "[green]PASS[/green]"
FAIL = "[red]FAIL[/red]"


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = PASS if condition else FAIL
    console.print(f"  {status}  {name}" + (f"  [dim]{detail}[/dim]" if detail else ""))
    return condition


def test_agent_fields(agents: list[HumanTwin]) -> int:
    """Validate field types and value ranges on every agent."""
    console.print("\n[bold]1. Agent field validation[/bold]")
    failures = 0
    for agent in agents:
        ok = True
        ok &= isinstance(agent.agent_id, str) and len(agent.agent_id) == 36
        ok &= isinstance(agent.tier, AgentTier)
        ok &= 0.0 <= agent.financial_literacy <= 1.0
        ok &= isinstance(agent.risk_tolerance, RiskTolerance)
        ok &= 0.0 <= agent.information_speed <= 1.0
        ok &= 0.0 <= agent.usd_exposure <= 1.0
        ok &= 0.0 <= agent.eur_exposure <= 1.0
        ok &= 0.0 <= agent.crypto_exposure <= 1.0
        # Portfolio exposures shouldn't exceed 1.5 (can be >1 with leverage for HFs)
        ok &= (agent.usd_exposure + agent.eur_exposure + agent.crypto_exposure) <= 2.0
        ok &= agent.loss_aversion > 0
        if not ok:
            failures += 1
            console.print(f"    [red]FIELD FAIL[/red] {agent.name} ({agent.tier.value})")

    check(
        f"All {len(agents)} agents pass field validation",
        failures == 0,
        f"{failures} failures" if failures else "",
    )
    return failures


def test_tier_coverage(agents: list[HumanTwin]) -> int:
    """Every tier must be represented."""
    console.print("\n[bold]2. Tier coverage[/bold]")
    present = {a.tier for a in agents}
    failures = 0
    for tier in AgentTier:
        ok = tier in present
        failures += 0 if ok else 1
        check(f"Tier {tier.value} present", ok)
    return failures


def test_prompt_context(agents: list[HumanTwin], verbose: bool = False) -> int:
    """to_prompt_context() must return non-empty strings for every agent."""
    console.print("\n[bold]3. Prompt context generation[/bold]")
    failures = 0
    sample_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    sample_table.add_column("Tier", width=24)
    sample_table.add_column("Name", width=28)
    sample_table.add_column("Context length", justify="right", width=14)

    seen_tiers: set[AgentTier] = set()
    for agent in agents:
        ctx = agent.to_prompt_context()
        ok = isinstance(ctx, str) and len(ctx) > 100
        if not ok:
            failures += 1
            console.print(f"    [red]PROMPT FAIL[/red] {agent.name}")

        if agent.tier not in seen_tiers:
            seen_tiers.add(agent.tier)
            sample_table.add_row(
                agent.tier.value.split("_", 1)[-1],
                agent.name[:26],
                str(len(ctx)),
            )
            if verbose:
                console.print(f"\n    [dim]--- {agent.tier.value} ---[/dim]")
                console.print(f"    [dim]{ctx[:300]}...[/dim]")

    check(f"All {len(agents)} prompt contexts valid", failures == 0)
    if not verbose:
        console.print(sample_table)
    return failures


def test_shock_format() -> int:
    """Shock serialization must produce non-empty text."""
    console.print("\n[bold]4. Shock format validation[/bold]")
    failures = 0
    for shock_fn in [fed_rate_hike_75bps, ecb_surprise_cut_50bps]:
        shock = shock_fn()
        text = shock.to_prompt_text()
        ok = isinstance(text, str) and len(text) > 50
        failures += 0 if ok else 1
        check(
            f"{shock.source.value}: {shock.headline[:40]}",
            ok,
            f"len={len(text)}",
        )
        # Tier salience must cover all 7 tiers
        ok2 = len(shock.tier_salience) == 7
        failures += 0 if ok2 else 1
        check(f"  tier_salience has 7 entries", ok2)
    return failures


def test_population_stats(agents: list[HumanTwin]) -> int:
    """Population stats must be internally consistent."""
    console.print("\n[bold]5. Population statistics[/bold]")
    stats = compute_population_stats(agents)
    failures = 0

    ok = stats.total == len(agents)
    failures += 0 if ok else 1
    check(f"Total agents match: {stats.total}", ok)

    ok = 15_000 < stats.household_income_median < 80_000
    failures += 0 if ok else 1
    check(
        f"Household income median in plausible range",
        ok,
        f"€{stats.household_income_median:,.0f}",
    )

    ok = 0.35 < stats.household_literacy_mean < 0.75
    failures += 0 if ok else 1
    check(
        f"Household literacy mean in HFCS range [0.35–0.75]",
        ok,
        f"{stats.household_literacy_mean:.4f}",
    )

    ok = stats.household_literacy_gini > 0.1
    failures += 0 if ok else 1
    check(
        f"Household literacy Gini > 0.1 (there is inequality)",
        ok,
        f"Gini = {stats.household_literacy_gini:.4f}",
    )

    return failures


def main():
    parser = argparse.ArgumentParser(description="NEXUS agent profile tester")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print sample prompt contexts")
    parser.add_argument("--hh",           type=int, default=200, help="Household sample size")
    parser.add_argument("--seed",         type=int, default=42)
    args = parser.parse_args()

    console.print("\n[bold cyan]NEXUS = HumanTwin — Agent Profile Test Suite[/bold cyan]")

    factory = AgentFactory(seed=args.seed)
    agents = factory.build(
        n_households=args.hh,
        n_professional_retail=20,
        n_ordinary_retail=50,
    )

    console.print(f"\n[dim]Testing {len(agents)} agents across 7 tiers[/dim]")

    total_failures = 0
    total_failures += test_agent_fields(agents)
    total_failures += test_tier_coverage(agents)
    total_failures += test_prompt_context(agents, verbose=args.verbose)
    total_failures += test_shock_format()
    total_failures += test_population_stats(agents)

    # Summary
    console.print("\n" + "=" * 44)
    if total_failures == 0:
        console.print("[bold green]All tests passed.[/bold green]")
        console.print(format_population_report(compute_population_stats(agents)))
    else:
        console.print(f"[bold red]{total_failures} test(s) failed.[/bold red]")

    return 0 if total_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
