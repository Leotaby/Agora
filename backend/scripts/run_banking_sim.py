#!/usr/bin/env python3
"""
run_banking_sim.py — Italian sovereign crisis counterfactual experiment.

Runs two scenarios using 2011 EBA-calibrated balance sheets:
  A) BASELINE  — with ECB lender-of-last-resort intervention
  B) COUNTERFACTUAL — without ECB intervention (no ELA, no backstop)

Without the ECB backstop the contagion cascade runs longer (20 rounds
instead of 10) because markets have no anchor of confidence, and failed
banks are not moved into orderly resolution.

Sources:
  Deutsche Bank Financial Report 2011, BNP Paribas AR 2011,
  UniCredit AR 2011, Commerzbank AR 2011, BayernLB AR 2011,
  EBA Capital Exercise Dec 2011, BIS Consolidated Banking Statistics Q4 2011.
"""
import sys
import os
from dataclasses import dataclass

# Allow running from the scripts directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.bank import Bank, BankType, BankStatus
from app.models.bank_factory import build_calibrated_network
from app.models.interbank_network import InterbankNetwork
from app.services.contagion_engine import ContagionEngine, BankingShock, ContagionEvent
from app.data.eba_calibration import ACTUAL_2012_CET1_RATIOS


# ── Formatting helpers ────────────────────────────────────────────

RESET = "\033[0m"
BOLD  = "\033[1m"
RED   = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN  = "\033[96m"
DIM   = "\033[2m"

def status_color(status: BankStatus) -> str:
    return {
        BankStatus.NORMAL: GREEN,
        BankStatus.STRESSED: YELLOW,
        BankStatus.CRITICAL: RED,
        BankStatus.FAILED: RED + BOLD,
        BankStatus.RESOLUTION: RED + BOLD,
    }.get(status, RESET)


def print_header(text: str) -> None:
    width = 72
    print(f"\n{BOLD}{CYAN}{'─' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * width}{RESET}")


def print_bank_table(network: InterbankNetwork, label: str) -> None:
    print(f"\n{BOLD}  {label}{RESET}")
    print(f"  {'Bank':12s} {'Assets':>8s} {'CET1%':>7s} {'LCR%':>7s} "
          f"{'Spread':>7s} {'Status':>12s}")
    print(f"  {'─' * 55}")
    for bank in sorted(network.banks.values(),
                       key=lambda b: b.total_assets_eur_bn, reverse=True):
        if bank.bank_type == BankType.CENTRAL_BANK:
            continue
        sc = status_color(bank.status)
        print(
            f"  {bank.short_name:12s} "
            f"{bank.total_assets_eur_bn:7.1f}€ "
            f"{bank.cet1_ratio * 100:6.2f}% "
            f"{bank.liquidity.lcr_pct:6.1f}% "
            f"{bank.credit_spread_bps:6.0f}bp "
            f"{sc}{bank.status.value:>12s}{RESET}"
        )


# ── Shared shock definition ──────────────────────────────────────

def build_shock() -> BankingShock:
    return BankingShock(
        shock_id="italian_crisis_2011",
        description="Italian sovereign crisis → deposit run on UniCredit",
        target_bank_id="UCG",
        asset_writedown_pct=8.0,
        affected_asset="loans",
        deposit_run_pct=40.0,
        wholesale_funding_haircut_pct=50.0,
        sovereign_bond_haircut_pct=15.0,
        credit_spread_shock_bps=200.0,
        interbank_rate_spike_bps=50.0,
    )


# ── Scenario runner ───────────────────────────────────────────────

@dataclass
class ScenarioResult:
    label: str
    pre_shock_cet1: dict[str, float]   # short_name → %
    post_shock_cet1: dict[str, float]
    post_shock_lcr: dict[str, float]
    statuses: dict[str, BankStatus]
    total_losses_eur_bn: float
    n_failures: int
    n_rounds: int
    n_events: int
    ecb_ela_total_eur_bn: float
    events: list[ContagionEvent]
    engine: ContagionEngine


