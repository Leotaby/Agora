"""
models/nonstate_actor.py - Non-state actors

The layer that standard economic models never include,
but which shapes financial flows more than most textbooks admit.

Terrorist groups move money through hawala, gold, and crypto.
Drug cartels control commodity supply chains and launder through real estate.
Hackers can freeze a central bank's payment system in hours.
NGOs shift narrative and sometimes capital in meaningful ways.
Rating agencies effectively govern sovereign borrowing costs.

These are modeled as agents with financial flows, influence networks,
and behavioral responses to geopolitical shocks.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NonstateType(str, Enum):
    TERRORIST_GROUP      = "terrorist_group"
    CRIMINAL_ORGANIZATION= "criminal_organization"
    HACKTIVIST_GROUP     = "hacktivist_group"
    NGO                  = "ngo"
    THINK_TANK           = "think_tank"
    RATING_AGENCY        = "rating_agency"
    MEDIA_CONGLOMERATE   = "media_conglomerate"
    SOVEREIGN_WEALTH_ADJ = "sovereign_wealth_adjacent"  # opaque state funds
    RELIGIOUS_NETWORK    = "religious_network"
    DIASPORA_NETWORK     = "diaspora_network"


class FinancingMethod(str, Enum):
    HAWALA               = "hawala"           # informal value transfer
    CRYPTOCURRENCY       = "cryptocurrency"
    CASH_SMUGGLING       = "cash_smuggling"
    TRADE_MISINVOICING   = "trade_misinvoicing"
    REAL_ESTATE          = "real_estate"
    SHELL_COMPANIES      = "shell_companies"
    DONATIONS            = "donations"
    STATE_SPONSOR        = "state_sponsor"
    DRUG_TRAFFICKING     = "drug_trafficking"
    OIL_SMUGGLING        = "oil_smuggling"
    RANSOMWARE           = "ransomware"
    CYBER_HEIST          = "cyber_heist"


class ThreatLevel(str, Enum):
    MINIMAL  = "minimal"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


@dataclass
class NonstateActor:
    """
    A non-state actor with financial flows, geographic presence,
    and capacity to influence markets, politics, and security.
    """
    actor_id: str
    name: str
    actor_type: NonstateType
    description: str

    # Geographic footprint
    headquarter_country: Optional[str] = None    # ISO2 (None = stateless/online)
    operating_countries: list[str] = field(default_factory=list)
    state_sponsors: list[str] = field(default_factory=list)   # ISO2 countries backing them

    # Financial profile
    estimated_annual_revenue_usd_mn: float = 0.0
    financing_methods: list[FinancingMethod] = field(default_factory=list)
    crypto_holdings_usd_mn: float = 0.0

    # Threat / influence
    threat_level: ThreatLevel = ThreatLevel.LOW
    cyber_capability: float = 0.0     # 0–1
    financial_disruption_capacity: float = 0.0  # ability to disrupt financial markets

    # Narrative / influence
    narrative_influence: float = 0.0  # 0–1 influence on public discourse
    active: bool = True


# ---------------------------------------------------------------------------
# Preset non-state actors
# ---------------------------------------------------------------------------

PRESET_NONSTATE_ACTORS: list[NonstateActor] = [

    # --- Terrorist / armed groups ---
    NonstateActor(
        "ISIS", "Islamic State (ISIS/Daesh)", NonstateType.TERRORIST_GROUP,
        "Transnational jihadist group. Revenue from oil smuggling, taxation, ransoms, crypto.",
        headquarter_country=None, operating_countries=["IQ", "SY", "LY", "AF", "NG"],
        state_sponsors=[], estimated_annual_revenue_usd_mn=250,
        financing_methods=[FinancingMethod.OIL_SMUGGLING, FinancingMethod.HAWALA,
                          FinancingMethod.CRYPTOCURRENCY, FinancingMethod.CASH_SMUGGLING],
        crypto_holdings_usd_mn=8, threat_level=ThreatLevel.HIGH,
        cyber_capability=0.3, financial_disruption_capacity=0.1,
    ),
    NonstateActor(
        "HEZBOLLAH", "Hezbollah", NonstateType.TERRORIST_GROUP,
        "Lebanese Shia militant group. Largest non-state military force. State-sponsored by Iran.",
        headquarter_country="LB", operating_countries=["LB", "SY", "IR", "YE"],
        state_sponsors=["IR"], estimated_annual_revenue_usd_mn=700,
        financing_methods=[FinancingMethod.STATE_SPONSOR, FinancingMethod.HAWALA,
                          FinancingMethod.TRADE_MISINVOICING, FinancingMethod.SHELL_COMPANIES],
        threat_level=ThreatLevel.HIGH, financial_disruption_capacity=0.15,
    ),
    NonstateActor(
        "HAMAS", "Hamas", NonstateType.TERRORIST_GROUP,
        "Palestinian Islamist group governing Gaza. Funded by Iran, Qatar, private donors.",
        headquarter_country="PS", operating_countries=["PS", "QA", "TR"],
        state_sponsors=["IR", "QA"], estimated_annual_revenue_usd_mn=300,
        financing_methods=[FinancingMethod.STATE_SPONSOR, FinancingMethod.CRYPTOCURRENCY,
                          FinancingMethod.HAWALA, FinancingMethod.DONATIONS],
        crypto_holdings_usd_mn=30, threat_level=ThreatLevel.HIGH,
    ),
    NonstateActor(
        "WAGNER", "Wagner Group / Africa Corps", NonstateType.CRIMINAL_ORGANIZATION,
        "Russian private military company. Operates across Africa and Middle East. Funded by Russian state.",
        headquarter_country="RU", operating_countries=["ML", "CF", "LY", "SY", "SD", "NE"],
        state_sponsors=["RU"], estimated_annual_revenue_usd_mn=2_000,
        financing_methods=[FinancingMethod.STATE_SPONSOR, FinancingMethod.CASH_SMUGGLING],
        threat_level=ThreatLevel.HIGH, financial_disruption_capacity=0.2,
    ),

    # --- Criminal organizations ---
    NonstateActor(
        "SINALOA", "Sinaloa Cartel", NonstateType.CRIMINAL_ORGANIZATION,
        "World's largest drug trafficking organization. Launders through real estate, trade, crypto.",
        headquarter_country="MX", operating_countries=["MX", "US", "CA", "CO", "GT", "EU_countries"],
        estimated_annual_revenue_usd_mn=20_000,
        financing_methods=[FinancingMethod.DRUG_TRAFFICKING, FinancingMethod.REAL_ESTATE,
                          FinancingMethod.SHELL_COMPANIES, FinancingMethod.CRYPTOCURRENCY,
                          FinancingMethod.TRADE_MISINVOICING],
        crypto_holdings_usd_mn=400, threat_level=ThreatLevel.HIGH,
        financial_disruption_capacity=0.05,
    ),
    NonstateActor(
        "NDRANGHETA", "Ndrangheta (Calabrian mafia)", NonstateType.CRIMINAL_ORGANIZATION,
        "Italy's most powerful criminal organization. Controls European cocaine market.",
        headquarter_country="IT", operating_countries=["IT", "DE", "NL", "AU", "CA", "US"],
        estimated_annual_revenue_usd_mn=55_000,
        financing_methods=[FinancingMethod.DRUG_TRAFFICKING, FinancingMethod.REAL_ESTATE,
                          FinancingMethod.SHELL_COMPANIES, FinancingMethod.TRADE_MISINVOICING],
        threat_level=ThreatLevel.HIGH, financial_disruption_capacity=0.08,
    ),
    NonstateActor(
        "RU_MAFIA", "Russian Organized Crime (Bratva)", NonstateType.CRIMINAL_ORGANIZATION,
        "Post-Soviet criminal networks with deep ties to oligarchs and intelligence services.",
        headquarter_country="RU", operating_countries=["RU", "DE", "IL", "CY", "UA", "US"],
        estimated_annual_revenue_usd_mn=8_000,
        financing_methods=[FinancingMethod.REAL_ESTATE, FinancingMethod.SHELL_COMPANIES,
                          FinancingMethod.CRYPTOCURRENCY, FinancingMethod.TRADE_MISINVOICING],
        crypto_holdings_usd_mn=200, threat_level=ThreatLevel.MEDIUM,
        financial_disruption_capacity=0.1,
    ),

    # --- State-sponsored hackers ---
    NonstateActor(
        "LAZARUS", "Lazarus Group (North Korea)", NonstateType.HACKTIVIST_GROUP,
        "NK state-sponsored cyber unit. Steals crypto and conducts ransomware attacks to evade sanctions.",
        headquarter_country="KP", operating_countries=["KP", "CN"],
        state_sponsors=["KP"], estimated_annual_revenue_usd_mn=1_700,
        financing_methods=[FinancingMethod.CYBER_HEIST, FinancingMethod.RANSOMWARE,
                          FinancingMethod.CRYPTOCURRENCY],
        crypto_holdings_usd_mn=2_000,  # largest state crypto holding after sanctions evasion
        threat_level=ThreatLevel.CRITICAL, cyber_capability=0.92,
        financial_disruption_capacity=0.40,
    ),
    NonstateActor(
        "COZY_BEAR", "Cozy Bear / APT29 (Russia/SVR)", NonstateType.HACKTIVIST_GROUP,
        "Russian intelligence cyber unit. Targets financial infrastructure, elections, and energy.",
        headquarter_country="RU", operating_countries=["RU"],
        state_sponsors=["RU"],
        financing_methods=[FinancingMethod.STATE_SPONSOR],
        threat_level=ThreatLevel.CRITICAL, cyber_capability=0.96,
        financial_disruption_capacity=0.35,
    ),

    # --- Rating agencies (enormous financial power) ---
    NonstateActor(
        "MOODYS", "Moody's Investors Service", NonstateType.RATING_AGENCY,
        "Credit rating agency. Downgrades can trigger sovereign debt crises overnight.",
        headquarter_country="US", operating_countries=["US"],
        threat_level=ThreatLevel.MINIMAL, financial_disruption_capacity=0.70,
        narrative_influence=0.85,
    ),
    NonstateActor(
        "SP", "S&P Global Ratings", NonstateType.RATING_AGENCY,
        "Credit rating agency. S&P downgrade of US in 2011 moved global markets.",
        headquarter_country="US", operating_countries=["US"],
        threat_level=ThreatLevel.MINIMAL, financial_disruption_capacity=0.70,
        narrative_influence=0.85,
    ),

    # --- NGOs / Narrative actors ---
    NonstateActor(
        "OXFAM", "Oxfam International", NonstateType.NGO,
        "Anti-poverty NGO. Publishes influential inequality reports that shape political discourse.",
        headquarter_country="GB", operating_countries=["GB", "US", "FR", "DE", "IN"],
        estimated_annual_revenue_usd_mn=950,
        financing_methods=[FinancingMethod.DONATIONS],
        narrative_influence=0.55,
    ),
    NonstateActor(
        "IMF_FATF", "Financial Action Task Force (FATF)", NonstateType.NGO,
        "AML/CFT standard-setter. Blacklisting = loss of correspondent banking = financial isolation.",
        headquarter_country="FR", operating_countries=["FR"],
        threat_level=ThreatLevel.MINIMAL, financial_disruption_capacity=0.60,
        narrative_influence=0.70,
    ),

    # --- Crypto mixing / anonymity networks ---
    NonstateActor(
        "TORNADO_CASH", "Tornado Cash (OFAC sanctioned)", NonstateType.SOVEREIGN_WEALTH_ADJ,
        "Ethereum mixing protocol. Used by Lazarus Group, cartels. OFAC sanctioned 2022.",
        headquarter_country=None, operating_countries=[],
        financing_methods=[FinancingMethod.CRYPTOCURRENCY],
        crypto_holdings_usd_mn=100,
        threat_level=ThreatLevel.HIGH, cyber_capability=0.0,
        financial_disruption_capacity=0.12,
    ),
]


def build_all_nonstate_actors() -> list[NonstateActor]:
    return list(PRESET_NONSTATE_ACTORS)
