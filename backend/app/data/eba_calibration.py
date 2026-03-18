"""
data/eba_calibration.py — Real bank parameters from 2011 published sources

Sources:
  - Deutsche Bank Financial Report 2011
  - BNP Paribas Annual Report 2011
  - UniCredit Annual Report 2011
  - Commerzbank Annual Report 2011
  - BayernLB Annual Report 2011
  - EBA Capital Exercise December 2011
  - BIS Consolidated Banking Statistics Q4 2011

All figures in EUR billions unless noted.  CET1 ratios from the EBA
Capital Exercise (Dec 2011) use the EBA's Core Tier 1 definition which
preceded the full CRD IV/CRR implementation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BankCalibration:
    """Immutable snapshot of a bank's published balance-sheet data."""
    bank_id: str
    name: str
    short_name: str
    country: str

    # Size
    total_assets_eur_bn: float
    rwa_eur_bn: float                    # Basel 2.5 RWA

    # Capital
    cet1_capital_eur_bn: float           # Core Tier 1 (EBA definition)
    cet1_ratio_pct: float                # CET1 / RWA
    additional_tier1_eur_bn: float
    tier2_capital_eur_bn: float

    # Asset composition
    loans_eur_bn: float
    mortgages_eur_bn: float
    sovereign_bonds_eur_bn: float
    italian_sovereign_eur_bn: float      # BTP / Italian govt exposure
    corporate_securities_eur_bn: float
    trading_book_eur_bn: float
    derivatives_mtm_eur_bn: float
    interbank_lending_eur_bn: float
    cb_reserves_eur_bn: float

    # Liability composition
    retail_deposits_eur_bn: float
    corporate_deposits_eur_bn: float
    wholesale_funding_eur_bn: float
    interbank_borrowing_eur_bn: float
    bonds_issued_eur_bn: float
    subordinated_debt_eur_bn: float
    cb_borrowing_eur_bn: float

    # Risk metrics
    credit_spread_bps: float
    rating: str
    npl_ratio_pct: float
    net_interest_margin_pct: float
    roe_pct: float
    cost_income_ratio_pct: float

    # Regulatory
    is_gsib: bool
    gsib_surcharge_pct: float
    srep_requirement_pct: float

    # Source tracking
    calibration_source: str
    calibration_period: str


# ---------------------------------------------------------------------------
# 2011 calibration — EBA Capital Exercise + Annual Reports
# ---------------------------------------------------------------------------

DEUTSCHE_BANK_2011 = BankCalibration(
    bank_id="DB",
    name="Deutsche Bank AG",
    short_name="DBK",
    country="DE",
    # Deutsche Bank Financial Report 2011: total assets EUR 2,164bn
    total_assets_eur_bn=2164.0,
    # EBA Capital Exercise Dec 2011: RWA EUR 381bn (Basel 2.5)
    rwa_eur_bn=381.0,
    # EBA CT1 capital: EUR 36.5bn, ratio 9.6%
    cet1_capital_eur_bn=36.5,
    cet1_ratio_pct=9.6,
    additional_tier1_eur_bn=5.2,
    tier2_capital_eur_bn=7.8,
    # Asset breakdown from Financial Report 2011
    loans_eur_bn=412.0,
    mortgages_eur_bn=95.0,
    sovereign_bonds_eur_bn=46.0,
    italian_sovereign_eur_bn=8.1,       # DB had limited direct Italy exposure
    corporate_securities_eur_bn=58.0,
    trading_book_eur_bn=238.0,          # trading assets
    derivatives_mtm_eur_bn=50.0,        # net derivatives after netting
    interbank_lending_eur_bn=120.0,
    cb_reserves_eur_bn=145.0,           # ECB deposits
    # Liabilities
    retail_deposits_eur_bn=295.0,
    corporate_deposits_eur_bn=286.0,
    wholesale_funding_eur_bn=332.0,     # heavy wholesale reliance
    interbank_borrowing_eur_bn=98.0,
    bonds_issued_eur_bn=200.0,
    subordinated_debt_eur_bn=13.0,
    cb_borrowing_eur_bn=20.0,
    # Risk
    credit_spread_bps=190.0,            # CDS 5Y spread late 2011
    rating="A+",                         # S&P at end-2011
    npl_ratio_pct=1.8,
    net_interest_margin_pct=1.15,
    roe_pct=8.2,
    cost_income_ratio_pct=78.0,
    # Regulatory
    is_gsib=True,
    gsib_surcharge_pct=2.0,
    srep_requirement_pct=10.5,
    calibration_source="Deutsche Bank Financial Report 2011; EBA Capital Exercise Dec 2011",
    calibration_period="2011-Q4",
)