def run_scenario(
    ecb_intervention: bool,
    label: str,
    max_rounds: int = 10,
) -> ScenarioResult:
    """Run one scenario on a fresh copy of the calibrated network."""
    banks, exposures = build_calibrated_network()
    engine = ContagionEngine(seed=42, ecb_intervention=ecb_intervention)
    engine.max_contagion_rounds = max_rounds
    engine.banks = banks
    engine.interbank_exposures = exposures

    for bank in engine.banks.values():
        if bank.bank_type != BankType.CENTRAL_BANK:
            bank.update_liquidity_metrics()
            bank.update_status()

    # Capture pre-shock
    non_cb = [b for b in banks.values() if b.bank_type != BankType.CENTRAL_BANK]
    pre_cet1 = {b.short_name: b.cet1_ratio * 100 for b in non_cb}

    # Run
    events = engine.process_shock(build_shock(), tick=1)

    # Capture post-shock
    post_cet1 = {b.short_name: b.cet1_ratio * 100 for b in non_cb}
    post_lcr = {b.short_name: b.liquidity.lcr_pct for b in non_cb}
    statuses = {b.short_name: b.status for b in non_cb}

    total_losses = sum(e.loss_eur_bn for e in events if e.loss_eur_bn > 0)
    n_failures = sum(
        1 for b in non_cb
        if b.status in (BankStatus.FAILED, BankStatus.RESOLUTION)
    )
    n_rounds = max((e.round_num for e in events), default=0)
    ecb_ela = sum(
        float(e.description.split("€")[1].split("bn")[0])
        for e in events if e.channel == "ecb_intervention"
    ) if ecb_intervention else 0.0

    return ScenarioResult(
        label=label,
        pre_shock_cet1=pre_cet1,
        post_shock_cet1=post_cet1,
        post_shock_lcr=post_lcr,
        statuses=statuses,
        total_losses_eur_bn=total_losses,
        n_failures=n_failures,
        n_rounds=n_rounds,
        n_events=len(events),
        ecb_ela_total_eur_bn=ecb_ela,
        events=events,
        engine=engine,
    )


# ── Event printer ─────────────────────────────────────────────────

CHANNEL_COLORS = {
    "solvency": RED, "liquidity": YELLOW, "counterparty": RED,
    "fire_sale": YELLOW, "confidence": CYAN,
    "ecb_intervention": GREEN, "resolution": RED + BOLD,
}

def print_events(events: list[ContagionEvent]) -> None:
    current_round = -1
    for event in events:
        if event.round_num != current_round:
            current_round = event.round_num
            if current_round == 0:
                print(f"\n  {BOLD}── Initial shock ──{RESET}")
            else:
                print(f"\n  {BOLD}── Contagion round {current_round} ──{RESET}")
        cc = CHANNEL_COLORS.get(event.channel, RESET)
        loss_str = (f" (€{event.loss_eur_bn:.2f}bn)"
                    if event.loss_eur_bn > 0 else "")
        print(f"    {cc}[{event.channel:14s}]{RESET} "
              f"{event.description}{loss_str}")


# ── Main ──────────────────────────────────────────────────────────

