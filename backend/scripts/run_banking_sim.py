#!/usr/bin/env python3
"""
run_banking_sim.py — Deposit-run shock on UniCredit, trace contagion through the network.

Scenario: Italian sovereign crisis triggers a deposit run on UniCredit.
  - Corporate depositors pull 40% of funds (BTP fears)
  - Wholesale funding market freezes 50% (repo counterparties flee)
  - Italian sovereign bonds marked down 15%
  - CDS spreads blow out +200bps

We trace: which banks survive, which need ECB support, which fail.
"""
import sys
import os

# Allow running from the scripts directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.bank import BankType, BankStatus
from app.models.interbank_network import InterbankNetwork
from app.services.contagion_engine import ContagionEngine, BankingShock


# ── Formatting helpers ────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
DIM = "\033[2m"

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
    print(f"  {'Bank':12s} {'Assets':>8s} {'CET1%':>7s} {'LCR%':>7s} {'Spread':>7s} {'Status':>12s}")
    print(f"  {'─' * 55}")
    for bank in sorted(network.banks.values(), key=lambda b: b.total_assets_eur_bn, reverse=True):
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


# ── Main simulation ──────────────────────────────────────────────

def main():
    print_header("SYSTEMIC RISK SIMULATION: Italian Sovereign / UniCredit Deposit Run")

    # ── Step 1: Build the network ────────────────────────────────
    print(f"\n{BOLD}Step 1: Building interbank network...{RESET}")
    engine = ContagionEngine(seed=42)
    engine.initialize()
    network = InterbankNetwork(banks=engine.banks, exposures=engine.interbank_exposures)
    network.print_network()

    print_bank_table(network, "PRE-SHOCK BALANCE SHEETS")

    # Check solvency/liquidity before shock
    print(f"\n{DIM}  Solvency check (CET1 >= 8%):{RESET}")
    for b in engine.banks.values():
        if b.bank_type == BankType.CENTRAL_BANK:
            continue
        solvent = b.is_solvent()
        liquid = b.is_liquid()
        tag = f"{GREEN}OK{RESET}" if (solvent and liquid) else f"{YELLOW}WATCH{RESET}"
        print(f"    {b.short_name:8s} solvent={solvent}  liquid={liquid}  [{tag}]")

    # ── Step 2: Apply the shock to UniCredit ─────────────────────
    print_header("Step 2: SHOCK — Italian sovereign crisis hits UniCredit")

    shock = BankingShock(
        shock_id="italian_crisis_2026",
        description="Italian sovereign crisis → deposit run on UniCredit",
        target_bank_id="UCG",
        asset_writedown_pct=8.0,             # 8% of loans go bad
        affected_asset="loans",
        deposit_run_pct=40.0,                # 40% of corporate deposits flee
        wholesale_funding_haircut_pct=50.0,  # half of wholesale won't roll
        sovereign_bond_haircut_pct=15.0,     # BTP prices crash 15%
        credit_spread_shock_bps=200.0,       # CDS spreads blow out
        interbank_rate_spike_bps=50.0,       # interbank stress premium
    )

    print(f"\n  {BOLD}Shock parameters:{RESET}")
    print(f"    Target:              UniCredit (UCG)")
    print(f"    Loan writedown:      {shock.asset_writedown_pct}%")
    print(f"    Deposit run:         {shock.deposit_run_pct}% of corporate deposits")
    print(f"    Wholesale freeze:    {shock.wholesale_funding_haircut_pct}%")
    print(f"    Sovereign haircut:   {shock.sovereign_bond_haircut_pct}%")
    print(f"    CDS spread shock:    +{shock.credit_spread_shock_bps:.0f}bps")

    # ── Step 3: Run contagion ────────────────────────────────────
    print_header("Step 3: CONTAGION CASCADE")

    events = engine.process_shock(shock, tick=1)

    # Print events grouped by round
    current_round = -1
    for event in events:
        if event.round_num != current_round:
            current_round = event.round_num
            if current_round == 0:
                print(f"\n  {BOLD}── Initial shock ──{RESET}")
            else:
                print(f"\n  {BOLD}── Contagion round {current_round} ──{RESET}")

        channel_colors = {
            "solvency": RED,
            "liquidity": YELLOW,
            "counterparty": RED,
            "fire_sale": YELLOW,
            "confidence": CYAN,
            "ecb_intervention": GREEN,
            "resolution": RED + BOLD,
        }
        cc = channel_colors.get(event.channel, RESET)
        loss_str = f" (€{event.loss_eur_bn:.2f}bn)" if event.loss_eur_bn > 0 else ""
        print(f"    {cc}[{event.channel:14s}]{RESET} {event.description}{loss_str}")

    # ── Step 4: Results ──────────────────────────────────────────
    print_header("Step 4: AFTERMATH")

    print_bank_table(network, "POST-SHOCK BALANCE SHEETS")

    # Classify outcomes
    survived = []
    ecb_support = []
    failed = []

    for bank in engine.banks.values():
        if bank.bank_type == BankType.CENTRAL_BANK:
            continue
        if bank.status in (BankStatus.FAILED, BankStatus.RESOLUTION):
            failed.append(bank)
        elif bank.status in (BankStatus.STRESSED, BankStatus.CRITICAL):
            ecb_support.append(bank)
        else:
            survived.append(bank)

    print(f"\n{BOLD}  OUTCOME SUMMARY{RESET}")
    print(f"  {'─' * 55}")

    if survived:
        print(f"\n  {GREEN}{BOLD}SURVIVED (no intervention needed):{RESET}")
        for b in survived:
            print(f"    {GREEN}✓{RESET} {b.short_name:8s} CET1={b.cet1_ratio*100:.1f}%  LCR={b.liquidity.lcr_pct:.0f}%")

    if ecb_support:
        print(f"\n  {YELLOW}{BOLD}ECB SUPPORT REQUIRED:{RESET}")
        for b in ecb_support:
            cb_borrow = b.liabilities.cb_borrowing_eur_bn
            print(
                f"    {YELLOW}!{RESET} {b.short_name:8s} CET1={b.cet1_ratio*100:.1f}%  "
                f"LCR={b.liquidity.lcr_pct:.0f}%  "
                f"ECB facility=€{cb_borrow:.1f}bn"
            )

    if failed:
        print(f"\n  {RED}{BOLD}FAILED / IN RESOLUTION:{RESET}")
        for b in failed:
            print(
                f"    {RED}✗{RESET} {b.short_name:8s} CET1={b.cet1_ratio*100:.1f}%  "
                f"LCR={b.liquidity.lcr_pct:.0f}%  "
                f"→ bail-in of creditors"
            )

    # ── System-level metrics ─────────────────────────────────────
    print_header("SYSTEM RISK METRICS")
    summary = engine.system_summary()
    for key, val in summary.items():
        label = key.replace("_", " ").title()
        print(f"    {label:40s} {val}")

    # ── Total losses ─────────────────────────────────────────────
    total_losses = sum(e.loss_eur_bn for e in events if e.loss_eur_bn > 0)
    print(f"\n  {BOLD}Total losses across system: €{total_losses:.1f}bn{RESET}")
    print(f"  {BOLD}Contagion events: {len(events)}{RESET}")
    print(f"  {BOLD}Contagion rounds: {max(e.round_num for e in events) if events else 0}{RESET}")
    print()


if __name__ == "__main__":
    main()
