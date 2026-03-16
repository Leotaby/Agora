"""
THE GOD'S-EYE SIMULATION.

Builds the complete synthetic Earth, injects a geopolitical or financial shock,
and traces its propagation through every layer:
  Institutions → Countries → Political actors → Financial system → Households

Available shocks:
  --fed-hike        Fed raises rates +75bps
  --russia-sanction New SWIFT exclusion applied to Russia
  --oil-cut         OPEC cuts production 10%
  --iran-escalate   Iran nuclear escalation → geopolitical risk spike
  --nk-cyber        North Korea (Lazarus) cyberattack on Western banks
  --argentina-default Argentina sovereign default
  --ecb-cut         ECB emergency rate cut

Run from /backend:
    uv run python scripts/run_world_simulation.py --fed-hike
    uv run python scripts/run_world_simulation.py --russia-sanction
    uv run python scripts/run_world_simulation.py --nk-cyber
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
import asyncio
from datetime import date

from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich.panel import Panel
from rich import box

from app.models.shock import (
    MacroShock, ShockType, ShockSource,
    fed_rate_hike_75bps, ecb_surprise_cut_50bps
)
from app.models.simulation import Simulation
from app.services.world_factory import WorldFactory
from app.services.simulation_runner import SimulationRunner

console = Console()


# ---------------------------------------------------------------------------
# World-specific shocks (beyond the basic FX shocks)
# ---------------------------------------------------------------------------

def shock_russia_new_sanctions() -> MacroShock:
    return MacroShock(
        shock_type=ShockType.SANCTIONS,
        source=ShockSource.FED,  # USA-led
        magnitude_pct=-8.0,
        direction=-1,
        headline="USA + EU expand Russia sanctions: new energy embargo and secondary sanctions",
        description=(
            "The US Treasury and EU Commission announce a new package targeting "
            "Russian LNG exports and imposing secondary sanctions on third-country "
            "entities trading with Russia. Turkey and India face financial penalties "
            "for continued Russian oil imports."
        ),
        forward_guidance="Secondary sanctions enforcement begins in 90 days.",
        primary_currency="RUB",
        secondary_currency="USD",
        tier_salience={
            "T1_central_bank":        1.0,
            "T2_macro_hedge_fund":    0.90,
            "T3_commercial_bank":     0.85,
            "T4_institutional_am":    0.60,
            "T5_professional_retail": 0.50,
            "T6_ordinary_retail":     0.25,
            "T7_household":           0.10,
        },
        tier_delay_rounds={
            "T1_central_bank":        0,
            "T2_macro_hedge_fund":    0,
            "T3_commercial_bank":     0,
            "T4_institutional_am":    1,
            "T5_professional_retail": 1,
            "T6_ordinary_retail":     2,
            "T7_household":           4,
        },
    )


def shock_opec_cut() -> MacroShock:
    return MacroShock(
        shock_type=ShockType.TRADE_WAR,
        source=ShockSource.FED,
        magnitude_pct=15.0,
        direction=1,
        headline="OPEC+ agrees surprise 10% production cut - Brent spikes to $98",
        description=(
            "Saudi Arabia and Russia announce a coordinated 10% production cut effective "
            "next month. Brent crude surges 15% on announcement. Energy inflation "
            "expectations jump across Europe and Asia."
        ),
        forward_guidance="Cut maintained for minimum 6 months.",
        primary_currency="USD",
        secondary_currency="EUR",
        tier_salience={
            "T1_central_bank":        0.95,
            "T2_macro_hedge_fund":    0.85,
            "T3_commercial_bank":     0.65,
            "T4_institutional_am":    0.70,
            "T5_professional_retail": 0.55,
            "T6_ordinary_retail":     0.40,
            "T7_household":           0.30,  # households feel via petrol prices
        },
        tier_delay_rounds={
            "T1_central_bank":        0,
            "T2_macro_hedge_fund":    0,
            "T3_commercial_bank":     1,
            "T4_institutional_am":    1,
            "T5_professional_retail": 1,
            "T6_ordinary_retail":     2,
            "T7_household":           5,  # feel it at fuel pump in 5 weeks
        },
    )


def shock_nk_cyber_attack() -> MacroShock:
    return MacroShock(
        shock_type=ShockType.LIQUIDITY_CRISIS,
        source=ShockSource.MARKET,
        magnitude_bps=-200.0,
        direction=-1,
        headline="Lazarus Group (North Korea) cyberattack disables three major Western banks' payment systems",
        description=(
            "The FBI and CISA confirm a coordinated cyberattack by the Lazarus Group "
            "has disabled payment processing at three major US banks and one European bank. "
            "SWIFT messaging disrupted for 6 hours. $1.2bn in crypto stolen from DeFi bridges."
        ),
        forward_guidance="OFAC imposes new sanctions on DPRK front companies. G7 emergency meeting called.",
        primary_currency="USD",
        secondary_currency="EUR",
        tier_salience={
            "T1_central_bank":        1.0,
            "T2_macro_hedge_fund":    0.95,
            "T3_commercial_bank":     1.0,   # directly hit
            "T4_institutional_am":    0.75,
            "T5_professional_retail": 0.70,
            "T6_ordinary_retail":     0.50,
            "T7_household":           0.20,
        },
        tier_delay_rounds={
            "T1_central_bank":        0,
            "T2_macro_hedge_fund":    0,
            "T3_commercial_bank":     0,
            "T4_institutional_am":    0,
            "T5_professional_retail": 0,
            "T6_ordinary_retail":     1,
            "T7_household":           2,
        },
    )


def shock_argentina_default() -> MacroShock:
    return MacroShock(
        shock_type=ShockType.CURRENCY_CRISIS,
        source=ShockSource.MARKET,
        magnitude_pct=-40.0,
        direction=-1,
        headline="Argentina misses IMF repayment - 9th sovereign default, peso collapses 40%",
        description=(
            "Argentina fails to make a $2.1bn IMF payment. Talks collapse. "
            "The peso collapses 40% overnight. Capital controls tightened. "
            "Contagion spreads to Turkey, Pakistan, and other high-debt EM economies."
        ),
        forward_guidance="IMF emergency team dispatched. New austerity program under negotiation.",
        primary_currency="ARS",
        secondary_currency="USD",
        tier_salience={
            "T1_central_bank":        0.70,
            "T2_macro_hedge_fund":    0.95,
            "T3_commercial_bank":     0.60,
            "T4_institutional_am":    0.75,
            "T5_professional_retail": 0.65,
            "T6_ordinary_retail":     0.45,
            "T7_household":           0.55,  # households directly affected (peso savings)
        },
        tier_delay_rounds={
            "T1_central_bank":        0,
            "T2_macro_hedge_fund":    0,
            "T3_commercial_bank":     1,
            "T4_institutional_am":    1,
            "T5_professional_retail": 1,
            "T6_ordinary_retail":     1,
            "T7_household":           2,  # feel via supermarket prices fast
        },
    )


SHOCK_MENU = {
    "fed_hike":          fed_rate_hike_75bps,
    "ecb_cut":           ecb_surprise_cut_50bps,
    "russia_sanction":   shock_russia_new_sanctions,
    "oil_cut":           shock_opec_cut,
    "nk_cyber":          shock_nk_cyber_attack,
    "argentina_default": shock_argentina_default,
}


# ---------------------------------------------------------------------------
# World state reporter
# ---------------------------------------------------------------------------

def report_world_state(world) -> None:
    console.print(Rule("[bold]World state[/bold]", style="dim"))

    # Sanctions
    table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    table.add_column("Sanctions regime", width=44)
    table.add_column("Targets", width=16)
    table.add_column("SWIFT cut", width=10)
    table.add_column("GDP hit", justify="right", width=10)
    for regime in world.sanctions_regimes:
        if regime.active:
            swift = "[red]YES[/red]" if regime.affects_swift() else "[dim]no[/dim]"
            table.add_row(
                regime.name[:42],
                ", ".join(regime.target_countries),
                swift,
                f"{regime.gdp_impact_annual_pct:.1f}%",
            )
    console.print(table)

    # Key geopolitical risks
    console.print(f"\n[dim]Geopolitical risk index:[/dim] {world.macro.geopolitical_risk_index:.0f}/100")
    console.print(f"[dim]VIX:[/dim] {world.macro.vix:.1f}")
    console.print(f"[dim]USD reserve share:[/dim] {world.macro.usd_reserve_share:.1%}")
    console.print(f"[dim]BTC price:[/dim] ${world.macro.bitcoin_price_usd:,.0f}")

    # Non-state threat landscape
    console.print(f"\n[dim]High-threat non-state actors active:[/dim]")
    from app.models.nonstate_actor import ThreatLevel
    high_threat = [a for a in world.nonstate_actors
                   if a.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL] and a.active]
    for actor in high_threat[:6]:
        console.print(f"  [{actor.threat_level.value}] {actor.name} - {actor.description[:60]}...")


def main():
    parser = argparse.ArgumentParser(description="NEXUS World Simulation")
    for key in SHOCK_MENU:
        parser.add_argument(f"--{key.replace('_', '-')}", action="store_true",
                           help=f"Inject {key} shock")
    parser.add_argument("--hh",     type=int, default=50,  help="Households per major country")
    parser.add_argument("--rounds", type=int, default=6,   help="Simulation rounds")
    parser.add_argument("--no-llm", action="store_true",   help="Use stub reactions instead of real LLM")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    # Determine which shock to use
    selected_shock_key = None
    for key in SHOCK_MENU:
        if getattr(args, key.replace("-", "_"), False):
            selected_shock_key = key
            break
    if not selected_shock_key:
        selected_shock_key = "fed_hike"
        console.print("[dim]No shock specified - defaulting to Fed rate hike[/dim]\n")

    # Build the world
    factory = WorldFactory(seed=args.seed)
    world = factory.build(n_households_per_major_country=args.hh)

    # Show world state
    report_world_state(world)

    # Inject shock
    shock = SHOCK_MENU[selected_shock_key]()
    console.print(f"\n[yellow]SHOCK INJECTED:[/yellow] {shock.headline}\n")

    # Run simulation over the agent population
    simulation = Simulation(
        agents=world.households,
        shocks=[shock],
        num_rounds=args.rounds,
    )
    runner = SimulationRunner(use_llm=not args.no_llm)
    asyncio.run(runner.run(simulation, verbose=True))

    # Post-shock world state update (macro impact)
    console.print(Rule("[bold]Post-shock analysis[/bold]", style="dim"))

    # Identify which countries are most affected
    affected = []
    for iso2 in shock.tier_salience:
        pass  # placeholder - in Phase 1 we trace through country financial linkages

    # Household impact breakdown by country
    from app.models.agent import AgentTier
    households = [a for a in world.households if a.tier == AgentTier.HOUSEHOLD]
    by_country: dict[str, list] = {}
    for hh in households:
        by_country.setdefault(hh.country, []).append(hh)

    if simulation.round_results:
        last_round = simulation.round_results[-1]
        hh_sent = last_round.avg_sentiment_by_tier.get("T7_household", 0.0)
        hf_r0 = simulation.round_results[0].avg_sentiment_by_tier.get("T2_macro_hedge_fund", 0.0)

        console.print(f"\n[bold]Disconnect gap:[/bold]")
        console.print(f"  Hedge funds at t=0:   [green]{hf_r0:+.3f}[/green]")
        console.print(f"  Households at t=end:  [yellow]{hh_sent:+.3f}[/yellow]")
        console.print(f"  Gap:                  [bold]{hf_r0 - hh_sent:+.3f}[/bold]")

    console.print(f"\n[bold]Household countries in simulation:[/bold]")
    for country, hhs in sorted(by_country.items(), key=lambda x: -len(x[1])):
        avg_lit = sum(h.financial_literacy for h in hhs) / len(hhs)
        avg_dol = sum(h.usd_exposure for h in hhs) / len(hhs)
        console.print(f"  {country}  n={len(hhs):<4} literacy={avg_lit:.2f}  USD_exp={avg_dol:.2%}")

    console.print(f"\n[dim]Simulation complete. Status: {simulation.status.value}[/dim]")
    console.print(f"[dim]World: {world}[/dim]")


if __name__ == "__main__":
    main()
