"""
models/bank_factory.py — Build calibrated bank networks from published data

Creates Bank objects from real balance-sheet data (EBA Capital Exercise,
annual reports) rather than synthetic defaults.  The calibrated network
preserves the same interbank topology but scales exposures to match
reported balance-sheet sizes.
"""
from __future__ import annotations

from app.models.bank import (
    Bank, BankType, AssetBook, LiabilityBook, CapitalPosition,
    LiquidityPosition, InterbankExposure, build_ecb, wire_interbank_network,
)
from app.data.eba_calibration import EBA_2011_BANKS, BankCalibration


def _bank_type_for(cal: BankCalibration) -> BankType:
    """Map calibration data to BankType enum."""
    if cal.bank_id == "BAYLB":
        return BankType.LANDESBANK
    if cal.bank_id == "UCG":
        return BankType.NATIONAL_CHAMPION
    if cal.is_gsib:
        return BankType.GSIB
    return BankType.COMMERCIAL


def _build_bank_from_calibration(cal: BankCalibration) -> Bank:
    """Create a Bank instance from a BankCalibration snapshot."""
    return Bank(
        bank_id=cal.bank_id,
        name=cal.name,
        short_name=cal.short_name,
        bank_type=_bank_type_for(cal),
        country=cal.country,
        is_gsib=cal.is_gsib,
        gsib_surcharge_pct=cal.gsib_surcharge_pct,
        srep_requirement_pct=cal.srep_requirement_pct,
        total_buffer_requirement_pct=cal.srep_requirement_pct + cal.gsib_surcharge_pct + 2.5,
        assets=AssetBook(
            loans_eur_bn=cal.loans_eur_bn,
            mortgages_eur_bn=cal.mortgages_eur_bn,
            sovereign_bonds_eur_bn=cal.sovereign_bonds_eur_bn,
            corporate_securities_eur_bn=cal.corporate_securities_eur_bn,
            interbank_lending_eur_bn=cal.interbank_lending_eur_bn,
            cb_reserves_eur_bn=cal.cb_reserves_eur_bn,
            derivatives_mtm_eur_bn=cal.derivatives_mtm_eur_bn,
            trading_book_eur_bn=cal.trading_book_eur_bn,
        ),
        liabilities=LiabilityBook(
            retail_deposits_eur_bn=cal.retail_deposits_eur_bn,
            corporate_deposits_eur_bn=cal.corporate_deposits_eur_bn,
            wholesale_funding_eur_bn=cal.wholesale_funding_eur_bn,
            interbank_borrowing_eur_bn=cal.interbank_borrowing_eur_bn,
            bonds_issued_eur_bn=cal.bonds_issued_eur_bn,
            subordinated_debt_eur_bn=cal.subordinated_debt_eur_bn,
            cb_borrowing_eur_bn=cal.cb_borrowing_eur_bn,
        ),
        capital=CapitalPosition(
            cet1_capital_eur_bn=cal.cet1_capital_eur_bn,
            additional_tier1_eur_bn=cal.additional_tier1_eur_bn,
            tier2_capital_eur_bn=cal.tier2_capital_eur_bn,
        ),
        liquidity=LiquidityPosition(
            lcr_pct=100.0,   # will be recomputed
            nsfr_pct=100.0,  # will be recomputed
            cash_eur_bn=cal.cb_reserves_eur_bn * 0.10,
            collateral_pool_eur_bn=cal.sovereign_bonds_eur_bn * 0.60,
            survival_horizon_days=30,
            encumbrance_ratio=0.30,
        ),
        rating=cal.rating,
        credit_spread_bps=cal.credit_spread_bps,
        npl_ratio_pct=cal.npl_ratio_pct,
        net_interest_margin_pct=cal.net_interest_margin_pct,
        roe_pct=cal.roe_pct,
        cost_income_ratio_pct=cal.cost_income_ratio_pct,
        italian_sovereign_eur_bn=cal.italian_sovereign_eur_bn,
        calibration_source=cal.calibration_source,
        calibration_period=cal.calibration_period,
    )


def build_calibrated_network() -> tuple[dict[str, Bank], list[InterbankExposure]]:
    """
    Build a bank network calibrated to 2011 EBA / annual report data.

    Returns (banks_dict, interbank_exposures) ready for the ContagionEngine.
    The ECB is included unchanged (central bank parameters are not calibrated).
    UBS and JPMorgan retain synthetic defaults (non-eurozone, not in EBA exercise).
    """
    banks: dict[str, Bank] = {}

    # ECB — unchanged
    banks["ECB_BANK"] = build_ecb()

    # Calibrated eurozone banks
    for bank_id, calibration in EBA_2011_BANKS.items():
        banks[bank_id] = _build_bank_from_calibration(calibration)

    # UBS and JPMorgan keep synthetic defaults (not in EBA 2011 exercise)
    from app.models.bank import build_ubs, build_jpmorgan
    banks["UBS"] = build_ubs()
    banks["JPM"] = build_jpmorgan()

    # Wire interbank network (same topology, naturally sized by balance sheets)
    exposures = wire_interbank_network(banks)

    return banks, exposures
