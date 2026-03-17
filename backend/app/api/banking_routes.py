"""
api/banking_routes.py — Banking contagion simulation API

Runs the Italian sovereign crisis scenario step-by-step, capturing
bank state snapshots after each contagion round so the frontend
can replay the cascade with per-round graph updates.
"""
from fastapi import APIRouter

from app.models.bank import BankType, BankStatus
from app.services.contagion_engine import ContagionEngine, BankingShock

banking_router = APIRouter(prefix="/banking", tags=["banking"])


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _bank_snapshot(engine):
    """Snapshot all commercial bank states."""
    states = {}
    for bank in engine.banks.values():
        if bank.bank_type == BankType.CENTRAL_BANK:
            continue
        states[bank.bank_id] = {
            "bank_id": bank.bank_id,
            "name": bank.name,
            "short_name": bank.short_name,
            "type": bank.bank_type.value,
            "country": bank.country,
            "status": bank.status.value,
            "total_assets_eur_bn": round(bank.total_assets_eur_bn, 1),
            "cet1_ratio_pct": round(bank.cet1_ratio * 100, 2),
            "lcr_pct": round(bank.liquidity.lcr_pct, 1),
            "credit_spread_bps": round(bank.credit_spread_bps, 0),
            "funding_stress": bank.funding_stress.value,
            "cb_borrowing_eur_bn": round(bank.liabilities.cb_borrowing_eur_bn, 1),
        }
    return states


def _compute_metrics(bank_states, cumulative_loss=0.0):
    """Compute system-wide metrics from bank state snapshot."""
    banks = list(bank_states.values())
    if not banks:
        return {}
    n_stressed = sum(1 for b in banks if b["status"] in ("stressed", "critical"))
    n_failed = sum(1 for b in banks if b["status"] in ("failed", "resolution"))
    return {
        "total_assets_eur_bn": round(sum(b["total_assets_eur_bn"] for b in banks), 1),
        "avg_cet1_ratio_pct": round(sum(b["cet1_ratio_pct"] for b in banks) / len(banks), 2),
        "avg_lcr_pct": round(sum(b["lcr_pct"] for b in banks) / len(banks), 1),
        "avg_spread_bps": round(sum(b["credit_spread_bps"] for b in banks) / len(banks), 0),
        "banks_normal": len(banks) - n_stressed - n_failed,
        "banks_stressed": n_stressed,
        "banks_failed": n_failed,
        "ecb_facility_eur_bn": round(sum(b["cb_borrowing_eur_bn"] for b in banks), 1),
        "cumulative_loss_eur_bn": round(cumulative_loss, 1),
    }


def _serialize_event(e):
    return {
        "channel": e.channel,
        "source_bank_id": e.source_bank_id,
        "target_bank_id": e.target_bank_id,
        "loss_eur_bn": round(e.loss_eur_bn, 2),
        "description": e.description,
    }


def _extract_contagion_edges(events):
    """Extract bank-to-bank contagion flow for edge highlighting."""
    edges = set()
    for e in events:
        if not e.target_bank_id:
            continue
        sources = e.source_bank_id.split(",") if e.source_bank_id else []
        for src in sources:
            src = src.strip()
            if src and src not in ("exogenous", "market", "depositors") and src != e.target_bank_id:
                edges.add((src, e.target_bank_id))
    return [{"source": s, "target": t} for s, t in edges]