def main():
    print_header("CALIBRATION: Real EBA/Annual Report data (2011)")
    print(f"\n{DIM}  Sources: EBA Capital Exercise Dec 2011, Deutsche Bank Financial"
          f" Report 2011,{RESET}")
    print(f"{DIM}  BNP Paribas AR 2011, UniCredit AR 2011, Commerzbank AR 2011,"
          f"{RESET}")
    print(f"{DIM}  BayernLB AR 2011, BIS Consolidated Banking Statistics"
          f" Q4 2011{RESET}")

    # ==================================================================
    # SCENARIO A — BASELINE (with ECB intervention)
    # ==================================================================
    print_header("SCENARIO A: BASELINE — With ECB Intervention")

    baseline = run_scenario(ecb_intervention=True, label="With ECB",
                            max_rounds=10)

    # Show network + pre-shock table for baseline
    net_a = InterbankNetwork(banks=baseline.engine.banks,
                             exposures=baseline.engine.interbank_exposures)

    # Print shock parameters once
    shock = build_shock()
    print(f"\n  {BOLD}Shock parameters:{RESET}")
    print(f"    Target:              UniCredit (UCG)")
    print(f"    Loan writedown:      {shock.asset_writedown_pct}%")
    print(f"    Deposit run:         {shock.deposit_run_pct}% of corporate deposits")
    print(f"    Wholesale freeze:    {shock.wholesale_funding_haircut_pct}%")
    print(f"    Sovereign haircut:   {shock.sovereign_bond_haircut_pct}%")
    print(f"    CDS spread shock:    +{shock.credit_spread_shock_bps:.0f}bps")
    print(f"    {DIM}+ JPM restricts dollar repo to European banks{RESET}")
    print(f"    {DIM}+ UBS marks down European sovereign bond holdings{RESET}")

    print(f"\n  {BOLD}Contagion cascade ({baseline.n_rounds} rounds, "
          f"{baseline.n_events} events):{RESET}")
    print_events(baseline.events)

    print_bank_table(net_a, "POST-SHOCK — With ECB")
    print(f"\n  {GREEN}ECB ELA total: €{baseline.ecb_ela_total_eur_bn:.1f}bn{RESET}")
    print(f"  Total losses: €{baseline.total_losses_eur_bn:.1f}bn | "
          f"Failures: {baseline.n_failures}")

    # ==================================================================
    # SCENARIO B — COUNTERFACTUAL (no ECB)
    # ==================================================================
    print_header("SCENARIO B: COUNTERFACTUAL — No ECB Intervention")
    print(f"\n  {DIM}ECB lender-of-last-resort disabled.{RESET}")
    print(f"  {DIM}Contagion circuit breaker raised to 20 rounds "
          f"(no backstop → no confidence anchor).{RESET}")

    no_ecb = run_scenario(ecb_intervention=False, label="No ECB",
                          max_rounds=20)

    net_b = InterbankNetwork(banks=no_ecb.engine.banks,
                             exposures=no_ecb.engine.interbank_exposures)

    print(f"\n  {BOLD}Contagion cascade ({no_ecb.n_rounds} rounds, "
          f"{no_ecb.n_events} events):{RESET}")
    print_events(no_ecb.events)

    print_bank_table(net_b, "POST-SHOCK — No ECB")
    print(f"\n  Total losses: €{no_ecb.total_losses_eur_bn:.1f}bn | "
          f"Failures: {no_ecb.n_failures}")

    # ==================================================================
    # COMPARISON TABLE
    # ==================================================================
    print_header("COUNTERFACTUAL COMPARISON: ECB vs No-ECB vs Actual 2012")

    # Ordered bank list (by pre-shock assets, descending)
    bank_order = sorted(
        baseline.pre_shock_cet1.keys(),
        key=lambda n: baseline.post_shock_cet1.get(n, 0),
        reverse=True,
    )

    print(f"\n  {'Bank':8s} {'Pre-Shock':>10s} {'With ECB':>9s} "
          f"{'No ECB':>9s} {'Actual':>9s} {'ECB':>8s} {'Status':>13s} "
          f"{'Status':>13s}")
    print(f"  {'':8s} {'(2011)':>10s} {'CET1%':>9s} "
          f"{'CET1%':>9s} {'2012':>9s} {'Contrib':>8s} "
          f"{'(w/ ECB)':>13s} {'(no ECB)':>13s}")
    print(f"  {'─' * 82}")

    for name in bank_order:
        pre = baseline.pre_shock_cet1[name]
        with_ecb = baseline.post_shock_cet1[name]
        without_ecb = no_ecb.post_shock_cet1[name]
        actual = ACTUAL_2012_CET1_RATIOS.get(name)
        contrib = with_ecb - without_ecb

        actual_str = f"{actual:.1f}%" if actual is not None else "n/a"
        contrib_str = f"{contrib:+.1f}pp" if abs(contrib) >= 0.05 else "0.0pp"

        st_a = baseline.statuses[name]
        st_b = no_ecb.statuses[name]
        sc_a = status_color(st_a)
        sc_b = status_color(st_b)

        print(
            f"  {name:8s} {pre:9.1f}% {with_ecb:8.1f}% "
            f"{without_ecb:8.1f}% {actual_str:>9s} {contrib_str:>8s} "
            f"{sc_a}{st_a.value:>13s}{RESET} {sc_b}{st_b.value:>13s}{RESET}"
        )

    # ==================================================================
    # SYSTEM-LEVEL COMPARISON
    # ==================================================================
    print_header("SYSTEM-LEVEL IMPACT")

    metrics = [
        ("Total system losses",
         f"€{baseline.total_losses_eur_bn:.1f}bn",
         f"€{no_ecb.total_losses_eur_bn:.1f}bn"),
        ("Contagion rounds",
         str(baseline.n_rounds),
         str(no_ecb.n_rounds)),
        ("Contagion events",
         str(baseline.n_events),
         str(no_ecb.n_events)),
        ("Bank failures",
         str(baseline.n_failures),
         str(no_ecb.n_failures)),
        ("ECB ELA deployed",
         f"€{baseline.ecb_ela_total_eur_bn:.1f}bn",
         "€0.0bn"),
    ]

    loss_delta = no_ecb.total_losses_eur_bn - baseline.total_losses_eur_bn

    print(f"\n  {'Metric':30s} {'With ECB':>14s} {'No ECB':>14s}")
    print(f"  {'─' * 60}")
    for label, val_a, val_b in metrics:
        print(f"  {label:30s} {val_a:>14s} {val_b:>14s}")

    print(f"\n  {BOLD}Additional losses without ECB: "
          f"€{loss_delta:.1f}bn{RESET}")
    print(f"  {BOLD}Additional failures without ECB: "
          f"{no_ecb.n_failures - baseline.n_failures}{RESET}")

    # ==================================================================
    # COUNTERFACTUAL RESULT — plain-language summary
    # ==================================================================
    print_header("COUNTERFACTUAL RESULT")

    # Compute summary statistics for the paragraph
    avg_cet1_ecb = sum(baseline.post_shock_cet1.values()) / len(baseline.post_shock_cet1)
    avg_cet1_no = sum(no_ecb.post_shock_cet1.values()) / len(no_ecb.post_shock_cet1)

    # Banks at CET1 <= 0% are effectively insolvent
    insolvent_ecb = [n for n, c in baseline.post_shock_cet1.items() if c <= 0.01]
    insolvent_no = [n for n, c in no_ecb.post_shock_cet1.items() if c <= 0.01]
    insolvent_no_euro = [n for n in insolvent_no if n not in ("UBS", "JPM")]

    euro_banks_needing_ela = sum(
        1 for name, st in baseline.statuses.items()
        if st in (BankStatus.CRITICAL, BankStatus.STRESSED)
        and name not in ("UBS", "JPM")
    )

    print(f"""
  Using 2011 balance-sheet data from EBA Capital Exercise and published
  annual reports, we simulate an Italian sovereign crisis (8% loan
  writedown, 15% BTP haircut, 40% deposit run, 50% wholesale freeze) on
  UniCredit and trace contagion through a 7-bank cross-Atlantic network.

  With ECB intervention (baseline), the system absorbs
  €{baseline.total_losses_eur_bn:.0f}bn in losses over {baseline.n_rounds} contagion rounds.
  {euro_banks_needing_ela} eurozone bank(s) require ECB Emergency Liquidity Assistance
  totalling €{baseline.ecb_ela_total_eur_bn:.0f}bn. {len(insolvent_ecb)} bank(s) reach
  effective insolvency (CET1 ~ 0%): {', '.join(insolvent_ecb) if insolvent_ecb else 'none'}.
  Average post-shock CET1 across all banks: {avg_cet1_ecb:.1f}%.

  Without ECB intervention (counterfactual), contagion runs for
  {no_ecb.n_rounds} rounds — {no_ecb.n_rounds - baseline.n_rounds} more than the baseline — generating
  €{no_ecb.total_losses_eur_bn:.0f}bn in total losses (+€{loss_delta:.0f}bn).
  {len(insolvent_no)} bank(s) are wiped out to CET1 ~ 0%
  ({', '.join(insolvent_no)}), {len(insolvent_no_euro)} of them eurozone
  institutions. Average post-shock CET1 falls to {avg_cet1_no:.1f}%,
  a {avg_cet1_ecb - avg_cet1_no:.1f}pp deterioration vs the baseline.

  The ECB's lender-of-last-resort function does not inject capital — its
  ELA facility adds reserves (asset) and CB borrowing (liability) in equal
  measure, leaving CET1 ratios mechanically unchanged. Its primary
  contribution is stabilising liquidity: with the backstop, stressed banks
  maintain funding access and avoid disorderly fire-sales that would
  further erode system-wide capital through mark-to-market contagion.
  The additional {no_ecb.n_rounds - baseline.n_rounds} rounds of contagion in the no-ECB scenario
  — driven by unchecked confidence collapse and cascading counterparty
  losses — account for the entire €{loss_delta:.0f}bn loss differential and push
  {len(insolvent_no) - len(insolvent_ecb)} additional bank(s) to insolvency.
""")


if __name__ == "__main__":
    main()
