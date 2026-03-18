"""
services/contagion_engine.py — Systemic risk contagion through the interbank network

How a single bank's distress becomes everyone's problem:

1. SOLVENCY CHANNEL — Asset write-downs erode capital
   A bank marks down bad loans/bonds → CET1 falls → breaches minimum →
   forced asset sales at fire-sale prices → other banks holding same assets
   mark down too → death spiral.

2. LIQUIDITY CHANNEL — Funding freeze propagates
   Market loses confidence in Bank A → wholesale funding won't roll →
   Bank A can't pay back interbank borrowing → Bank B (the lender) takes
   a hit on its interbank_lending asset → Bank B's own funding dries up →
   cascade.

3. COUNTERPARTY CHANNEL — Interbank exposure losses
   Bank A fails → every bank that lent to A overnight loses that money →
   direct balance sheet hit → those banks may then fail too.

4. FIRE SALE CHANNEL — Forced selling depresses asset prices
   Stressed banks dump liquid assets → market prices drop → every bank
   marks down the same assets → more banks breach ratios → more selling.

5. CONFIDENCE CHANNEL — Credit spreads blow out
   CDS spreads widen → wholesale funding costs spike → marginal banks
   become unprofitable → preemptive bank runs.

The ECB can intervene as lender of last resort (ELA, TLTRO expansion).
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from app.models.bank import (
    Bank, BankStatus, BankType, FundingStress,
    InterbankExposure, build_all_banks, wire_interbank_network,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shock definitions
# ---------------------------------------------------------------------------

@dataclass
class BankingShock:
    """An exogenous shock to the banking system."""
    shock_id: str = ""
    description: str = ""

    # Solvency shock: direct loss to a specific bank's assets
    target_bank_id: str = ""                 # "" = system-wide
    asset_writedown_pct: float = 0.0         # % of affected assets written down
    affected_asset: str = ""                 # "loans", "sovereign_bonds", "mortgages", etc.

    # Liquidity shock: funding market freezes
    wholesale_funding_haircut_pct: float = 0.0  # % of wholesale funding that won't roll
    deposit_run_pct: float = 0.0               # % of uninsured deposits that flee

    # Market shock: asset prices drop across the board
    sovereign_bond_haircut_pct: float = 0.0
    corporate_securities_haircut_pct: float = 0.0
    interbank_rate_spike_bps: float = 0.0      # stress premium on all interbank lending

    # Confidence shock
    credit_spread_shock_bps: float = 0.0       # added to all banks' CDS spreads


@dataclass
class ContagionEvent:
    """Record of one contagion propagation step."""
    tick: int = 0
    round_num: int = 0                       # contagion round within this tick
    channel: str = ""                        # "solvency", "liquidity", "counterparty", "fire_sale", "confidence"
    source_bank_id: str = ""
    target_bank_id: str = ""
    loss_eur_bn: float = 0.0
    description: str = ""


# ---------------------------------------------------------------------------
# Contagion engine
# ---------------------------------------------------------------------------

class ContagionEngine:
    """
    Propagates solvency and liquidity shocks through the interbank network.

    Usage:
        engine = ContagionEngine(seed=42)
        engine.initialize()  # builds banks + wires network
        events = engine.process_shock(shock, tick=5)
        # events is a list of ContagionEvent describing the cascade
    """

    def __init__(self, seed: int = 42, ecb_intervention: bool = True):
        self._rng = random.Random(seed)
        self.banks: dict[str, Bank] = {}
        self.interbank_exposures: list[InterbankExposure] = []
        self.contagion_log: list[ContagionEvent] = []
        self._max_log: int = 5000

        # ECB backstop
        self.ecb_intervention: bool = ecb_intervention

        # Contagion parameters
        self.fire_sale_price_impact: float = 0.02     # 2% price drop per €100bn sold
        self.confidence_decay_rate: float = 0.5       # how fast spreads infect neighbors
        self.max_contagion_rounds: int = 10            # circuit breaker
        self.recovery_rate_on_failure: float = 0.40    # 40 cents on the dollar in resolution
        self.lgd_critical_pct: float = 0.20            # loss given default for critical banks
        self.lgd_stressed_pct: float = 0.05            # loss given default for stressed banks

    def initialize(self) -> None:
        """Build all preset banks and wire the interbank network."""
        self.banks = build_all_banks()
        self.interbank_exposures = wire_interbank_network(self.banks)

        # Compute initial liquidity metrics for all banks
        for bank in self.banks.values():
            if bank.bank_type != BankType.CENTRAL_BANK:
                bank.update_liquidity_metrics()
                bank.update_status()

        logger.info(
            "ContagionEngine initialized: %d banks, %d interbank exposures",
            len(self.banks), len(self.interbank_exposures),
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_shock(self, shock: BankingShock, tick: int = 0) -> list[ContagionEvent]:
        """
        Apply an exogenous shock and propagate contagion until equilibrium.
        Returns the full cascade of contagion events.
        """
        events: list[ContagionEvent] = []
        round_num = 0

        # Phase 1: Apply the initial shock
        initial_events = self._apply_initial_shock(shock, tick)
        events.extend(initial_events)

        # Phase 1b: Cross-border secondary effects
        # JPMorgan restricts dollar repo; UBS marks down European sovereigns
        secondary_events = self._apply_cross_border_effects(shock, tick)
        events.extend(secondary_events)

        # Phase 2: Iterative contagion rounds
        newly_stressed = {e.target_bank_id for e in events if e.target_bank_id}
        while newly_stressed and round_num < self.max_contagion_rounds:
            round_num += 1
            round_events: list[ContagionEvent] = []

            # 2a. Counterparty channel — interbank losses from stressed/failed banks
            round_events.extend(
                self._propagate_counterparty(newly_stressed, tick, round_num)
            )

            # 2b. Fire sale channel — stressed banks dump assets
            round_events.extend(
                self._propagate_fire_sale(newly_stressed, tick, round_num)
            )

            # 2c. Liquidity channel — funding freeze spreads
            round_events.extend(
                self._propagate_funding_freeze(newly_stressed, tick, round_num)
            )

            # 2d. Confidence channel — spreads blow out
            round_events.extend(
                self._propagate_confidence(newly_stressed, tick, round_num)
            )

            # Determine which banks became newly stressed this round
            prev_stressed = newly_stressed
            newly_stressed = set()
            for event in round_events:
                if event.target_bank_id and event.target_bank_id not in prev_stressed:
                    bank = self.banks.get(event.target_bank_id)
                    if bank and bank.status in (BankStatus.STRESSED, BankStatus.CRITICAL, BankStatus.FAILED):
                        newly_stressed.add(event.target_bank_id)

            events.extend(round_events)

            if not round_events:
                break  # equilibrium reached

        # Phase 3: ECB intervention (lender of last resort)
        if self.ecb_intervention:
            ecb_events = self._ecb_intervention(tick, round_num + 1)
            events.extend(ecb_events)

        # Update all statuses
        for bank in self.banks.values():
            if bank.bank_type != BankType.CENTRAL_BANK:
                bank.update_liquidity_metrics()
                bank.update_status()

        # Log
        self.contagion_log.extend(events)
        if len(self.contagion_log) > self._max_log:
            self.contagion_log = self.contagion_log[-self._max_log:]

        return events

    # ------------------------------------------------------------------
    # Phase 1: Initial shock application
    # ------------------------------------------------------------------

    def _apply_initial_shock(
        self, shock: BankingShock, tick: int,
    ) -> list[ContagionEvent]:
        events: list[ContagionEvent] = []

        target_banks = (
            [self.banks[shock.target_bank_id]]
            if shock.target_bank_id and shock.target_bank_id in self.banks
            else [b for b in self.banks.values() if b.bank_type != BankType.CENTRAL_BANK]
        )

        for bank in target_banks:
            total_loss = 0.0

            # Solvency: asset write-down
            if shock.asset_writedown_pct > 0:
                loss = self._apply_asset_writedown(
                    bank, shock.affected_asset, shock.asset_writedown_pct,
                )
                if loss > 0:
                    total_loss += loss
                    events.append(ContagionEvent(
                        tick=tick, round_num=0, channel="solvency",
                        source_bank_id="exogenous", target_bank_id=bank.bank_id,
                        loss_eur_bn=loss,
                        description=f"{bank.short_name}: {shock.affected_asset} writedown {shock.asset_writedown_pct:.1f}% → loss €{loss:.1f}bn",
                    ))

            # Market: sovereign/corporate bond haircuts
            if shock.sovereign_bond_haircut_pct > 0:
                loss = bank.assets.sovereign_bonds_eur_bn * shock.sovereign_bond_haircut_pct / 100
                bank.assets.sovereign_bonds_eur_bn -= loss
                excess = bank.absorb_loss(loss)
                total_loss += loss
                events.append(ContagionEvent(
                    tick=tick, round_num=0, channel="solvency",
                    source_bank_id="market", target_bank_id=bank.bank_id,
                    loss_eur_bn=loss,
                    description=f"{bank.short_name}: sovereign bonds haircut {shock.sovereign_bond_haircut_pct:.1f}% → loss €{loss:.1f}bn",
                ))

            if shock.corporate_securities_haircut_pct > 0:
                loss = bank.assets.corporate_securities_eur_bn * shock.corporate_securities_haircut_pct / 100
                bank.assets.corporate_securities_eur_bn -= loss
                excess = bank.absorb_loss(loss)
                total_loss += loss
                events.append(ContagionEvent(
                    tick=tick, round_num=0, channel="solvency",
                    source_bank_id="market", target_bank_id=bank.bank_id,
                    loss_eur_bn=loss,
                    description=f"{bank.short_name}: corporate securities haircut → loss €{loss:.1f}bn",
                ))

            # Liquidity: wholesale funding haircut
            if shock.wholesale_funding_haircut_pct > 0:
                lost_funding = bank.liabilities.wholesale_funding_eur_bn * shock.wholesale_funding_haircut_pct / 100
                bank.liabilities.wholesale_funding_eur_bn -= lost_funding
                # Bank must find replacement or shrink assets
                bank.assets.cb_reserves_eur_bn = max(
                    0, bank.assets.cb_reserves_eur_bn - lost_funding,
                )
                events.append(ContagionEvent(
                    tick=tick, round_num=0, channel="liquidity",
                    source_bank_id="market", target_bank_id=bank.bank_id,
                    loss_eur_bn=lost_funding,
                    description=f"{bank.short_name}: wholesale funding freeze {shock.wholesale_funding_haircut_pct:.0f}% → €{lost_funding:.1f}bn lost",
                ))
                self._update_funding_stress(bank)

            # Liquidity: deposit run
            if shock.deposit_run_pct > 0:
                lost_deposits = bank.liabilities.corporate_deposits_eur_bn * shock.deposit_run_pct / 100
                bank.liabilities.corporate_deposits_eur_bn -= lost_deposits
                bank.assets.cb_reserves_eur_bn = max(
                    0, bank.assets.cb_reserves_eur_bn - lost_deposits,
                )
                events.append(ContagionEvent(
                    tick=tick, round_num=0, channel="liquidity",
                    source_bank_id="depositors", target_bank_id=bank.bank_id,
                    loss_eur_bn=lost_deposits,
                    description=f"{bank.short_name}: deposit run {shock.deposit_run_pct:.0f}% → €{lost_deposits:.1f}bn withdrawn",
                ))
                self._update_funding_stress(bank)

            # Confidence: credit spread shock
            if shock.credit_spread_shock_bps > 0:
                bank.credit_spread_bps += shock.credit_spread_shock_bps
                events.append(ContagionEvent(
                    tick=tick, round_num=0, channel="confidence",
                    source_bank_id="market", target_bank_id=bank.bank_id,
                    loss_eur_bn=0,
                    description=f"{bank.short_name}: CDS spread +{shock.credit_spread_shock_bps:.0f}bps → {bank.credit_spread_bps:.0f}bps",
                ))

            # Interbank rate spike
            if shock.interbank_rate_spike_bps > 0:
                for exp in bank.interbank_exposures:
                    exp.rate_bps += shock.interbank_rate_spike_bps

            bank.update_liquidity_metrics()
            bank.update_status()

        return events

    def _apply_asset_writedown(
        self, bank: Bank, asset_type: str, writedown_pct: float,
    ) -> float:
        """Write down a specific asset class and absorb the loss. Returns loss amount."""
        pct = writedown_pct / 100

        asset_map = {
            "loans": "loans_eur_bn",
            "mortgages": "mortgages_eur_bn",
            "sovereign_bonds": "sovereign_bonds_eur_bn",
            "corporate_securities": "corporate_securities_eur_bn",
            "interbank_lending": "interbank_lending_eur_bn",
            "trading_book": "trading_book_eur_bn",
        }

        attr = asset_map.get(asset_type, "loans_eur_bn")
        current_val = getattr(bank.assets, attr)
        loss = current_val * pct
        setattr(bank.assets, attr, current_val - loss)
        bank.absorb_loss(loss)
        return loss

    # ------------------------------------------------------------------
    # Phase 1b: Cross-border secondary effects
    # ------------------------------------------------------------------

    def _apply_cross_border_effects(
        self, shock: BankingShock, tick: int,
    ) -> list[ContagionEvent]:
        """
        Cross-Atlantic secondary effects triggered by European sovereign stress.

        1. JPMorgan restricts dollar repo funding to European banks:
           When European sovereign risk spikes, JPM's risk desk cuts secured
           lending lines to all European counterparties (guilt-by-association).
           European banks that depend on dollar repo lose funding immediately.

        2. UBS marks down European sovereign bond holdings:
           Swiss bank holds European government bonds; sovereign repricing
           in Italy triggers mark-to-market losses across the portfolio
           (not just Italian BTPs but a general risk-off on European debt).
        """
        events: list[ContagionEvent] = []

        # Only trigger on sovereign-related shocks
        is_sovereign_shock = (
            shock.sovereign_bond_haircut_pct > 0
            or shock.affected_asset == "sovereign_bonds"
        )
        if not is_sovereign_shock:
            return events

        jpm = self.banks.get("JPM")
        ubs = self.banks.get("UBS")

        # 1. JPMorgan restricts dollar repo to European banks
        if jpm:
            # Restriction severity scales with sovereign shock magnitude
            restriction_pct = min(60.0, shock.sovereign_bond_haircut_pct * 4)

            for exp in self.interbank_exposures:
                if exp.lender_id != "JPM":
                    continue
                if not exp.is_secured:
                    continue  # only dollar repo (secured) lines

                borrower = self.banks.get(exp.borrower_id)
                if not borrower or borrower.country == "US":
                    continue  # only restrict European borrowers

                # Reduce the repo line
                reduction = exp.amount_eur_bn * restriction_pct / 100
                exp.amount_eur_bn -= reduction

                # Borrower loses dollar funding → drains reserves
                borrower.liabilities.wholesale_funding_eur_bn -= reduction
                borrower.assets.cb_reserves_eur_bn = max(
                    0, borrower.assets.cb_reserves_eur_bn - reduction,
                )
                self._update_funding_stress(borrower)
                borrower.update_liquidity_metrics()
                borrower.update_status()

                events.append(ContagionEvent(
                    tick=tick, round_num=0, channel="liquidity",
                    source_bank_id="JPM", target_bank_id=borrower.bank_id,
                    loss_eur_bn=reduction,
                    description=(
                        f"JPM restricts dollar repo to {borrower.short_name}: "
                        f"-{restriction_pct:.0f}% → €{reduction:.1f}bn withdrawn"
                    ),
                ))

        # 2. UBS marks down European sovereign bond holdings
        if ubs:
            # Haircut proportional to shock but smaller (guilt-by-association)
            ubs_haircut_pct = shock.sovereign_bond_haircut_pct * 0.33
            loss = ubs.assets.sovereign_bonds_eur_bn * ubs_haircut_pct / 100
            if loss > 0.1:
                ubs.assets.sovereign_bonds_eur_bn -= loss
                ubs.absorb_loss(loss)
                # Some spread contagion to UBS
                spread_hit = shock.credit_spread_shock_bps * 0.25
                ubs.credit_spread_bps += spread_hit
                ubs.update_liquidity_metrics()
                ubs.update_status()

                events.append(ContagionEvent(
                    tick=tick, round_num=0, channel="solvency",
                    source_bank_id="market", target_bank_id="UBS",
                    loss_eur_bn=loss,
                    description=(
                        f"UBS marks down European sovereign bonds "
                        f"{ubs_haircut_pct:.1f}% (guilt-by-association) "
                        f"→ loss €{loss:.1f}bn, CDS +{spread_hit:.0f}bps"
                    ),
                ))

        return events

    # ------------------------------------------------------------------
    # Phase 2: Contagion channels
    # ------------------------------------------------------------------

    def _propagate_counterparty(
        self, stressed_ids: set[str], tick: int, round_num: int,
    ) -> list[ContagionEvent]:
        """
        Banks that lent money to stressed/failed banks take losses.
        If the borrower has failed: loss = exposure * (1 - recovery_rate).
        If stressed: loss = exposure * probability_of_default_estimate.
        """
        events: list[ContagionEvent] = []

        for exp in self.interbank_exposures:
            if exp.borrower_id not in stressed_ids:
                continue

            borrower = self.banks.get(exp.borrower_id)
            lender = self.banks.get(exp.lender_id)
            if not borrower or not lender:
                continue
            if lender.bank_type == BankType.CENTRAL_BANK:
                continue  # ECB doesn't take losses this way

            # Calculate loss
            if borrower.status == BankStatus.FAILED:
                loss = exp.amount_eur_bn * (1 - self.recovery_rate_on_failure)
            elif borrower.status == BankStatus.CRITICAL:
                loss = exp.amount_eur_bn * self.lgd_critical_pct
            elif borrower.status == BankStatus.STRESSED:
                loss = exp.amount_eur_bn * self.lgd_stressed_pct
            else:
                continue

            # Secured exposures have lower loss
            if exp.is_secured:
                loss *= 0.2  # 80% recovery from collateral

            if loss < 0.01:
                continue

            # Apply loss to lender
            lender.assets.interbank_lending_eur_bn = max(
                0, lender.assets.interbank_lending_eur_bn - loss,
            )
            excess = lender.absorb_loss(loss)
            lender.update_liquidity_metrics()
            lender.update_status()

            events.append(ContagionEvent(
                tick=tick, round_num=round_num, channel="counterparty",
                source_bank_id=exp.borrower_id, target_bank_id=exp.lender_id,
                loss_eur_bn=loss,
                description=(
                    f"{lender.short_name} loses €{loss:.2f}bn on interbank exposure "
                    f"to {borrower.short_name} ({borrower.status.value})"
                ),
            ))

        return events

    def _propagate_fire_sale(
        self, stressed_ids: set[str], tick: int, round_num: int,
    ) -> list[ContagionEvent]:
        """
        Stressed banks sell liquid assets → price drops → all banks mark down.
        """
        events: list[ContagionEvent] = []

        # Calculate total forced selling
        total_selling_eur_bn = 0.0
        sellers: list[str] = []
        for bank_id in stressed_ids:
            bank = self.banks.get(bank_id)
            if not bank or bank.bank_type == BankType.CENTRAL_BANK:
                continue
            if bank.status in (BankStatus.STRESSED, BankStatus.CRITICAL):
                # Sell liquid assets to rebuild LCR
                lcr_deficit = max(0, 100 - bank.liquidity.lcr_pct)
                sell_amount = bank.assets.sovereign_bonds_eur_bn * lcr_deficit / 400
                sell_amount = min(sell_amount, bank.assets.sovereign_bonds_eur_bn * 0.3)
                if sell_amount > 0.1:
                    bank.assets.sovereign_bonds_eur_bn -= sell_amount
                    bank.assets.cb_reserves_eur_bn += sell_amount * 0.97  # 3% fire-sale discount
                    total_selling_eur_bn += sell_amount
                    sellers.append(bank_id)

        if total_selling_eur_bn < 0.5:
            return events

        # Price impact hits everyone
        price_impact_pct = total_selling_eur_bn * self.fire_sale_price_impact
        price_impact_pct = min(price_impact_pct, 15.0)  # cap at 15% drop

        for bank in self.banks.values():
            if bank.bank_type == BankType.CENTRAL_BANK:
                continue
            if bank.bank_id in sellers:
                continue  # already sold, don't double-count

            loss = bank.assets.sovereign_bonds_eur_bn * price_impact_pct / 100
            if loss < 0.01:
                continue

            bank.assets.sovereign_bonds_eur_bn -= loss
            bank.absorb_loss(loss)
            bank.update_liquidity_metrics()
            bank.update_status()

            events.append(ContagionEvent(
                tick=tick, round_num=round_num, channel="fire_sale",
                source_bank_id=",".join(sellers),
                target_bank_id=bank.bank_id,
                loss_eur_bn=loss,
                description=(
                    f"{bank.short_name}: sovereign bonds marked down {price_impact_pct:.2f}% "
                    f"from fire sales → loss €{loss:.2f}bn"
                ),
            ))

        return events

    def _propagate_funding_freeze(
        self, stressed_ids: set[str], tick: int, round_num: int,
    ) -> list[ContagionEvent]:
        """
        When banks are stressed, their counterparties face guilt-by-association
        funding pressure. Wholesale lenders pull back from connected banks.
        """
        events: list[ContagionEvent] = []

        # Find banks connected to stressed banks
        connected: dict[str, float] = {}  # bank_id -> total exposure to stressed
        for exp in self.interbank_exposures:
            if exp.borrower_id in stressed_ids and exp.lender_id not in stressed_ids:
                lender = self.banks.get(exp.lender_id)
                if lender and lender.bank_type != BankType.CENTRAL_BANK:
                    connected[exp.lender_id] = connected.get(exp.lender_id, 0) + exp.amount_eur_bn
            if exp.lender_id in stressed_ids and exp.borrower_id not in stressed_ids:
                borrower = self.banks.get(exp.borrower_id)
                if borrower and borrower.bank_type != BankType.CENTRAL_BANK:
                    connected[exp.borrower_id] = connected.get(exp.borrower_id, 0) + exp.amount_eur_bn

        for bank_id, exposure in connected.items():
            bank = self.banks.get(bank_id)
            if not bank:
                continue

            # Funding stress proportional to exposure relative to total assets
            exposure_ratio = exposure / max(bank.total_assets_eur_bn, 1)
            funding_haircut = min(0.30, exposure_ratio * 2)  # up to 30%

            lost_funding = bank.liabilities.wholesale_funding_eur_bn * funding_haircut
            if lost_funding < 0.1:
                continue

            bank.liabilities.wholesale_funding_eur_bn -= lost_funding
            bank.assets.cb_reserves_eur_bn = max(
                0, bank.assets.cb_reserves_eur_bn - lost_funding * 0.5,
            )
            self._update_funding_stress(bank)
            bank.update_liquidity_metrics()
            bank.update_status()

            events.append(ContagionEvent(
                tick=tick, round_num=round_num, channel="liquidity",
                source_bank_id=",".join(stressed_ids),
                target_bank_id=bank_id,
                loss_eur_bn=lost_funding,
                description=(
                    f"{bank.short_name}: wholesale funding -{funding_haircut*100:.1f}% "
                    f"(guilt-by-association) → €{lost_funding:.1f}bn lost"
                ),
            ))

        return events

    def _propagate_confidence(
        self, stressed_ids: set[str], tick: int, round_num: int,
    ) -> list[ContagionEvent]:
        """
        Credit spreads of stressed banks infect neighbors.
        Connected banks see their CDS spreads widen.
        """
        events: list[ContagionEvent] = []

        max_spread = 0.0
        for bank_id in stressed_ids:
            bank = self.banks.get(bank_id)
            if bank:
                max_spread = max(max_spread, bank.credit_spread_bps)

        if max_spread < 50:
            return events

        for bank in self.banks.values():
            if bank.bank_type == BankType.CENTRAL_BANK:
                continue
            if bank.bank_id in stressed_ids:
                continue

            # Check connectivity to stressed banks
            connection_weight = 0.0
            for exp in self.interbank_exposures:
                if exp.lender_id == bank.bank_id and exp.borrower_id in stressed_ids:
                    connection_weight += exp.amount_eur_bn
                if exp.borrower_id == bank.bank_id and exp.lender_id in stressed_ids:
                    connection_weight += exp.amount_eur_bn

            if connection_weight < 0.1:
                continue

            # Spread contagion
            spread_increase = (
                max_spread * self.confidence_decay_rate
                * min(1.0, connection_weight / bank.total_assets_eur_bn * 10)
            )
            spread_increase = min(spread_increase, 200)  # cap per round

            if spread_increase < 5:
                continue

            bank.credit_spread_bps += spread_increase
            bank.update_status()

            events.append(ContagionEvent(
                tick=tick, round_num=round_num, channel="confidence",
                source_bank_id=",".join(stressed_ids),
                target_bank_id=bank.bank_id,
                loss_eur_bn=0,
                description=(
                    f"{bank.short_name}: CDS spread +{spread_increase:.0f}bps "
                    f"→ {bank.credit_spread_bps:.0f}bps (contagion from stressed peers)"
                ),
            ))

        return events

    # ------------------------------------------------------------------
    # Phase 3: ECB intervention
    # ------------------------------------------------------------------

    def _ecb_intervention(self, tick: int, round_num: int) -> list[ContagionEvent]:
        """
        ECB provides Emergency Liquidity Assistance (ELA) to banks in
        critical or stressed status that still have positive capital.
        Failed banks go to resolution (no ECB rescue).
        """
        events: list[ContagionEvent] = []
        ecb = self.banks.get("ECB_BANK")
        if not ecb:
            return events

        for bank in self.banks.values():
            if bank.bank_type == BankType.CENTRAL_BANK:
                continue

            # Failed banks: no rescue, resolution instead
            if bank.status == BankStatus.FAILED:
                events.append(ContagionEvent(
                    tick=tick, round_num=round_num, channel="resolution",
                    source_bank_id="ECB_BANK", target_bank_id=bank.bank_id,
                    loss_eur_bn=0,
                    description=f"{bank.short_name}: FAILED — entered SRB resolution. Bail-in of creditors.",
                ))
                bank.status = BankStatus.RESOLUTION
                continue

            # Critical banks with positive capital: ELA
            if bank.status in (BankStatus.CRITICAL, BankStatus.STRESSED):
                if bank.capital.cet1_capital_eur_bn <= 0:
                    continue

                # Provide emergency liquidity
                ela_amount = bank.liabilities.runnable_funding_eur_bn * 0.5
                ela_amount = min(ela_amount, 50.0)  # cap at €50bn per bank

                if ela_amount < 0.1:
                    continue

                bank.liabilities.cb_borrowing_eur_bn += ela_amount
                bank.assets.cb_reserves_eur_bn += ela_amount
                bank.update_liquidity_metrics()
                bank.update_status()

                events.append(ContagionEvent(
                    tick=tick, round_num=round_num, channel="ecb_intervention",
                    source_bank_id="ECB_BANK", target_bank_id=bank.bank_id,
                    loss_eur_bn=0,
                    description=(
                        f"ECB provides €{ela_amount:.1f}bn ELA to {bank.short_name} "
                        f"(CET1: {bank.cet1_ratio*100:.1f}%, LCR: {bank.liquidity.lcr_pct:.0f}%)"
                    ),
                ))

        return events

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_funding_stress(self, bank: Bank) -> None:
        """Update the qualitative funding stress level based on LCR."""
        bank.update_liquidity_metrics()
        lcr = bank.liquidity.lcr_pct
        if lcr >= 100:
            bank.funding_stress = FundingStress.NONE
        elif lcr >= 80:
            bank.funding_stress = FundingStress.MILD
        elif lcr >= 50:
            bank.funding_stress = FundingStress.MODERATE
        else:
            bank.funding_stress = FundingStress.SEVERE

    # ------------------------------------------------------------------
    # Network analysis
    # ------------------------------------------------------------------

    def get_network_graph(self) -> dict:
        """Return the interbank network as nodes + edges for visualization."""
        nodes = []
        for bank in self.banks.values():
            nodes.append({
                "id": bank.bank_id,
                "name": bank.short_name,
                "type": bank.bank_type.value,
                "country": bank.country,
                "status": bank.status.value,
                "total_assets_eur_bn": round(bank.total_assets_eur_bn, 1),
                "cet1_ratio_pct": round(bank.cet1_ratio * 100, 2),
                "lcr_pct": round(bank.liquidity.lcr_pct, 1),
                "credit_spread_bps": round(bank.credit_spread_bps, 0),
            })

        edges = []
        for exp in self.interbank_exposures:
            edges.append({
                "source": exp.lender_id,
                "target": exp.borrower_id,
                "amount_eur_bn": round(exp.amount_eur_bn, 2),
                "rate_bps": round(exp.rate_bps, 0),
                "maturity_days": exp.maturity_days,
                "is_secured": exp.is_secured,
            })

        return {"nodes": nodes, "edges": edges}

    def system_summary(self) -> dict:
        """Aggregate system-level risk metrics."""
        banks = [b for b in self.banks.values() if b.bank_type != BankType.CENTRAL_BANK]
        if not banks:
            return {}

        total_assets = sum(b.total_assets_eur_bn for b in banks)
        total_capital = sum(b.capital.total_capital_eur_bn for b in banks)
        avg_cet1 = sum(b.cet1_ratio for b in banks) / len(banks)
        avg_lcr = sum(b.liquidity.lcr_pct for b in banks) / len(banks)
        avg_spread = sum(b.credit_spread_bps for b in banks) / len(banks)
        n_stressed = sum(1 for b in banks if b.status in (BankStatus.STRESSED, BankStatus.CRITICAL))
        n_failed = sum(1 for b in banks if b.status in (BankStatus.FAILED, BankStatus.RESOLUTION))

        return {
            "total_assets_eur_bn": round(total_assets, 1),
            "total_capital_eur_bn": round(total_capital, 1),
            "system_leverage": round(total_assets / max(total_capital, 0.1), 1),
            "avg_cet1_ratio_pct": round(avg_cet1 * 100, 2),
            "avg_lcr_pct": round(avg_lcr, 1),
            "avg_credit_spread_bps": round(avg_spread, 0),
            "banks_normal": len(banks) - n_stressed - n_failed,
            "banks_stressed": n_stressed,
            "banks_failed": n_failed,
            "total_interbank_exposure_eur_bn": round(
                sum(e.amount_eur_bn for e in self.interbank_exposures), 1,
            ),
        }