def _run_with_snapshots(engine, shock):
    """
    Run the contagion cascade step-by-step, capturing a bank-state
    snapshot after each round for the frontend timeline replay.
    """
    rounds = []

    # Phase 1: Initial shock
    initial_events = engine._apply_initial_shock(shock, tick=1)
    rounds.append({
        "round_num": 0,
        "label": "Initial Shock",
        "events": [_serialize_event(e) for e in initial_events],
        "bank_states": _bank_snapshot(engine),
        "active_edges": _extract_contagion_edges(initial_events),
        "affected_banks": list({e.target_bank_id for e in initial_events if e.target_bank_id}),
        "round_loss_eur_bn": round(sum(e.loss_eur_bn for e in initial_events), 2),
    })

    # Phase 2: Iterative contagion rounds
    newly_stressed = {e.target_bank_id for e in initial_events if e.target_bank_id}
    round_num = 0
    while newly_stressed and round_num < engine.max_contagion_rounds:
        round_num += 1
        round_events = []
        round_events.extend(engine._propagate_counterparty(newly_stressed, 1, round_num))
        round_events.extend(engine._propagate_fire_sale(newly_stressed, 1, round_num))
        round_events.extend(engine._propagate_funding_freeze(newly_stressed, 1, round_num))
        round_events.extend(engine._propagate_confidence(newly_stressed, 1, round_num))

        prev_stressed = newly_stressed
        newly_stressed = set()
        for event in round_events:
            if event.target_bank_id and event.target_bank_id not in prev_stressed:
                bank = engine.banks.get(event.target_bank_id)
                if bank and bank.status in (
                    BankStatus.STRESSED, BankStatus.CRITICAL, BankStatus.FAILED,
                ):
                    newly_stressed.add(event.target_bank_id)

        if not round_events:
            break

        rounds.append({
            "round_num": round_num,
            "label": f"Contagion Round {round_num}",
            "events": [_serialize_event(e) for e in round_events],
            "bank_states": _bank_snapshot(engine),
            "active_edges": _extract_contagion_edges(round_events),
            "affected_banks": list({e.target_bank_id for e in round_events if e.target_bank_id}),
            "round_loss_eur_bn": round(sum(e.loss_eur_bn for e in round_events), 2),
        })

    # Phase 3: ECB intervention
    ecb_events = engine._ecb_intervention(1, round_num + 1)
    for bank in engine.banks.values():
        if bank.bank_type != BankType.CENTRAL_BANK:
            bank.update_liquidity_metrics()
            bank.update_status()

    if ecb_events:
        rounds.append({
            "round_num": round_num + 1,
            "label": "ECB Intervention",
            "events": [_serialize_event(e) for e in ecb_events],
            "bank_states": _bank_snapshot(engine),
            "active_edges": [],
            "affected_banks": list({e.target_bank_id for e in ecb_events if e.target_bank_id}),
            "round_loss_eur_bn": 0.0,
        })

    return rounds


# -------------------------------------------------------------------
# Endpoint
# -------------------------------------------------------------------

@banking_router.get("/simulate")
def simulate_banking_contagion():
    """
    Run the Italian sovereign crisis scenario and return the full
    contagion cascade with per-round bank state snapshots, network
    graph data, and system-wide metrics for visualization.
    """
    engine = ContagionEngine(seed=42)
    engine.initialize()

    # Pre-shock snapshot
    pre_shock_banks = _bank_snapshot(engine)
    network = engine.get_network_graph()

    # Define shock
    shock = BankingShock(
        shock_id="italian_crisis_2026",
        description="Italian sovereign crisis \u2192 deposit run on UniCredit",
        target_bank_id="UCG",
        asset_writedown_pct=8.0,
        affected_asset="loans",
        deposit_run_pct=40.0,
        wholesale_funding_haircut_pct=50.0,
        sovereign_bond_haircut_pct=15.0,
        credit_spread_shock_bps=200.0,
        interbank_rate_spike_bps=50.0,
    )

    # Run step-by-step with snapshots
    rounds = _run_with_snapshots(engine, shock)

    # Attach cumulative losses and metrics to each round
    cumulative = 0.0
    for r in rounds:
        cumulative += r["round_loss_eur_bn"]
        r["cumulative_loss_eur_bn"] = round(cumulative, 2)
        r["metrics"] = _compute_metrics(r["bank_states"], cumulative)

    return {
        "shock": {
            "id": shock.shock_id,
            "description": shock.description,
            "target": shock.target_bank_id,
            "params": {
                "loan_writedown_pct": shock.asset_writedown_pct,
                "deposit_run_pct": shock.deposit_run_pct,
                "wholesale_freeze_pct": shock.wholesale_funding_haircut_pct,
                "sovereign_haircut_pct": shock.sovereign_bond_haircut_pct,
                "spread_shock_bps": shock.credit_spread_shock_bps,
            },
        },
        "network": network,
        "pre_shock": {
            "bank_states": pre_shock_banks,
            "metrics": _compute_metrics(pre_shock_banks),
        },
        "rounds": rounds,
        "total_events": sum(len(r["events"]) for r in rounds),
    }
