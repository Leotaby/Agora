"""
models/bank.py — Bank balance sheets and interbank network

A bank is a leveraged balance sheet with maturity mismatch:
  - Assets: illiquid loans + liquid securities + interbank lending + CB reserves
  - Liabilities: sticky deposits + flighty wholesale funding + interbank borrowing + bonds
  - Capital: thin equity buffer absorbing losses (CET1 ratio, leverage ratio)
  - Liquidity: LCR/NSFR buffers determining survival horizon under stress

Five preset banks form an interbank network:
  ECB (central bank, lender of last resort)
  Deutsche Bank (G-SIB, massive derivatives book)
  BNP Paribas (G-SIB, diversified eurozone)
  UniCredit (Italian champion, sovereign exposure)
  Bayerische Landesbank (small, concentrated, fragile)

The interbank network tracks overnight lending between banks.
Contagion propagates through this network when one bank fails to
roll over funding or marks down assets that others hold as collateral.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BankType(str, Enum):
    CENTRAL_BANK     = "central_bank"
    GSIB             = "g_sib"              # global systemically important bank
    NATIONAL_CHAMPION = "national_champion"
    LANDESBANK       = "landesbank"          # German public-sector bank
    COMMERCIAL       = "commercial"
    INVESTMENT       = "investment"


class BankStatus(str, Enum):
    NORMAL           = "normal"
    STRESSED         = "stressed"           # LCR < 100% or CET1 < 7%
    CRITICAL         = "critical"           # LCR < 60% or CET1 < 4.5%
    RESOLUTION       = "resolution"         # being wound down / bailed in
    FAILED           = "failed"


class FundingStress(str, Enum):
    NONE             = "none"
    MILD             = "mild"               # wholesale spreads +50bp
    MODERATE         = "moderate"           # wholesale market closed, deposit outflows
    SEVERE           = "severe"             # bank run, CB facility only lifeline


# ---------------------------------------------------------------------------
# Balance sheet components
# ---------------------------------------------------------------------------

@dataclass
class AssetBook:
    """Asset side of the balance sheet (what the bank owns / is owed)."""
    loans_eur_bn: float = 0.0               # corporate + retail loans
    mortgages_eur_bn: float = 0.0           # residential mortgage book
    sovereign_bonds_eur_bn: float = 0.0     # government bond holdings
    corporate_securities_eur_bn: float = 0.0  # corporate bonds + equities
    interbank_lending_eur_bn: float = 0.0   # unsecured lending to other banks
    cb_reserves_eur_bn: float = 0.0         # deposits at central bank
    derivatives_mtm_eur_bn: float = 0.0     # net mark-to-market of derivatives book
    trading_book_eur_bn: float = 0.0        # short-term trading positions

    @property
    def total_eur_bn(self) -> float:
        return (
            self.loans_eur_bn + self.mortgages_eur_bn
            + self.sovereign_bonds_eur_bn + self.corporate_securities_eur_bn
            + self.interbank_lending_eur_bn + self.cb_reserves_eur_bn
            + self.derivatives_mtm_eur_bn + self.trading_book_eur_bn
        )

    @property
    def liquid_assets_eur_bn(self) -> float:
        """HQLA-equivalent: CB reserves + sovereign bonds (haircut applied elsewhere)."""
        return self.cb_reserves_eur_bn + self.sovereign_bonds_eur_bn * 0.95

    @property
    def risk_weighted_eur_bn(self) -> float:
        """Simplified RWA calculation."""
        return (
            self.loans_eur_bn * 0.75          # corporate: 75% risk weight
            + self.mortgages_eur_bn * 0.35    # mortgages: 35% RW
            + self.sovereign_bonds_eur_bn * 0.0  # eurozone sovereigns: 0% RW (Basel)
            + self.corporate_securities_eur_bn * 1.0
            + self.interbank_lending_eur_bn * 0.20  # interbank: 20% RW
            + self.cb_reserves_eur_bn * 0.0   # central bank: 0% RW
            + abs(self.derivatives_mtm_eur_bn) * 0.50
            + self.trading_book_eur_bn * 1.0
        )


@dataclass
class LiabilityBook:
    """Liability side of the balance sheet (what the bank owes)."""
    retail_deposits_eur_bn: float = 0.0     # insured household deposits (sticky)
    corporate_deposits_eur_bn: float = 0.0  # uninsured corporate deposits (flighty)
    wholesale_funding_eur_bn: float = 0.0   # repo, CP, CD (very flighty, short-term)
    interbank_borrowing_eur_bn: float = 0.0  # unsecured borrowing from other banks
    bonds_issued_eur_bn: float = 0.0        # senior unsecured + covered bonds
    subordinated_debt_eur_bn: float = 0.0   # T2 capital instruments
    cb_borrowing_eur_bn: float = 0.0        # central bank facility (TLTRO, MRO, ELA)

    @property
    def total_eur_bn(self) -> float:
        return (
            self.retail_deposits_eur_bn + self.corporate_deposits_eur_bn
            + self.wholesale_funding_eur_bn + self.interbank_borrowing_eur_bn
            + self.bonds_issued_eur_bn + self.subordinated_debt_eur_bn
            + self.cb_borrowing_eur_bn
        )

    @property
    def stable_funding_eur_bn(self) -> float:
        """Available stable funding for NSFR."""
        return (
            self.retail_deposits_eur_bn * 0.95   # retail deposits very stable
            + self.corporate_deposits_eur_bn * 0.50
            + self.bonds_issued_eur_bn * 0.85    # term bonds are stable
            + self.subordinated_debt_eur_bn * 1.0
            + self.cb_borrowing_eur_bn * 0.50    # CB facilities semi-stable
        )

    @property
    def runnable_funding_eur_bn(self) -> float:
        """Funding that can disappear in 30 days under stress."""
        return (
            self.wholesale_funding_eur_bn * 0.75   # 75% of wholesale won't roll
            + self.interbank_borrowing_eur_bn * 0.50
            + self.corporate_deposits_eur_bn * 0.25  # 25% of corporate deposits flee
        )


@dataclass
class CapitalPosition:
    """Capital adequacy — the equity buffer between solvency and failure."""
    cet1_capital_eur_bn: float = 0.0         # Common Equity Tier 1
    additional_tier1_eur_bn: float = 0.0     # AT1 instruments (CoCos)
    tier2_capital_eur_bn: float = 0.0        # subordinated debt counted as T2

    @property
    def tier1_capital_eur_bn(self) -> float:
        return self.cet1_capital_eur_bn + self.additional_tier1_eur_bn

    @property
    def total_capital_eur_bn(self) -> float:
        return self.tier1_capital_eur_bn + self.tier2_capital_eur_bn

    def cet1_ratio(self, rwa_eur_bn: float) -> float:
        """CET1 / RWA. Basel III minimum: 4.5%, with buffers ~10-13%."""
        if rwa_eur_bn <= 0:
            return 1.0
        return self.cet1_capital_eur_bn / rwa_eur_bn

    def leverage_ratio(self, total_assets_eur_bn: float) -> float:
        """Tier 1 / Total assets. Basel III minimum: 3%."""
        if total_assets_eur_bn <= 0:
            return 1.0
        return self.tier1_capital_eur_bn / total_assets_eur_bn


@dataclass
class LiquidityPosition:
    """Liquidity buffers — how long the bank survives if markets close."""
    lcr_pct: float = 100.0                  # Liquidity Coverage Ratio (min 100%)
    nsfr_pct: float = 100.0                 # Net Stable Funding Ratio (min 100%)
    collateral_pool_eur_bn: float = 0.0     # unencumbered collateral for repo/CB
    cash_eur_bn: float = 0.0                # actual vault cash + nostro
    survival_horizon_days: int = 30         # days until liquidity exhaustion under stress
    encumbrance_ratio: float = 0.0          # % of assets pledged as collateral

    def update_lcr(self, hqla_eur_bn: float, net_outflows_30d_eur_bn: float) -> None:
        """Recompute LCR = HQLA / Net cash outflows over 30 days."""
        if net_outflows_30d_eur_bn <= 0:
            self.lcr_pct = 999.0
        else:
            self.lcr_pct = (hqla_eur_bn / net_outflows_30d_eur_bn) * 100

    def update_nsfr(self, available_stable_funding: float, required_stable_funding: float) -> None:
        """Recompute NSFR = ASF / RSF."""
        if required_stable_funding <= 0:
            self.nsfr_pct = 999.0
        else:
            self.nsfr_pct = (available_stable_funding / required_stable_funding) * 100


# ---------------------------------------------------------------------------
# Interbank exposure
# ---------------------------------------------------------------------------

@dataclass
class InterbankExposure:
    """A directed lending relationship between two banks."""
    lender_id: str = ""
    borrower_id: str = ""
    amount_eur_bn: float = 0.0
    maturity_days: int = 1                  # 1 = overnight, 7 = 1-week, etc.
    rate_bps: float = 0.0                   # interest rate in basis points
    is_secured: bool = False                # True = repo (collateralized)
    collateral_type: str = ""               # e.g. "sovereign_bonds", "covered_bonds"


# ---------------------------------------------------------------------------
# The Bank entity
# ---------------------------------------------------------------------------

@dataclass
class Bank:
    """
    A full bank balance sheet with capital adequacy and liquidity metrics.

    The balance sheet identity holds: Assets = Liabilities + Capital.
    Deviations from this identity represent unrealized gains/losses or
    accounting gaps that the contagion engine resolves through write-downs.
    """
    bank_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    short_name: str = ""                     # ticker / abbreviation
    bank_type: BankType = BankType.COMMERCIAL
    country: str = ""                        # ISO2 headquarters
    status: BankStatus = BankStatus.NORMAL
    funding_stress: FundingStress = FundingStress.NONE

    # Balance sheet
    assets: AssetBook = field(default_factory=AssetBook)
    liabilities: LiabilityBook = field(default_factory=LiabilityBook)
    capital: CapitalPosition = field(default_factory=CapitalPosition)
    liquidity: LiquidityPosition = field(default_factory=LiquidityPosition)

    # Interbank network
    interbank_exposures: list[InterbankExposure] = field(default_factory=list)

    # Regulatory
    is_gsib: bool = False
    gsib_surcharge_pct: float = 0.0          # additional capital buffer (1-3.5%)
    srep_requirement_pct: float = 0.0        # ECB supervisory requirement
    total_buffer_requirement_pct: float = 0.0  # CET1 min + buffers

    # Risk metrics
    credit_spread_bps: float = 0.0           # CDS spread / market perception of risk
    rating: str = ""                         # S&P-style: AAA, AA+, A, BBB+, etc.
    npl_ratio_pct: float = 0.0              # non-performing loans / total loans

    # Profit
    net_interest_margin_pct: float = 0.0     # NIM
    roe_pct: float = 0.0                     # return on equity
    cost_income_ratio_pct: float = 0.0

    # ---------------------------------------------------------------
    # Derived metrics
    # ---------------------------------------------------------------

    @property
    def total_assets_eur_bn(self) -> float:
        return self.assets.total_eur_bn

    @property
    def rwa_eur_bn(self) -> float:
        return self.assets.risk_weighted_eur_bn

    @property
    def cet1_ratio(self) -> float:
        return self.capital.cet1_ratio(self.rwa_eur_bn)

    @property
    def leverage_ratio(self) -> float:
        return self.capital.leverage_ratio(self.total_assets_eur_bn)

    @property
    def balance_sheet_gap_eur_bn(self) -> float:
        """Assets - Liabilities - Capital. Should be ~0."""
        return (
            self.assets.total_eur_bn
            - self.liabilities.total_eur_bn
            - self.capital.total_capital_eur_bn
        )

    # ---------------------------------------------------------------
    # Core state checks
    # ---------------------------------------------------------------

    def is_solvent(self) -> bool:
        """Bank is solvent if CET1 ratio >= 8% (regulatory minimum + conservation buffer)."""
        return self.cet1_ratio >= 0.08

    def is_liquid(self) -> bool:
        """Bank is liquid if LCR >= 100% (Basel III minimum)."""
        return self.liquidity.lcr_pct >= 100.0

    # ---------------------------------------------------------------
    # Shock & fire-sale actions
    # ---------------------------------------------------------------

    def apply_shock(
        self,
        asset_type: str = "loans",
        writedown_pct: float = 0.0,
        deposit_run_pct: float = 0.0,
        wholesale_freeze_pct: float = 0.0,
        spread_shock_bps: float = 0.0,
    ) -> dict:
        """
        Apply a combined shock to this bank and return a report of what happened.

        Parameters:
            asset_type: which asset class to write down
            writedown_pct: % of that asset class written off
            deposit_run_pct: % of corporate deposits that flee
            wholesale_freeze_pct: % of wholesale funding that won't roll
            spread_shock_bps: CDS spread widening in basis points
        """
        report: dict = {"bank": self.short_name, "losses": []}
        asset_map = {
            "loans": "loans_eur_bn",
            "mortgages": "mortgages_eur_bn",
            "sovereign_bonds": "sovereign_bonds_eur_bn",
            "corporate_securities": "corporate_securities_eur_bn",
            "interbank_lending": "interbank_lending_eur_bn",
            "trading_book": "trading_book_eur_bn",
        }

        # 1. Asset writedown
        if writedown_pct > 0:
            attr = asset_map.get(asset_type, "loans_eur_bn")
            current = getattr(self.assets, attr)
            loss = current * writedown_pct / 100
            setattr(self.assets, attr, current - loss)
            excess = self.absorb_loss(loss)
            report["losses"].append({
                "type": "asset_writedown", "asset": asset_type,
                "loss_eur_bn": round(loss, 2), "unabsorbed_eur_bn": round(excess, 2),
            })

        # 2. Deposit run
        if deposit_run_pct > 0:
            lost = self.liabilities.corporate_deposits_eur_bn * deposit_run_pct / 100
            self.liabilities.corporate_deposits_eur_bn -= lost
            self.assets.cb_reserves_eur_bn = max(0, self.assets.cb_reserves_eur_bn - lost)
            report["losses"].append({
                "type": "deposit_run", "outflow_eur_bn": round(lost, 2),
            })

        # 3. Wholesale freeze
        if wholesale_freeze_pct > 0:
            lost = self.liabilities.wholesale_funding_eur_bn * wholesale_freeze_pct / 100
            self.liabilities.wholesale_funding_eur_bn -= lost
            self.assets.cb_reserves_eur_bn = max(0, self.assets.cb_reserves_eur_bn - lost)
            report["losses"].append({
                "type": "wholesale_freeze", "outflow_eur_bn": round(lost, 2),
            })

        # 4. Spread shock
        if spread_shock_bps > 0:
            self.credit_spread_bps += spread_shock_bps
            report["spread_bps"] = round(self.credit_spread_bps, 0)

        self.update_liquidity_metrics()
        self.update_status()
        report["status_after"] = self.status.value
        report["cet1_ratio_pct"] = round(self.cet1_ratio * 100, 2)
        report["lcr_pct"] = round(self.liquidity.lcr_pct, 1)
        return report

    def fire_sell(self, target_cash_eur_bn: float) -> float:
        """
        Sell liquid assets at a fire-sale discount to raise cash.
        Sells sovereign bonds first (3% haircut), then corporate securities (10% haircut).
        Returns the actual cash raised.
        """
        cash_raised = 0.0
        remaining_need = target_cash_eur_bn

        # Sell sovereign bonds first (most liquid, smallest haircut)
        if remaining_need > 0 and self.assets.sovereign_bonds_eur_bn > 0:
            sell_face = min(remaining_need / 0.97, self.assets.sovereign_bonds_eur_bn)
            proceeds = sell_face * 0.97  # 3% fire-sale discount
            self.assets.sovereign_bonds_eur_bn -= sell_face
            loss = sell_face - proceeds
            self.absorb_loss(loss)
            self.assets.cb_reserves_eur_bn += proceeds
            cash_raised += proceeds
            remaining_need -= proceeds

        # Sell corporate securities (less liquid, bigger haircut)
        if remaining_need > 0 and self.assets.corporate_securities_eur_bn > 0:
            sell_face = min(remaining_need / 0.90, self.assets.corporate_securities_eur_bn)
            proceeds = sell_face * 0.90  # 10% fire-sale discount
            self.assets.corporate_securities_eur_bn -= sell_face
            loss = sell_face - proceeds
            self.absorb_loss(loss)
            self.assets.cb_reserves_eur_bn += proceeds
            cash_raised += proceeds
            remaining_need -= proceeds

        self.update_liquidity_metrics()
        self.update_status()
        return cash_raised

    # ---------------------------------------------------------------
    # Status & liquidity updates
    # ---------------------------------------------------------------

    def update_status(self) -> None:
        """Recompute bank status from capital and liquidity metrics."""
        cet1 = self.cet1_ratio
        lcr = self.liquidity.lcr_pct

        if cet1 < 0 or lcr < 0:
            self.status = BankStatus.FAILED
        elif cet1 < 0.045 or lcr < 60:
            self.status = BankStatus.CRITICAL
        elif cet1 < 0.07 or lcr < 100:
            self.status = BankStatus.STRESSED
        else:
            self.status = BankStatus.NORMAL

    def update_liquidity_metrics(self) -> None:
        """Recompute LCR and NSFR from balance sheet."""
        # LCR = HQLA / Net 30-day outflows
        hqla = self.assets.liquid_assets_eur_bn + self.liquidity.cash_eur_bn
        net_outflows = self.liabilities.runnable_funding_eur_bn
        self.liquidity.update_lcr(hqla, net_outflows)

        # NSFR = Available stable funding / Required stable funding
        asf = (
            self.liabilities.stable_funding_eur_bn
            + self.capital.total_capital_eur_bn
        )
        rsf = (
            self.assets.loans_eur_bn * 0.85
            + self.assets.mortgages_eur_bn * 0.65
            + self.assets.sovereign_bonds_eur_bn * 0.05
            + self.assets.corporate_securities_eur_bn * 0.50
            + self.assets.interbank_lending_eur_bn * 0.10
            + self.assets.trading_book_eur_bn * 0.50
        )
        self.liquidity.update_nsfr(asf, rsf)

    def absorb_loss(self, loss_eur_bn: float) -> float:
        """
        Apply a loss to the capital stack (bail-in waterfall).
        Returns the amount of loss that could NOT be absorbed (excess loss).
        CET1 absorbs first, then AT1 (CoCos), then T2.
        """
        remaining = loss_eur_bn

        # CET1 absorbs first
        absorbed = min(remaining, self.capital.cet1_capital_eur_bn)
        self.capital.cet1_capital_eur_bn -= absorbed
        remaining -= absorbed

        # AT1 (CoCos convert / write down)
        absorbed = min(remaining, self.capital.additional_tier1_eur_bn)
        self.capital.additional_tier1_eur_bn -= absorbed
        remaining -= absorbed

        # T2 subordinated debt
        absorbed = min(remaining, self.capital.tier2_capital_eur_bn)
        self.capital.tier2_capital_eur_bn -= absorbed
        remaining -= absorbed

        self.update_status()
        return remaining  # unabsorbed loss = depositor losses or bailout needed

    def summary(self) -> dict:
        """Compact summary for API / UI."""
        return {
            "bank_id": self.bank_id,
            "name": self.name,
            "short_name": self.short_name,
            "type": self.bank_type.value,
            "country": self.country,
            "status": self.status.value,
            "funding_stress": self.funding_stress.value,
            "total_assets_eur_bn": round(self.total_assets_eur_bn, 1),
            "rwa_eur_bn": round(self.rwa_eur_bn, 1),
            "cet1_ratio_pct": round(self.cet1_ratio * 100, 2),
            "leverage_ratio_pct": round(self.leverage_ratio * 100, 2),
            "lcr_pct": round(self.liquidity.lcr_pct, 1),
            "nsfr_pct": round(self.liquidity.nsfr_pct, 1),
            "credit_spread_bps": round(self.credit_spread_bps, 0),
            "rating": self.rating,
            "npl_ratio_pct": round(self.npl_ratio_pct, 2),
        }


# ---------------------------------------------------------------------------
# Preset banks
# ---------------------------------------------------------------------------

def build_ecb() -> Bank:
    """European Central Bank — lender of last resort, infinite balance sheet."""
    return Bank(
        bank_id="ECB_BANK",
        name="European Central Bank",
        short_name="ECB",
        bank_type=BankType.CENTRAL_BANK,
        country="DE",
        assets=AssetBook(
            sovereign_bonds_eur_bn=4_800.0,   # QE portfolio (PSPP + PEPP)
            loans_eur_bn=2_100.0,             # TLTRO III lending to banks
            cb_reserves_eur_bn=0.0,           # CB doesn't hold reserves at itself
            interbank_lending_eur_bn=0.0,     # MRO/LTRO modeled as loans above
        ),
        liabilities=LiabilityBook(
            retail_deposits_eur_bn=0.0,
            corporate_deposits_eur_bn=0.0,
            wholesale_funding_eur_bn=0.0,
            interbank_borrowing_eur_bn=0.0,
            bonds_issued_eur_bn=0.0,
            cb_borrowing_eur_bn=0.0,          # CB doesn't borrow from itself
        ),
        capital=CapitalPosition(
            cet1_capital_eur_bn=8_900.0,      # banknotes + reserves = CB "equity"
        ),
        liquidity=LiquidityPosition(
            lcr_pct=999.0,                    # central bank has infinite liquidity
            nsfr_pct=999.0,
            collateral_pool_eur_bn=0.0,
            cash_eur_bn=0.0,
            survival_horizon_days=9999,
        ),
        rating="AAA",
        net_interest_margin_pct=0.0,
    )


def build_deutsche_bank() -> Bank:
    """Deutsche Bank — G-SIB, massive derivatives, wholesale-funded."""
    return Bank(
        bank_id="DB",
        name="Deutsche Bank AG",
        short_name="DBK",
        bank_type=BankType.GSIB,
        country="DE",
        is_gsib=True,
        gsib_surcharge_pct=2.0,
        srep_requirement_pct=10.5,
        total_buffer_requirement_pct=13.8,
        assets=AssetBook(
            loans_eur_bn=480.0,
            mortgages_eur_bn=120.0,
            sovereign_bonds_eur_bn=85.0,
            corporate_securities_eur_bn=65.0,
            interbank_lending_eur_bn=45.0,
            cb_reserves_eur_bn=130.0,
            derivatives_mtm_eur_bn=12.0,
            trading_book_eur_bn=180.0,
        ),
        liabilities=LiabilityBook(
            retail_deposits_eur_bn=310.0,
            corporate_deposits_eur_bn=220.0,
            wholesale_funding_eur_bn=250.0,     # heavy wholesale reliance
            interbank_borrowing_eur_bn=35.0,
            bonds_issued_eur_bn=180.0,
            subordinated_debt_eur_bn=18.0,
            cb_borrowing_eur_bn=25.0,
        ),
        capital=CapitalPosition(
            cet1_capital_eur_bn=48.0,
            additional_tier1_eur_bn=10.0,
            tier2_capital_eur_bn=9.0,
        ),
        liquidity=LiquidityPosition(
            lcr_pct=142.0,
            nsfr_pct=118.0,
            collateral_pool_eur_bn=120.0,
            cash_eur_bn=15.0,
            survival_horizon_days=45,
            encumbrance_ratio=0.28,
        ),
        rating="A-",
        credit_spread_bps=95.0,
        npl_ratio_pct=1.2,
        net_interest_margin_pct=1.35,
        roe_pct=7.8,
        cost_income_ratio_pct=75.0,
    )


def build_bnp_paribas() -> Bank:
    """BNP Paribas — largest eurozone bank by assets, diversified."""
    return Bank(
        bank_id="BNP",
        name="BNP Paribas SA",
        short_name="BNP",
        bank_type=BankType.GSIB,
        country="FR",
        is_gsib=True,
        gsib_surcharge_pct=1.5,
        srep_requirement_pct=10.0,
        total_buffer_requirement_pct=12.6,
        assets=AssetBook(
            loans_eur_bn=820.0,
            mortgages_eur_bn=280.0,
            sovereign_bonds_eur_bn=140.0,
            corporate_securities_eur_bn=95.0,
            interbank_lending_eur_bn=55.0,
            cb_reserves_eur_bn=180.0,
            derivatives_mtm_eur_bn=8.0,
            trading_book_eur_bn=120.0,
        ),
        liabilities=LiabilityBook(
            retail_deposits_eur_bn=580.0,
            corporate_deposits_eur_bn=310.0,
            wholesale_funding_eur_bn=300.0,
            interbank_borrowing_eur_bn=40.0,
            bonds_issued_eur_bn=280.0,
            subordinated_debt_eur_bn=22.0,
            cb_borrowing_eur_bn=30.0,
        ),
        capital=CapitalPosition(
            cet1_capital_eur_bn=85.0,
            additional_tier1_eur_bn=12.0,
            tier2_capital_eur_bn=15.0,
        ),
        liquidity=LiquidityPosition(
            lcr_pct=138.0,
            nsfr_pct=115.0,
            collateral_pool_eur_bn=160.0,
            cash_eur_bn=20.0,
            survival_horizon_days=50,
            encumbrance_ratio=0.22,
        ),
        rating="A+",
        credit_spread_bps=65.0,
        npl_ratio_pct=1.8,
        net_interest_margin_pct=1.52,
        roe_pct=10.2,
        cost_income_ratio_pct=62.0,
    )


def build_unicredit() -> Bank:
    """UniCredit — Italian champion, heavy sovereign bond exposure."""
    return Bank(
        bank_id="UCG",
        name="UniCredit SpA",
        short_name="UCG",
        bank_type=BankType.NATIONAL_CHAMPION,
        country="IT",
        is_gsib=True,
        gsib_surcharge_pct=1.0,
        srep_requirement_pct=10.0,
        total_buffer_requirement_pct=11.9,
        assets=AssetBook(
            loans_eur_bn=440.0,
            mortgages_eur_bn=130.0,
            sovereign_bonds_eur_bn=110.0,       # heavy BTP exposure
            corporate_securities_eur_bn=35.0,
            interbank_lending_eur_bn=30.0,
            cb_reserves_eur_bn=95.0,
            derivatives_mtm_eur_bn=4.0,
            trading_book_eur_bn=40.0,
        ),
        liabilities=LiabilityBook(
            retail_deposits_eur_bn=340.0,
            corporate_deposits_eur_bn=160.0,
            wholesale_funding_eur_bn=120.0,
            interbank_borrowing_eur_bn=25.0,
            bonds_issued_eur_bn=150.0,
            subordinated_debt_eur_bn=14.0,
            cb_borrowing_eur_bn=40.0,         # more TLTRO-dependent
        ),
        capital=CapitalPosition(
            cet1_capital_eur_bn=52.0,
            additional_tier1_eur_bn=8.0,
            tier2_capital_eur_bn=10.0,
        ),
        liquidity=LiquidityPosition(
            lcr_pct=155.0,
            nsfr_pct=122.0,
            collateral_pool_eur_bn=80.0,
            cash_eur_bn=10.0,
            survival_horizon_days=40,
            encumbrance_ratio=0.30,
        ),
        rating="BBB",
        credit_spread_bps=120.0,
        npl_ratio_pct=2.8,
        net_interest_margin_pct=1.75,
        roe_pct=12.5,
        cost_income_ratio_pct=52.0,
    )


def build_commerzbank() -> Bank:
    """Commerzbank — mid-tier German bank, restructuring, wholesale-heavy."""
    return Bank(
        bank_id="CBK",
        name="Commerzbank AG",
        short_name="CBK",
        bank_type=BankType.COMMERCIAL,
        country="DE",
        is_gsib=False,
        srep_requirement_pct=9.5,
        total_buffer_requirement_pct=11.5,
        assets=AssetBook(
            loans_eur_bn=230.0,
            mortgages_eur_bn=90.0,
            sovereign_bonds_eur_bn=55.0,
            corporate_securities_eur_bn=25.0,
            interbank_lending_eur_bn=18.0,
            cb_reserves_eur_bn=50.0,
            derivatives_mtm_eur_bn=3.0,
            trading_book_eur_bn=30.0,
        ),
        liabilities=LiabilityBook(
            retail_deposits_eur_bn=170.0,
            corporate_deposits_eur_bn=95.0,
            wholesale_funding_eur_bn=110.0,
            interbank_borrowing_eur_bn=20.0,
            bonds_issued_eur_bn=70.0,
            subordinated_debt_eur_bn=8.0,
            cb_borrowing_eur_bn=15.0,
        ),
        capital=CapitalPosition(
            cet1_capital_eur_bn=22.0,
            additional_tier1_eur_bn=4.0,
            tier2_capital_eur_bn=5.0,
        ),
        liquidity=LiquidityPosition(
            lcr_pct=135.0,
            nsfr_pct=112.0,
            collateral_pool_eur_bn=40.0,
            cash_eur_bn=5.0,
            survival_horizon_days=35,
            encumbrance_ratio=0.32,
        ),
        rating="BBB+",
        credit_spread_bps=105.0,
        npl_ratio_pct=1.6,
        net_interest_margin_pct=1.25,
        roe_pct=5.5,
        cost_income_ratio_pct=72.0,
    )


def build_bayerische_landesbank() -> Bank:
    """Bayerische Landesbank — small German public-sector bank, concentrated risks."""
    return Bank(
        bank_id="BAYLB",
        name="Bayerische Landesbank",
        short_name="BayLB",
        bank_type=BankType.LANDESBANK,
        country="DE",
        is_gsib=False,
        srep_requirement_pct=9.0,
        total_buffer_requirement_pct=11.0,
        assets=AssetBook(
            loans_eur_bn=110.0,               # concentrated in Bavarian corporates
            mortgages_eur_bn=55.0,
            sovereign_bonds_eur_bn=25.0,
            corporate_securities_eur_bn=12.0,
            interbank_lending_eur_bn=8.0,
            cb_reserves_eur_bn=18.0,
            derivatives_mtm_eur_bn=1.0,
            trading_book_eur_bn=5.0,
        ),
        liabilities=LiabilityBook(
            retail_deposits_eur_bn=45.0,
            corporate_deposits_eur_bn=35.0,
            wholesale_funding_eur_bn=80.0,      # dangerously wholesale-dependent
            interbank_borrowing_eur_bn=25.0,    # borrows heavily from bigger banks
            bonds_issued_eur_bn=30.0,
            subordinated_debt_eur_bn=3.0,
            cb_borrowing_eur_bn=8.0,
        ),
        capital=CapitalPosition(
            cet1_capital_eur_bn=8.0,
            additional_tier1_eur_bn=1.5,
            tier2_capital_eur_bn=2.0,
        ),
        liquidity=LiquidityPosition(
            lcr_pct=115.0,
            nsfr_pct=105.0,
            collateral_pool_eur_bn=15.0,
            cash_eur_bn=2.0,
            survival_horizon_days=25,
            encumbrance_ratio=0.40,           # high encumbrance = fragile
        ),
        rating="A-",
        credit_spread_bps=85.0,
        npl_ratio_pct=1.5,
        net_interest_margin_pct=1.10,
        roe_pct=4.2,
        cost_income_ratio_pct=78.0,
    )


# ---------------------------------------------------------------------------
# Registry and network builder
# ---------------------------------------------------------------------------

PRESET_BANKS: dict[str, callable] = {
    "ECB_BANK": build_ecb,
    "DB":       build_deutsche_bank,
    "BNP":      build_bnp_paribas,
    "UCG":      build_unicredit,
    "CBK":      build_commerzbank,
    "BAYLB":    build_bayerische_landesbank,
}


def build_all_banks() -> dict[str, Bank]:
    """Instantiate all preset banks."""
    return {bid: builder() for bid, builder in PRESET_BANKS.items()}


def wire_interbank_network(banks: dict[str, Bank]) -> list[InterbankExposure]:
    """
    Create the overnight interbank lending network.

    Structure reflects real eurozone money market:
    - G-SIBs lend to each other and to smaller banks
    - Landesbanken borrow from G-SIBs (net borrowers)
    - ECB provides standing facility (modeled separately, not here)
    - Rates based on ECB deposit facility + credit spread
    """
    exposures: list[InterbankExposure] = []

    ecb = banks.get("ECB_BANK")
    db = banks.get("DB")
    bnp = banks.get("BNP")
    ucg = banks.get("UCG")
    cbk = banks.get("CBK")
    baylb = banks.get("BAYLB")

    if not all([db, bnp, ucg, baylb]):
        return exposures

    # --- G-SIB to G-SIB (large, overnight, unsecured) ---
    # DB <-> BNP bilateral
    exposures.append(InterbankExposure(
        lender_id="DB", borrower_id="BNP",
        amount_eur_bn=8.0, maturity_days=1, rate_bps=385,
    ))
    exposures.append(InterbankExposure(
        lender_id="BNP", borrower_id="DB",
        amount_eur_bn=6.0, maturity_days=1, rate_bps=390,
    ))

    # DB <-> UCG
    exposures.append(InterbankExposure(
        lender_id="DB", borrower_id="UCG",
        amount_eur_bn=5.0, maturity_days=1, rate_bps=400,
    ))
    exposures.append(InterbankExposure(
        lender_id="UCG", borrower_id="DB",
        amount_eur_bn=3.0, maturity_days=1, rate_bps=395,
    ))

    # BNP <-> UCG
    exposures.append(InterbankExposure(
        lender_id="BNP", borrower_id="UCG",
        amount_eur_bn=7.0, maturity_days=1, rate_bps=395,
    ))
    exposures.append(InterbankExposure(
        lender_id="UCG", borrower_id="BNP",
        amount_eur_bn=4.0, maturity_days=1, rate_bps=390,
    ))

    # --- Commerzbank: mid-tier, borrows from G-SIBs, lends small amounts ---
    if cbk:
        # DB <-> CBK
        exposures.append(InterbankExposure(
            lender_id="DB", borrower_id="CBK",
            amount_eur_bn=6.0, maturity_days=1, rate_bps=393,
        ))
        exposures.append(InterbankExposure(
            lender_id="CBK", borrower_id="DB",
            amount_eur_bn=3.0, maturity_days=1, rate_bps=388,
        ))
        # BNP -> CBK
        exposures.append(InterbankExposure(
            lender_id="BNP", borrower_id="CBK",
            amount_eur_bn=4.0, maturity_days=1, rate_bps=396,
        ))
        # CBK <-> UCG
        exposures.append(InterbankExposure(
            lender_id="CBK", borrower_id="UCG",
            amount_eur_bn=3.0, maturity_days=1, rate_bps=402,
        ))
        exposures.append(InterbankExposure(
            lender_id="UCG", borrower_id="CBK",
            amount_eur_bn=2.0, maturity_days=1, rate_bps=400,
        ))
        # CBK -> BAYLB (German domestic)
        exposures.append(InterbankExposure(
            lender_id="CBK", borrower_id="BAYLB",
            amount_eur_bn=5.0, maturity_days=1, rate_bps=395,
        ))

    # --- G-SIBs lend to Landesbank (net borrower) ---
    exposures.append(InterbankExposure(
        lender_id="DB", borrower_id="BAYLB",
        amount_eur_bn=10.0, maturity_days=1, rate_bps=392,
    ))
    exposures.append(InterbankExposure(
        lender_id="BNP", borrower_id="BAYLB",
        amount_eur_bn=8.0, maturity_days=1, rate_bps=395,
    ))
    exposures.append(InterbankExposure(
        lender_id="UCG", borrower_id="BAYLB",
        amount_eur_bn=4.0, maturity_days=1, rate_bps=398,
    ))

    # --- Landesbank small reverse (some collateralized) ---
    exposures.append(InterbankExposure(
        lender_id="BAYLB", borrower_id="DB",
        amount_eur_bn=2.0, maturity_days=1, rate_bps=388,
        is_secured=True, collateral_type="covered_bonds",
    ))

    # --- 1-week term lending (less liquid) ---
    exposures.append(InterbankExposure(
        lender_id="BNP", borrower_id="DB",
        amount_eur_bn=4.0, maturity_days=7, rate_bps=400,
    ))
    exposures.append(InterbankExposure(
        lender_id="DB", borrower_id="UCG",
        amount_eur_bn=3.0, maturity_days=7, rate_bps=410,
    ))
    if cbk:
        exposures.append(InterbankExposure(
            lender_id="DB", borrower_id="CBK",
            amount_eur_bn=2.0, maturity_days=7, rate_bps=405,
        ))

    # Assign exposures to respective banks
    for exp in exposures:
        lender = banks.get(exp.lender_id)
        borrower = banks.get(exp.borrower_id)
        if lender:
            lender.interbank_exposures.append(exp)
        if borrower:
            borrower.interbank_exposures.append(exp)

    return exposures
