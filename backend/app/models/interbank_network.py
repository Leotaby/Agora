"""
models/interbank_network.py — Interbank lending network

A directed weighted graph of overnight and term lending relationships
between banks. Banks with excess liquidity lend to banks with shortfalls.
Contagion spreads through this network when a borrower defaults on its
obligations, imposing losses on all its creditors.

Network structure:
  - Nodes = banks (keyed by bank_id)
  - Edges = InterbankExposure (lender → borrower, with amount/rate/maturity)
  - G-SIBs form a dense core; smaller banks sit on the periphery as net borrowers
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.bank import (
    Bank, BankStatus, BankType, InterbankExposure,
    build_all_banks, wire_interbank_network,
)


@dataclass
class InterbankNetwork:
    """
    Manages the interbank lending graph and provides queries over it.

    Usage:
        network = InterbankNetwork.from_presets()
        excess = network.banks_with_excess_liquidity()
        deficit = network.banks_with_liquidity_shortfall()
        losses = network.default_bank("UCG")
    """
    banks: dict[str, Bank] = field(default_factory=dict)
    exposures: list[InterbankExposure] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Construction
    # -------------------------------------------------------------------

    @classmethod
    def from_presets(cls) -> InterbankNetwork:
        """Build the network from all preset banks."""
        banks = build_all_banks()
        exposures = wire_interbank_network(banks)
        for bank in banks.values():
            if bank.bank_type != BankType.CENTRAL_BANK:
                bank.update_liquidity_metrics()
                bank.update_status()
        return cls(banks=banks, exposures=exposures)

    # -------------------------------------------------------------------
    # Queries: who lends to whom, exposure totals
    # -------------------------------------------------------------------

    def exposures_from(self, bank_id: str) -> list[InterbankExposure]:
        """All exposures where bank_id is the lender."""
        return [e for e in self.exposures if e.lender_id == bank_id]

    def exposures_to(self, bank_id: str) -> list[InterbankExposure]:
        """All exposures where bank_id is the borrower."""
        return [e for e in self.exposures if e.borrower_id == bank_id]

    def total_lending(self, bank_id: str) -> float:
        """Total EUR bn this bank has lent out in the interbank market."""
        return sum(e.amount_eur_bn for e in self.exposures_from(bank_id))

    def total_borrowing(self, bank_id: str) -> float:
        """Total EUR bn this bank has borrowed from the interbank market."""
        return sum(e.amount_eur_bn for e in self.exposures_to(bank_id))

    def net_interbank_position(self, bank_id: str) -> float:
        """Positive = net lender, negative = net borrower."""
        return self.total_lending(bank_id) - self.total_borrowing(bank_id)

    def counterparties(self, bank_id: str) -> set[str]:
        """All bank_ids this bank has any interbank relationship with."""
        cps: set[str] = set()
        for e in self.exposures:
            if e.lender_id == bank_id:
                cps.add(e.borrower_id)
            elif e.borrower_id == bank_id:
                cps.add(e.lender_id)
        return cps

    # -------------------------------------------------------------------
    # Liquidity analysis
    # -------------------------------------------------------------------

    def banks_with_excess_liquidity(self, threshold_lcr: float = 120.0) -> list[Bank]:
        """Banks with LCR well above minimum — potential overnight lenders."""
        return [
            b for b in self.banks.values()
            if b.bank_type != BankType.CENTRAL_BANK
            and b.liquidity.lcr_pct >= threshold_lcr
        ]

    def banks_with_liquidity_shortfall(self, threshold_lcr: float = 100.0) -> list[Bank]:
        """Banks with LCR below threshold — need to borrow or sell assets."""
        return [
            b for b in self.banks.values()
            if b.bank_type != BankType.CENTRAL_BANK
            and b.liquidity.lcr_pct < threshold_lcr
        ]

    # -------------------------------------------------------------------
    # Default cascade
    # -------------------------------------------------------------------

    def default_bank(
        self, bank_id: str, recovery_rate: float = 0.40,
    ) -> list[dict]:
        """
        Simulate a bank defaulting on all interbank obligations.
        Each creditor bank takes a loss = exposure * (1 - recovery_rate).
        Returns a list of {creditor, loss_eur_bn, creditor_solvent_after}.
        Does NOT chain further defaults — that's the contagion engine's job.
        """
        results: list[dict] = []
        creditor_exposures = self.exposures_to(bank_id)

        defaulted = self.banks.get(bank_id)
        if defaulted:
            defaulted.status = BankStatus.FAILED

        for exp in creditor_exposures:
            creditor = self.banks.get(exp.lender_id)
            if not creditor or creditor.bank_type == BankType.CENTRAL_BANK:
                continue

            loss = exp.amount_eur_bn * (1 - recovery_rate)
            if exp.is_secured:
                loss *= 0.2  # collateral covers 80%

            creditor.assets.interbank_lending_eur_bn = max(
                0, creditor.assets.interbank_lending_eur_bn - loss,
            )
            excess = creditor.absorb_loss(loss)
            creditor.update_liquidity_metrics()
            creditor.update_status()

            results.append({
                "creditor": creditor.short_name,
                "creditor_id": creditor.bank_id,
                "exposure_eur_bn": round(exp.amount_eur_bn, 2),
                "loss_eur_bn": round(loss, 2),
                "unabsorbed_eur_bn": round(excess, 2),
                "creditor_cet1_after_pct": round(creditor.cet1_ratio * 100, 2),
                "creditor_solvent": creditor.is_solvent(),
            })

        return results

    # -------------------------------------------------------------------
    # Overnight lending round
    # -------------------------------------------------------------------

    def settle_overnight(self) -> list[dict]:
        """
        Simple overnight lending: banks with excess reserves lend to
        banks with shortfalls. Returns a log of new lending.
        """
        lenders = sorted(
            self.banks_with_excess_liquidity(threshold_lcr=130.0),
            key=lambda b: b.liquidity.lcr_pct,
            reverse=True,
        )
        borrowers = sorted(
            self.banks_with_liquidity_shortfall(threshold_lcr=100.0),
            key=lambda b: b.liquidity.lcr_pct,
        )

        log: list[dict] = []
        for borrower in borrowers:
            deficit = borrower.liabilities.runnable_funding_eur_bn * 0.3
            deficit = min(deficit, 10.0)  # cap per round

            for lender in lenders:
                if deficit <= 0.1:
                    break
                available = lender.assets.cb_reserves_eur_bn * 0.1
                amount = min(deficit, available)
                if amount < 0.1:
                    continue

                # Execute the loan
                lender.assets.cb_reserves_eur_bn -= amount
                lender.assets.interbank_lending_eur_bn += amount
                borrower.assets.cb_reserves_eur_bn += amount
                borrower.liabilities.interbank_borrowing_eur_bn += amount

                exp = InterbankExposure(
                    lender_id=lender.bank_id,
                    borrower_id=borrower.bank_id,
                    amount_eur_bn=amount,
                    maturity_days=1,
                    rate_bps=390,
                )
                self.exposures.append(exp)
                lender.interbank_exposures.append(exp)
                borrower.interbank_exposures.append(exp)
                deficit -= amount

                log.append({
                    "lender": lender.short_name,
                    "borrower": borrower.short_name,
                    "amount_eur_bn": round(amount, 2),
                })

            borrower.update_liquidity_metrics()
        for lender in lenders:
            lender.update_liquidity_metrics()

        return log

    # -------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------

    def adjacency_matrix(self) -> dict[str, dict[str, float]]:
        """Return exposure amounts as {lender_id: {borrower_id: total_eur_bn}}."""
        matrix: dict[str, dict[str, float]] = {}
        for exp in self.exposures:
            row = matrix.setdefault(exp.lender_id, {})
            row[exp.borrower_id] = row.get(exp.borrower_id, 0) + exp.amount_eur_bn
        return matrix

    def print_network(self) -> None:
        """Print a compact summary of the interbank network."""
        print("\n=== INTERBANK NETWORK ===")
        non_cb = [b for b in self.banks.values() if b.bank_type != BankType.CENTRAL_BANK]
        for bank in sorted(non_cb, key=lambda b: b.total_assets_eur_bn, reverse=True):
            net = self.net_interbank_position(bank.bank_id)
            label = "net lender" if net > 0 else "net borrower"
            print(
                f"  {bank.short_name:6s}  assets={bank.total_assets_eur_bn:7.1f}  "
                f"CET1={bank.cet1_ratio*100:5.1f}%  LCR={bank.liquidity.lcr_pct:5.1f}%  "
                f"interbank={net:+6.1f} ({label})"
            )
        print(f"  Total exposures: {len(self.exposures)}, "
              f"gross volume: €{sum(e.amount_eur_bn for e in self.exposures):.1f}bn")
