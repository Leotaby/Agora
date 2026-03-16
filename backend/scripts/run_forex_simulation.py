"""
run_forex_simulation.py

THE FIRST RUNNABLE SCRIPT.

Spawns a small population of agents across all 7 tiers,
injects a Fed rate hike shock, and prints each tier's reaction.
No LLM calls yet - this validates the data model and population generator.

Run from /backend:
    uv run python scripts/run_forex_simulation.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from app.models.agent import HumanTwin, AgentTier, RiskTolerance
from app.models.shock import MacroShock, fed_rate_hike_75bps
from app.models.simulation import Simulation, AgentReaction, RoundResult

console = Console()

# ---- Population factory ----

def make_central_bank(country: str = "US") -> HumanTwin:
    return HumanTwin(
        name=f"Central Bank of {country}",
        tier=AgentTier.CENTRAL_BANK,
        country=country,
        financial_literacy=1.0,
        risk_tolerance=RiskTolerance.VERY_LOW,
        information_speed=1.0,
        usd_exposure=1.0,
        eur_exposure=0.0,
        media_exposure="fed_wire",
    )

def make_macro_hf(name: str = "GlobalMacro Fund A") -> HumanTwin:
    return HumanTwin(
        name=name,
        tier=AgentTier.MACRO_HEDGE_FUND,
        country="US",
        income_annual_eur=5_000_000,
        net_wealth_eur=500_000_000,
        financial_literacy=0.98,
        risk_tolerance=RiskTolerance.HIGH,
        loss_aversion=1.1,
        information_speed=0.95,
        usd_exposure=0.4,
        eur_exposure=0.2,
        equity_exposure=0.3,
        media_exposure="bloomberg_terminal",
    )

def make_commercial_bank() -> HumanTwin:
    return HumanTwin(
        name="FX Desk - Major Bank",
        tier=AgentTier.COMMERCIAL_BANK,
        country="US",
        financial_literacy=0.97,
        risk_tolerance=RiskTolerance.MEDIUM,
        information_speed=0.90,
        media_exposure="interbank_feed",
    )

def make_institutional_am() -> HumanTwin:
    return HumanTwin(
        name="European Pension Fund",
        tier=AgentTier.INSTITUTIONAL_AM,
        country="DE",
        income_annual_eur=0,
        net_wealth_eur=50_000_000_000,
        financial_literacy=0.92,
        risk_tolerance=RiskTolerance.LOW,
        information_speed=0.70,
        usd_exposure=0.35,
        eur_exposure=0.55,
        media_exposure="bloomberg_terminal",
    )

def make_professional_retail(rng: random.Random) -> HumanTwin:
    return HumanTwin(
        name=f"Pro Trader #{rng.randint(1000,9999)}",
        tier=AgentTier.PROFESSIONAL_RETAIL,
        country=rng.choice(["IT", "DE", "FR", "ES", "GB"]),
        income_annual_eur=rng.uniform(40_000, 120_000),
        net_wealth_eur=rng.uniform(50_000, 500_000),
        financial_literacy=rng.uniform(0.65, 0.85),
        risk_tolerance=rng.choice([RiskTolerance.HIGH, RiskTolerance.VERY_HIGH]),
        information_speed=rng.uniform(0.55, 0.70),
        usd_exposure=rng.uniform(0.1, 0.5),
        eur_exposure=rng.uniform(0.2, 0.6),
        media_exposure="twitter_and_charts",
    )

def make_ordinary_retail(rng: random.Random) -> HumanTwin:
    return HumanTwin(
        name=f"Retail Trader #{rng.randint(10000,99999)}",
        tier=AgentTier.ORDINARY_RETAIL,
        country=rng.choice(["IT", "DE", "FR", "ES", "RO", "PL"]),
        income_annual_eur=rng.uniform(20_000, 60_000),
        net_wealth_eur=rng.uniform(2_000, 30_000),
        financial_literacy=rng.uniform(0.15, 0.45),
        risk_tolerance=rng.choice([RiskTolerance.HIGH, RiskTolerance.VERY_HIGH]),
        loss_aversion=rng.uniform(2.0, 3.5),
        information_speed=rng.uniform(0.30, 0.50),
        usd_exposure=rng.uniform(0.0, 0.3),
        eur_exposure=rng.uniform(0.4, 0.9),
        media_exposure="tiktok_and_reddit",
    )

def make_household(rng: random.Random) -> HumanTwin:
    literacy = rng.betavariate(2, 4)  # Right-skewed: most households have low literacy
    return HumanTwin(
        name=f"Household #{rng.randint(100000, 999999)}",
        tier=AgentTier.HOUSEHOLD,
        country=rng.choice(["IT", "DE", "FR", "ES", "NL", "BE", "PT", "GR"]),
        age=rng.randint(25, 70),
        income_annual_eur=rng.lognormvariate(10.3, 0.5),   # ~€30k median
        net_wealth_eur=max(0, rng.lognormvariate(10.5, 1.2)),
        debt_eur=rng.uniform(0, 150_000),
        financial_literacy=round(literacy, 3),
        risk_tolerance=(
            RiskTolerance.VERY_LOW if literacy < 0.25 else
            RiskTolerance.LOW      if literacy < 0.45 else
            RiskTolerance.MEDIUM   if literacy < 0.65 else
            RiskTolerance.HIGH
        ),
        loss_aversion=rng.uniform(1.5, 4.0),
        information_speed=literacy * 0.2,   # households are SLOW - max 20% speed
        usd_exposure=rng.uniform(0.0, 0.1),
        eur_exposure=rng.uniform(0.7, 1.0),
        crypto_exposure=rng.uniform(0.0, 0.05),
        social_influence=rng.uniform(0.4, 0.9),
        media_exposure=rng.choice(["tv_news", "newspaper", "word_of_mouth", "social_media"]),
    )


def build_population(n_households: int = 20, seed: int = 42) -> list[HumanTwin]:
    rng = random.Random(seed)
    agents: list[HumanTwin] = []

    # Tier 1 - 2 central banks
    agents.append(make_central_bank("US"))
    agents.append(make_central_bank("EU"))

    # Tier 2 - 3 hedge funds
    for name in ["GlobalMacro Fund A", "EM Macro Partners", "Systematic Alpha"]:
        agents.append(make_macro_hf(name))

    # Tier 3 - 2 commercial banks
    for _ in range(2):
        agents.append(make_commercial_bank())

    # Tier 4 - 2 institutional AMs
    for _ in range(2):
        agents.append(make_institutional_am())

    # Tier 5 - 5 professional retail
    for _ in range(5):
        agents.append(make_professional_retail(rng))

    # Tier 6 - 10 ordinary retail
    for _ in range(10):
        agents.append(make_ordinary_retail(rng))

    # Tier 7 - N households
    for _ in range(n_households):
        agents.append(make_household(rng))

    return agents


def simulate_tier_reaction(agent: HumanTwin, shock: MacroShock, round_num: int) -> AgentReaction:
    """
    STUB: deterministic reaction logic (no LLM yet).
    Next step: replace this with an actual LLM call using agent.to_prompt_context() + shock.to_prompt_text()
    """
    salience = shock.tier_salience.get(agent.tier.value, 0.5)
    delay = shock.tier_delay_rounds.get(agent.tier.value, 0)

    if round_num < delay:
        return AgentReaction(
            agent_id=agent.agent_id,
            tier=agent.tier,
            round_num=round_num,
            shock_id=shock.shock_id,
            reasoning="Shock not yet received (processing delay)",
            action="hold",
            usd_delta=0.0,
            sentiment=0.0,
        )

    # Simple rule-based stub: hawks buy USD proportional to salience and literacy
    if shock.direction > 0:  # hawkish shock (rate hike)
        base_sentiment = salience * agent.financial_literacy
        usd_delta = base_sentiment * 0.1 * (1 - agent.loss_aversion / 10)
    else:
        base_sentiment = -salience * agent.financial_literacy
        usd_delta = base_sentiment * 0.1

    action = (
        "buy USD aggressively" if usd_delta > 0.05 else
        "buy USD cautiously"   if usd_delta > 0.01 else
        "hold"                 if abs(usd_delta) < 0.01 else
        "reduce USD exposure"
    )

    return AgentReaction(
        agent_id=agent.agent_id,
        tier=agent.tier,
        round_num=round_num,
        shock_id=shock.shock_id,
        reasoning=f"[STUB] Salience={salience:.2f}, Literacy={agent.financial_literacy:.2f}",
        action=action,
        usd_delta=round(usd_delta, 4),
        sentiment=round(base_sentiment, 4),
    )


def main():
    console.print(Panel.fit(
        "[bold cyan]NEXUS = HumanTwin[/bold cyan]\n"
        "[dim]First forex simulation - population validation run[/dim]",
        border_style="cyan"
    ))

    # Build population
    console.print("\n[green]Building agent population...[/green]")
    agents = build_population(n_households=20, seed=42)
    console.print(f"  Spawned [bold]{len(agents)}[/bold] agents across 7 tiers\n")

    # Create shock
    shock = fed_rate_hike_75bps()
    console.print(f"[yellow]Shock injected:[/yellow] {shock.headline}\n")

    # Run 3 rounds
    simulation = Simulation(agents=agents, shocks=[shock], num_rounds=3)
    simulation.status = simulation.status.__class__.RUNNING

    for round_num in range(3):
        console.print(f"[bold]--- Round {round_num} ---[/bold]")
        reactions = [simulate_tier_reaction(a, shock, round_num) for a in agents]
        result = RoundResult(round_num=round_num, shock_id=shock.shock_id, reactions=reactions)
        result.compute_aggregates()
        simulation.round_results.append(result)

        # Print tier summary table
        table = Table(show_header=True, header_style="bold dim")
        table.add_column("Tier", style="dim", width=22)
        table.add_column("Agents", justify="right", width=6)
        table.add_column("Avg sentiment", justify="right", width=14)
        table.add_column("Dominant action", width=25)

        tier_actions: dict[str, list[str]] = {}
        for r in reactions:
            tier_actions.setdefault(r.tier.value, []).append(r.action)

        for tier, sentiment in result.avg_sentiment_by_tier.items():
            actions = tier_actions.get(tier, [])
            from collections import Counter
            dominant = Counter(actions).most_common(1)[0][0] if actions else "—"
            color = "green" if sentiment > 0.1 else "red" if sentiment < -0.1 else "white"
            table.add_row(
                tier.split("_", 1)[-1],
                str(len(actions)),
                f"[{color}]{sentiment:+.3f}[/{color}]",
                dominant,
            )
        console.print(table)

    console.print("\n[bold green]Simulation complete.[/bold green]")
    console.print(f"  {simulation}")
    console.print("\n[dim]Next step: replace simulate_tier_reaction() stub with LLM calls[/dim]")


if __name__ == "__main__":
    main()
