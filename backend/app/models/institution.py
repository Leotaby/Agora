"""
models/institution.py - International institutions

The rule-setters and enforcers of the world economy.
IMF imposes conditionality on bailouts. SWIFT controls payment plumbing.
Rating agencies determine borrowing costs. BIS coordinates central banks.
WTO arbitrates trade disputes. FATF decides who is a financial pariah.

These institutions are modeled as agents with mandates, decision rules,
and the power to reshape national economic policy overnight.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class InstitutionType(str, Enum):
    MONETARY_IFI         = "monetary_ifi"          # IMF, BIS
    DEVELOPMENT_IFI      = "development_ifi"        # World Bank, regional dev banks
    TRADE_BODY           = "trade_body"             # WTO, UNCTAD
    SECURITY_BODY        = "security_body"          # UN SC, NATO HQ
    REGULATORY_STANDARD  = "regulatory_standard"    # Basel Committee, FATF, IOSCO
    PAYMENT_INFRASTRUCTURE="payment_infrastructure" # SWIFT, TARGET2, CIPS
    STATISTICAL_BODY     = "statistical_body"       # BIS, Eurostat, IMF stats


@dataclass
class Institution:
    """
    An international institution with governance structure,
    mandate, and power to affect national policy.
    """
    institution_id: str
    name: str
    institution_type: InstitutionType
    headquarters_country: str       # ISO2
    member_countries: list[str]     # ISO2
    founding_year: int
    description: str

    # Power metrics
    financial_resources_usd_bn: float = 0.0   # lending capacity
    enforcement_power: float = 0.0            # 0–1 (ability to impose outcomes)
    narrative_power: float = 0.0              # 0–1 (influence over discourse)

    # Current stance
    current_focus: str = ""
    dominant_ideology: str = "Washington Consensus"


# ---------------------------------------------------------------------------
# Preset institutions
# ---------------------------------------------------------------------------

PRESET_INSTITUTIONS: list[Institution] = [

    Institution(
        "IMF", "International Monetary Fund", InstitutionType.MONETARY_IFI,
        "US", list(range(190)),  # 190 member countries
        1944,
        "Lender of last resort to sovereign borrowers. Imposes structural adjustment "
        "conditionality. Can trigger or prevent sovereign defaults.",
        financial_resources_usd_bn=1_000,
        enforcement_power=0.80,
        narrative_power=0.85,
        current_focus="Inflation, debt sustainability, climate",
    ),
    Institution(
        "WORLD_BANK", "World Bank Group", InstitutionType.DEVELOPMENT_IFI,
        "US", [],
        1944,
        "Provides loans and grants for development projects. Shapes policy in recipient "
        "countries through conditionality and technical assistance.",
        financial_resources_usd_bn=700,
        enforcement_power=0.55,
        narrative_power=0.75,
    ),
    Institution(
        "WTO", "World Trade Organization", InstitutionType.TRADE_BODY,
        "CH", [],
        1995,
        "Adjudicates international trade disputes. Sanctions non-compliance with "
        "retaliatory tariffs. Governance has been weakened by US-China tensions.",
        financial_resources_usd_bn=0,
        enforcement_power=0.45,
        narrative_power=0.60,
    ),
    Institution(
        "BIS", "Bank for International Settlements", InstitutionType.MONETARY_IFI,
        "CH", [],
        1930,
        "The central bank of central banks. Hosts the Basel Committee. Coordinates "
        "global monetary policy. Publishes the most authoritative banking data.",
        financial_resources_usd_bn=300,
        enforcement_power=0.40,
        narrative_power=0.90,
    ),
    Institution(
        "SWIFT", "Society for Worldwide Interbank Financial Telecommunication",
        InstitutionType.PAYMENT_INFRASTRUCTURE,
        "BE", [],
        1973,
        "Backbone of global financial messaging. SWIFT exclusion effectively "
        "cuts a country from the dollar-denominated global financial system. "
        "Russia's exclusion in 2022 demonstrated its power as a sanctions weapon.",
        financial_resources_usd_bn=0,
        enforcement_power=0.95,  # being excluded = economic isolation
        narrative_power=0.30,
        current_focus="Sanctions implementation, CBDC integration",
    ),
    Institution(
        "BASEL_COMMITTEE", "Basel Committee on Banking Supervision",
        InstitutionType.REGULATORY_STANDARD,
        "CH", [],
        1974,
        "Sets global banking capital and liquidity standards (Basel I/II/III/IV). "
        "Non-compliance means banks cannot access international capital markets.",
        financial_resources_usd_bn=0,
        enforcement_power=0.70,
        narrative_power=0.75,
    ),
    Institution(
        "FATF", "Financial Action Task Force", InstitutionType.REGULATORY_STANDARD,
        "FR", [],
        1989,
        "Sets global AML/CFT standards. Grey/black listing forces correspondent "
        "banks to withdraw, effectively cutting a country from the financial system.",
        financial_resources_usd_bn=0,
        enforcement_power=0.75,
        narrative_power=0.65,
    ),
    Institution(
        "UN_SC", "UN Security Council", InstitutionType.SECURITY_BODY,
        "US", [],
        1945,
        "Only body able to authorize binding international sanctions under Chapter VII. "
        "Veto power of P5 means US, UK, France, Russia, China can block any resolution.",
        financial_resources_usd_bn=3,
        enforcement_power=0.65,
        narrative_power=0.80,
    ),
    Institution(
        "ECB", "European Central Bank", InstitutionType.MONETARY_IFI,
        "DE", ["DE", "FR", "IT", "ES", "NL", "BE", "PT", "GR", "AT", "FI",
               "IE", "SK", "SI", "EE", "LV", "LT", "LU", "CY", "MT"],
        1998,
        "Sets monetary policy for the Eurozone. QE programs, rate decisions, "
        "and PEPP purchases have massive effects on sovereign spreads.",
        financial_resources_usd_bn=8_000,
        enforcement_power=0.90,
        narrative_power=0.85,
        current_focus="Inflation targeting, green transition",
    ),
    Institution(
        "OPEC_HQ", "OPEC Secretariat", InstitutionType.TRADE_BODY,
        "AT", ["SA", "IR", "IQ", "KW", "AE", "QA", "LY", "NG", "DZ", "GA", "GQ", "CG"],
        1960,
        "Coordinates oil production quotas among member states. "
        "Production cuts spike oil prices globally within days.",
        financial_resources_usd_bn=0,
        enforcement_power=0.65,
        narrative_power=0.70,
    ),
    Institution(
        "IAEA", "International Atomic Energy Agency", InstitutionType.REGULATORY_STANDARD,
        "AT", [],
        1957,
        "Inspects nuclear facilities. IAEA reports on Iran, NK, trigger "
        "sanctions escalation and geopolitical risk spikes.",
        financial_resources_usd_bn=1,
        enforcement_power=0.45,
        narrative_power=0.70,
    ),
    Institution(
        "MOODYS_INST", "Moody's / S&P / Fitch (rating agencies)",
        InstitutionType.REGULATORY_STANDARD,
        "US", [],
        1909,
        "Sovereign credit ratings determine borrowing costs. Downgrade to "
        "junk triggers automatic pension fund selling, capital flight, and crisis.",
        financial_resources_usd_bn=0,
        enforcement_power=0.80,
        narrative_power=0.88,
    ),
]


def build_all_institutions() -> dict[str, Institution]:
    return {inst.institution_id: inst for inst in PRESET_INSTITUTIONS}
