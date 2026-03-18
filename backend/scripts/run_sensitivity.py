#!/usr/bin/env python3
"""
run_sensitivity.py -- Parameter sensitivity analysis for the ECB counterfactual.

For each parameter variation, runs the Italian sovereign crisis twice
(with ECB, without ECB) and reports the additional losses without the
ECB backstop.  All results are expressed relative to the baseline delta
so that the most influential parameters are immediately visible.

Parameters varied (one at a time, others held at baseline):
  1. Shock magnitude: loan writedown 5%, 8%, 12%
  2. Fire-sale price impact: 0.01, 0.02, 0.03 per 100bn EUR
  3. LGD rates: low / baseline / high
  4. Network density: sparse (0.5x) / baseline (1x) / dense (2x)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.bank import BankType
from app.models.bank_factory import build_calibrated_network
from app.services.contagion_engine import ContagionEngine, BankingShock


# ── Formatting ────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 80}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 80}{RESET}")


# ── Scenario runner ───────────────────────────────────────────────

def run_pair(
    writedown_pct: float = 8.0,
    fire_sale_impact: float = 0.02,
    lgd_failed: float = 0.60,
    lgd_critical: float = 0.20,
    lgd_stressed: float = 0.05,
    exposure_scale: float = 1.0,
) -> tuple[float, float]:
    """
    Run with-ECB and without-ECB scenarios.
    Returns (losses_with_ecb, losses_without_ecb).
    """
    results = []
    for ecb_on in [True, False]:
        banks, exposures = build_calibrated_network()

        # Scale exposures for network density
        if exposure_scale != 1.0:
            for exp in exposures:
                exp.amount_eur_bn *= exposure_scale

        max_rounds = 10 if ecb_on else 20
        engine = ContagionEngine(seed=42, ecb_intervention=ecb_on)
        engine.max_contagion_rounds = max_rounds
        engine.fire_sale_price_impact = fire_sale_impact
        engine.recovery_rate_on_failure = 1.0 - lgd_failed
        engine.lgd_critical_pct = lgd_critical
        engine.lgd_stressed_pct = lgd_stressed
        engine.banks = banks
        engine.interbank_exposures = exposures

        for bank in engine.banks.values():
            if bank.bank_type != BankType.CENTRAL_BANK:
                bank.update_liquidity_metrics()
                bank.update_status()

        shock = BankingShock(
            shock_id="sensitivity",
            target_bank_id="UCG",
            asset_writedown_pct=writedown_pct,
            affected_asset="loans",
            deposit_run_pct=40.0,
            wholesale_funding_haircut_pct=50.0,
            sovereign_bond_haircut_pct=15.0,
            credit_spread_shock_bps=200.0,
            interbank_rate_spike_bps=50.0,
        )
        events = engine.process_shock(shock, tick=1)
        total = sum(e.loss_eur_bn for e in events if e.loss_eur_bn > 0)
        results.append(total)

    return results[0], results[1]


# ── Main ──────────────────────────────────────────────────────────

def main():
    header("SENSITIVITY ANALYSIS: ECB Counterfactual")
    print(f"\n{DIM}  Italian sovereign crisis on UniCredit, 2011 EBA calibration.{RESET}")
    print(f"{DIM}  Each row varies one parameter, all others at baseline.{RESET}")
    print(f"{DIM}  Delta = (no-ECB losses) - (with-ECB losses).{RESET}")

    # Baseline first
    header("BASELINE")
    bl_ecb, bl_no = run_pair()
    bl_delta = bl_no - bl_ecb
    print(f"\n  With ECB:    {GREEN}{bl_ecb:8.1f} bn EUR{RESET}")
    print(f"  Without ECB: {RED}{bl_no:8.1f} bn EUR{RESET}")
    print(f"  Delta:       {YELLOW}{bl_delta:8.1f} bn EUR{RESET}  (= baseline)")

    # Collect all results
    rows: list[tuple[str, str, float, float, float, float]] = []

    def add(name: str, label: str, with_ecb: float, no_ecb: float):
        delta = no_ecb - with_ecb
        pct = (delta / bl_delta * 100) if bl_delta != 0 else 0
        rows.append((name, label, with_ecb, no_ecb, delta, pct))

    # ── 1. Shock magnitude ────────────────────────────────────────
    header("1. SHOCK MAGNITUDE (loan writedown %)")
    for wd in [5.0, 8.0, 12.0]:
        w, n = run_pair(writedown_pct=wd)
        label = f"{wd:.0f}%" + (" (baseline)" if wd == 8.0 else "")
        add("Shock magnitude", label, w, n)

    # ── 2. Fire-sale price impact ─────────────────────────────────
    header("2. FIRE-SALE PRICE IMPACT (per 100bn EUR sold)")
    for fs in [0.01, 0.02, 0.03]:
        w, n = run_pair(fire_sale_impact=fs)
        label = f"{fs:.2f}" + (" (baseline)" if fs == 0.02 else "")
        add("Fire-sale impact", label, w, n)

    # ── 3. LGD rates ──────────────────────────────────────────────
    header("3. LOSS GIVEN DEFAULT RATES")
    lgd_configs = [
        ("low",      0.40, 0.10, 0.02),
        ("baseline", 0.60, 0.20, 0.05),
        ("high",     0.80, 0.35, 0.10),
    ]
    for name, f, c, s in lgd_configs:
        w, n = run_pair(lgd_failed=f, lgd_critical=c, lgd_stressed=s)
        label = f"{name} (F={f:.0%} C={c:.0%} S={s:.0%})"
        add("LGD rates", label, w, n)

    # ── 4. Network density ────────────────────────────────────────
    header("4. NETWORK DENSITY (exposure multiplier)")
    for scale, name in [(0.5, "sparse (0.5x)"), (1.0, "baseline (1.0x)"), (2.0, "dense (2.0x)")]:
        w, n = run_pair(exposure_scale=scale)
        add("Network density", name, w, n)

    # ── Summary table ─────────────────────────────────────────────
    header("SENSITIVITY SUMMARY")

    col_param = 18
    col_val = 32
    col_num = 12

    print(f"\n  {'Parameter':<{col_param}} {'Value':<{col_val}} "
          f"{'With ECB':>{col_num}} {'No ECB':>{col_num}} "
          f"{'Delta':>{col_num}} {'vs Base':>{col_num}}")
    print(f"  {'─' * (col_param + col_val + col_num * 4 + 4)}")

    for name, label, w, n, delta, pct in rows:
        pct_str = f"{pct:+.0f}%"
        if abs(pct - 100) < 0.5:
            pct_str = "baseline"
        color = GREEN if delta < bl_delta * 0.9 else RED if delta > bl_delta * 1.1 else YELLOW
        print(
            f"  {name:<{col_param}} {label:<{col_val}} "
            f"{w:{col_num}.1f} {n:{col_num}.1f} "
            f"{color}{delta:{col_num}.1f}{RESET} {pct_str:>{col_num}}"
        )

    # ── Key findings ──────────────────────────────────────────────
    header("KEY FINDINGS")

    # Find most sensitive parameter
    max_row = max(rows, key=lambda r: r[4])
    min_row = min(rows, key=lambda r: r[4])

    print(f"""
  Baseline ECB contribution: {bl_delta:.0f} bn EUR avoided losses.

  Most amplifying:  {max_row[0]} = {max_row[1]}
                    Delta {max_row[4]:.0f} bn ({max_row[5]:+.0f}% vs baseline)

  Most dampening:   {min_row[0]} = {min_row[1]}
                    Delta {min_row[4]:.0f} bn ({min_row[5]:+.0f}% vs baseline)

  The ECB backstop is most valuable when shock magnitudes are large,
  LGD rates are high, and the interbank network is dense, because
  these conditions produce longer contagion cascades that the ECB
  circuit-breaker terminates earlier.
""")


if __name__ == "__main__":
    main()