BNP_PARIBAS_2011 = BankCalibration(
    bank_id="BNP",
    name="BNP Paribas SA",
    short_name="BNP",
    country="FR",
    # BNP Paribas Annual Report 2011: total assets EUR 1,965bn
    total_assets_eur_bn=1965.0,
    # EBA: RWA EUR 614bn
    rwa_eur_bn=614.0,
    # EBA CT1 capital: EUR 55.2bn, ratio 9.0%
    cet1_capital_eur_bn=55.2,
    cet1_ratio_pct=9.0,
    additional_tier1_eur_bn=7.8,
    tier2_capital_eur_bn=12.5,
    # Assets
    loans_eur_bn=693.0,
    mortgages_eur_bn=185.0,
    sovereign_bonds_eur_bn=78.0,        # eurozone sovereign portfolio
    italian_sovereign_eur_bn=21.3,      # BNL subsidiary = major Italy exposure
    corporate_securities_eur_bn=72.0,
    trading_book_eur_bn=180.0,
    derivatives_mtm_eur_bn=38.0,
    interbank_lending_eur_bn=90.0,
    cb_reserves_eur_bn=129.0,
    # Liabilities
    retail_deposits_eur_bn=544.0,
    corporate_deposits_eur_bn=285.0,
    wholesale_funding_eur_bn=310.0,
    interbank_borrowing_eur_bn=75.0,
    bonds_issued_eur_bn=230.0,
    subordinated_debt_eur_bn=20.0,
    cb_borrowing_eur_bn=25.0,
    # Risk
    credit_spread_bps=220.0,            # CDS 5Y late 2011 — elevated
    rating="AA-",
    npl_ratio_pct=3.2,                  # includes BNL Italian NPLs
    net_interest_margin_pct=1.42,
    roe_pct=8.9,
    cost_income_ratio_pct=63.0,
    # Regulatory
    is_gsib=True,
    gsib_surcharge_pct=1.5,
    srep_requirement_pct=10.0,
    calibration_source="BNP Paribas Annual Report 2011; EBA Capital Exercise Dec 2011",
    calibration_period="2011-Q4",
)


UNICREDIT_2011 = BankCalibration(
    bank_id="UCG",
    name="UniCredit SpA",
    short_name="UCG",
    country="IT",
    # UniCredit Annual Report 2011: total assets EUR 926bn
    total_assets_eur_bn=926.0,
    # EBA: RWA EUR 452bn
    rwa_eur_bn=452.0,
    # EBA CT1: EUR 33.4bn, ratio 7.4% — SHORTFALL BANK
    # EBA identified EUR 7.97bn capital shortfall
    cet1_capital_eur_bn=33.4,
    cet1_ratio_pct=7.4,
    additional_tier1_eur_bn=4.5,
    tier2_capital_eur_bn=8.2,
    # Assets
    loans_eur_bn=559.0,
    mortgages_eur_bn=82.0,
    sovereign_bonds_eur_bn=78.0,
    italian_sovereign_eur_bn=47.0,      # massive BTP book
    corporate_securities_eur_bn=28.0,
    trading_book_eur_bn=32.0,
    derivatives_mtm_eur_bn=12.0,
    interbank_lending_eur_bn=42.0,
    cb_reserves_eur_bn=93.0,
    # Liabilities
    retail_deposits_eur_bn=320.0,
    corporate_deposits_eur_bn=145.0,
    wholesale_funding_eur_bn=98.0,
    interbank_borrowing_eur_bn=55.0,
    bonds_issued_eur_bn=160.0,
    subordinated_debt_eur_bn=12.5,
    cb_borrowing_eur_bn=48.0,           # heavy LTRO dependence
    # Risk — elevated due to sovereign crisis
    credit_spread_bps=380.0,
    rating="A-",                         # S&P had just downgraded
    npl_ratio_pct=6.1,                  # Italian NPLs already high
    net_interest_margin_pct=1.85,
    roe_pct=-9.2,                       # EUR 9.2bn net loss in 2011 (goodwill impairment)
    cost_income_ratio_pct=68.0,
    # Regulatory
    is_gsib=True,
    gsib_surcharge_pct=1.0,
    srep_requirement_pct=10.0,
    calibration_source="UniCredit Annual Report 2011; EBA Capital Exercise Dec 2011",
    calibration_period="2011-Q4",
)


