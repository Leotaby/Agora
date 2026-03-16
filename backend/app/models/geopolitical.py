"""
models/geopolitical.py - Sanctions, Alliances, Treaties

The geopolitical wiring of the world. This is what makes NEXUS
different from any pure financial model: sanctions cut off SWIFT,
alliances trigger coordinated responses, treaties constrain policy.

A sanction is a directed relationship: sender countries → target countries.
Its effects cascade through: trade flows → FX reserves → household income.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class SanctionMeasure(str, Enum):
    SWIFT_EXCLUSION      = "SWIFT"           # cut off from international payments
    ASSET_FREEZE         = "asset_freeze"    # foreign assets frozen
    TRADE_EMBARGO        = "trade_embargo"   # no bilateral trade
    ARMS_EMBARGO         = "arms_embargo"
    OIL_EXPORT_BAN       = "oil_export_ban"
    TECH_EXPORT_BAN      = "tech_export_ban"
    TRAVEL_BAN           = "travel_ban"
    FINANCIAL_BLACKLIST  = "financial_blacklist"
    SECONDARY_SANCTIONS  = "secondary_sanctions"  # penalize third parties too


class AllianceType(str, Enum):
    MILITARY            = "military"
    ECONOMIC            = "economic"
    POLITICAL           = "political"
    SECURITY_INTEL      = "security_intelligence"
    MONETARY_UNION      = "monetary_union"
    TRADE_BLOC          = "trade_bloc"


@dataclass
class SanctionsRegime:
    """
    A sanctions regime - a set of measures imposed by sender countries on target countries.

    Examples:
    - USA + EU + UK → Russia (post-2022): SWIFT exclusion, asset freeze, oil cap
    - USA → Iran (JCPOA era): financial blacklist, oil export ban
    - UN → North Korea: arms embargo, tech ban
    """
    regime_id: str
    name: str
    sender_countries: list[str]       # ISO2 list of sanctioning countries
    target_countries: list[str]       # ISO2 list of sanctioned countries
    measures: list[SanctionMeasure]
    imposed_date: Optional[date] = None
    active: bool = True

    # Economic impact parameters
    gdp_impact_annual_pct: float = 0.0     # estimated annual GDP hit on target
    trade_reduction_pct: float = 0.0       # % reduction in trade volume
    reserve_loss_usd_bn: float = 0.0       # frozen reserves
    inflation_impact_pct: float = 0.0      # inflation surge from import costs

    def affects_swift(self) -> bool:
        return SanctionMeasure.SWIFT_EXCLUSION in self.measures

    def affects_trade(self) -> bool:
        return SanctionMeasure.TRADE_EMBARGO in self.measures or \
               SanctionMeasure.OIL_EXPORT_BAN in self.measures

    def has_secondary_sanctions(self) -> bool:
        return SanctionMeasure.SECONDARY_SANCTIONS in self.measures


@dataclass
class Alliance:
    """A geopolitical alliance between countries."""
    alliance_id: str
    name: str
    alliance_type: AllianceType
    members: list[str]          # ISO2
    founding_year: int
    active: bool = True
    has_collective_defense: bool = False   # Article 5-type clause
    economic_integration: float = 0.0     # 0–1


# ---------------------------------------------------------------------------
# Preset sanctions regimes
# ---------------------------------------------------------------------------

def build_russia_sanctions_2022() -> SanctionsRegime:
    return SanctionsRegime(
        regime_id="RU_SANCTIONS_2022",
        name="Russia comprehensive sanctions (post-Ukraine invasion)",
        sender_countries=["US", "GB", "DE", "FR", "IT", "JP", "CA", "AU", "KR", "CH", "NO", "SE"],
        target_countries=["RU"],
        measures=[
            SanctionMeasure.SWIFT_EXCLUSION,
            SanctionMeasure.ASSET_FREEZE,
            SanctionMeasure.TECH_EXPORT_BAN,
            SanctionMeasure.OIL_EXPORT_BAN,
            SanctionMeasure.SECONDARY_SANCTIONS,
        ],
        imposed_date=date(2022, 2, 28),
        gdp_impact_annual_pct=-5.0,
        trade_reduction_pct=40.0,
        reserve_loss_usd_bn=300.0,
        inflation_impact_pct=8.0,
    )


def build_iran_sanctions() -> SanctionsRegime:
    return SanctionsRegime(
        regime_id="IR_SANCTIONS_JCPOA",
        name="Iran comprehensive sanctions (JCPOA collapse)",
        sender_countries=["US", "GB", "DE", "FR", "IT", "JP", "CA"],
        target_countries=["IR"],
        measures=[
            SanctionMeasure.SWIFT_EXCLUSION,
            SanctionMeasure.ASSET_FREEZE,
            SanctionMeasure.OIL_EXPORT_BAN,
            SanctionMeasure.FINANCIAL_BLACKLIST,
            SanctionMeasure.SECONDARY_SANCTIONS,
        ],
        gdp_impact_annual_pct=-8.0,
        trade_reduction_pct=70.0,
        reserve_loss_usd_bn=100.0,
        inflation_impact_pct=35.0,
    )


def build_north_korea_sanctions() -> SanctionsRegime:
    return SanctionsRegime(
        regime_id="KP_UN_SANCTIONS",
        name="UN Security Council North Korea sanctions",
        sender_countries=["US", "GB", "FR", "DE", "JP", "KR", "AU", "CA"],
        target_countries=["KP"],
        measures=[
            SanctionMeasure.ARMS_EMBARGO,
            SanctionMeasure.TRADE_EMBARGO,
            SanctionMeasure.TECH_EXPORT_BAN,
            SanctionMeasure.FINANCIAL_BLACKLIST,
            SanctionMeasure.TRAVEL_BAN,
        ],
        gdp_impact_annual_pct=-15.0,
        trade_reduction_pct=90.0,
    )


# ---------------------------------------------------------------------------
# Preset alliances
# ---------------------------------------------------------------------------

def build_nato() -> Alliance:
    return Alliance(
        alliance_id="NATO",
        name="North Atlantic Treaty Organization",
        alliance_type=AllianceType.MILITARY,
        members=["US", "GB", "DE", "FR", "IT", "CA", "NO", "BE", "NL", "DK",
                 "IS", "LU", "PT", "TR", "GR", "ES", "CZ", "HU", "PL", "SK",
                 "SI", "EE", "LV", "LT", "BG", "RO", "HR", "MK", "ME", "AL",
                 "FI", "SE"],
        founding_year=1949,
        has_collective_defense=True,
        economic_integration=0.3,
    )


def build_eu() -> Alliance:
    return Alliance(
        alliance_id="EU",
        name="European Union",
        alliance_type=AllianceType.TRADE_BLOC,
        members=["DE", "FR", "IT", "ES", "NL", "BE", "SE", "PL", "AT",
                 "DK", "FI", "IE", "PT", "GR", "CZ", "HU", "RO", "BG",
                 "SK", "HR", "SI", "EE", "LV", "LT", "LU", "CY", "MT"],
        founding_year=1993,
        has_collective_defense=False,
        economic_integration=0.9,
    )


def build_brics() -> Alliance:
    return Alliance(
        alliance_id="BRICS",
        name="BRICS+ (expanded)",
        alliance_type=AllianceType.ECONOMIC,
        members=["BR", "RU", "IN", "CN", "ZA", "IR", "AE", "SA", "ET", "EG", "AR"],
        founding_year=2009,
        has_collective_defense=False,
        economic_integration=0.15,
    )


def build_shanghai_cooperation() -> Alliance:
    return Alliance(
        alliance_id="SCO",
        name="Shanghai Cooperation Organisation",
        alliance_type=AllianceType.SECURITY_INTEL,
        members=["CN", "RU", "IN", "PK", "KZ", "KG", "TJ", "UZ", "IR"],
        founding_year=2001,
        has_collective_defense=False,
        economic_integration=0.2,
    )


def build_opec_plus() -> Alliance:
    return Alliance(
        alliance_id="OPEC_PLUS",
        name="OPEC+",
        alliance_type=AllianceType.ECONOMIC,
        members=["SA", "IR", "IQ", "KW", "AE", "QA", "LY", "NG", "DZ",
                 "GA", "GQ", "CG", "RU", "KZ", "AZ", "MX", "MY", "BH", "SD"],
        founding_year=1960,
        has_collective_defense=False,
        economic_integration=0.4,
    )


def build_all_sanctions() -> list[SanctionsRegime]:
    return [
        build_russia_sanctions_2022(),
        build_iran_sanctions(),
        build_north_korea_sanctions(),
    ]


def build_all_alliances() -> list[Alliance]:
    return [
        build_nato(),
        build_eu(),
        build_brics(),
        build_shanghai_cooperation(),
        build_opec_plus(),
    ]