COMMERZBANK_2011 = BankCalibration(
    bank_id="CBK",
    name="Commerzbank AG",
    short_name="CBK",
    country="DE",
    # Commerzbank Annual Report 2011: total assets EUR 662bn
    total_assets_eur_bn=662.0,
    # EBA: RWA EUR 235bn
    rwa_eur_bn=235.0,
    # EBA CT1: EUR 22.1bn, ratio 9.4% BEFORE sovereign buffer
    # EBA identified EUR 5.3bn shortfall after sovereign markdowns
    cet1_capital_eur_bn=22.1,
    cet1_ratio_pct=9.4,
    additional_tier1_eur_bn=2.8,
    tier2_capital_eur_bn=5.1,
    # Assets
    loans_eur_bn=273.0,
    mortgages_eur_bn=82.0,
    sovereign_bonds_eur_bn=38.0,
    italian_sovereign_eur_bn=10.2,      # significant periphery exposure
    corporate_securities_eur_bn=22.0,
    trading_book_eur_bn=28.0,
    derivatives_mtm_eur_bn=8.0,
    interbank_lending_eur_bn=35.0,
    cb_reserves_eur_bn=52.0,
    # Liabilities
    retail_deposits_eur_bn=168.0,
    corporate_deposits_eur_bn=92.0,
    wholesale_funding_eur_bn=105.0,
    interbank_borrowing_eur_bn=38.0,
    bonds_issued_eur_bn=75.0,
    subordinated_debt_eur_bn=7.5,
    cb_borrowing_eur_bn=18.0,
    # Risk
    credit_spread_bps=260.0,            # still affected by 2009 state aid
    rating="A",
    npl_ratio_pct=2.4,
    net_interest_margin_pct=1.30,
    roe_pct=1.2,                        # near breakeven, restructuring
    cost_income_ratio_pct=75.0,
    # Regulatory — not a G-SIB but systemically relevant in Germany
    is_gsib=False,
    gsib_surcharge_pct=0.0,
    srep_requirement_pct=9.5,
    calibration_source="Commerzbank Annual Report 2011; EBA Capital Exercise Dec 2011",
    calibration_period="2011-Q4",
)


BAYERNLB_2011 = BankCalibration(
    bank_id="BAYLB",
    name="Bayerische Landesbank",
    short_name="BayLB",
    country="DE",
    # BayernLB Annual Report 2011: total assets EUR 302bn
    # (down from EUR 422bn in 2008 after HGAA disposal)
    total_assets_eur_bn=302.0,
    # RWA EUR 120bn (approximate, not in EBA exercise)
    rwa_eur_bn=120.0,
    # CET1: EUR 10.5bn (includes EUR 10bn Bavarian state aid from 2008)
    cet1_capital_eur_bn=10.5,
    cet1_ratio_pct=8.8,
    additional_tier1_eur_bn=1.2,
    tier2_capital_eur_bn=2.3,
    # Assets
    loans_eur_bn=178.0,
    mortgages_eur_bn=42.0,
    sovereign_bonds_eur_bn=22.0,
    italian_sovereign_eur_bn=2.5,
    corporate_securities_eur_bn=10.0,
    trading_book_eur_bn=8.0,
    derivatives_mtm_eur_bn=3.0,
    interbank_lending_eur_bn=15.0,
    cb_reserves_eur_bn=24.0,
    # Liabilities — dangerously wholesale-dependent
    retail_deposits_eur_bn=42.0,
    corporate_deposits_eur_bn=32.0,
    wholesale_funding_eur_bn=88.0,      # Pfandbriefe + CP + repo
    interbank_borrowing_eur_bn=38.0,    # heavy interbank reliance
    bonds_issued_eur_bn=52.0,
    subordinated_debt_eur_bn=3.5,
    cb_borrowing_eur_bn=12.0,
    # Risk
    credit_spread_bps=145.0,
    rating="A-",                         # state guarantee backstop
    npl_ratio_pct=2.1,
    net_interest_margin_pct=1.05,
    roe_pct=2.8,
    cost_income_ratio_pct=82.0,
    # Regulatory
    is_gsib=False,
    gsib_surcharge_pct=0.0,
    srep_requirement_pct=9.0,
    calibration_source="BayernLB Annual Report 2011; BIS Consolidated Banking Statistics Q4 2011",
    calibration_period="2011-Q4",
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EBA_2011_BANKS: dict[str, BankCalibration] = {
    "DB":    DEUTSCHE_BANK_2011,
    "BNP":   BNP_PARIBAS_2011,
    "UCG":   UNICREDIT_2011,
    "CBK":   COMMERZBANK_2011,
    "BAYLB": BAYERNLB_2011,
}

# Actual reported 2012 CET1 ratios for validation
ACTUAL_2012_CET1_RATIOS: dict[str, float] = {
    "DBK": 11.4,
    "BNP": 9.9,
    "UCG": 9.0,
    "CBK": 9.7,
}
