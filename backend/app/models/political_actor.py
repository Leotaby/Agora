"""
models/political_actor.py - Political actors

Governments, political parties, and ideological movements.
Elections change governments. Governments change policy.
Policy changes interest rates, fiscal stance, trade policy, sanctions.
Policy changes flow down to corporations and households.

"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Ideology(str, Enum):
    LIBERAL_PROGRESSIVE  = "liberal_progressive"
    SOCIAL_DEMOCRAT      = "social_democrat"
    CENTRIST             = "centrist"
    CONSERVATIVE         = "conservative"
    NATIONALIST          = "nationalist"
    FAR_RIGHT            = "far_right"
    COMMUNIST            = "communist"
    LIBERTARIAN          = "libertarian"
    ISLAMIST             = "islamist"
    THEOCRATIC           = "theocratic"
    AUTHORITARIAN        = "authoritarian_nationalist"
    GREEN                = "green"
    POPULIST             = "populist"


class FiscalStance(str, Enum):
    AUSTERITY            = "austerity"
    BALANCED             = "balanced"
    EXPANSIONARY         = "expansionary"
    CRISIS_SPENDING      = "crisis_spending"


class MonetaryPreference(str, Enum):
    HAWKISH              = "hawkish"          # prefers high rates, low inflation
    NEUTRAL              = "neutral"
    DOVISH               = "dovish"           # prefers low rates, growth
    UNORTHODOX           = "unorthodox"       # e.g. Erdogan's rate theory


class TradePolicy(str, Enum):
    FREE_TRADE           = "free_trade"
    MANAGED_TRADE        = "managed_trade"
    PROTECTIONIST        = "protectionist"
    MERCANTILIST         = "mercantilist"
    AUTARKY              = "autarky"


@dataclass
class PoliticalParty:
    """A political party with ideology, support base, and policy positions."""
    party_id: str
    name: str
    country_iso2: str
    ideology: Ideology
    vote_share_pct: float          # current vote share
    approval_rating: float         # leader approval 0–100
    is_governing: bool = False

    fiscal_stance: FiscalStance = FiscalStance.BALANCED
    monetary_preference: MonetaryPreference = MonetaryPreference.NEUTRAL
    trade_policy: TradePolicy = TradePolicy.MANAGED_TRADE

    pro_eu: bool = True
    pro_nato: bool = True
    sanctions_hawk: bool = False    # supports aggressive sanctions
    climate_priority: float = 0.5   # 0–1
    welfare_priority: float = 0.5   # 0–1
    market_reform_priority: float = 0.5


@dataclass
class Government:
    """The currently governing entity of a country."""
    country_iso2: str
    head_of_state: str
    head_of_government: str
    governing_parties: list[str]       # party_ids
    coalition: bool = False
    majority_strength: float = 0.5    # 0–1, higher = stronger majority
    term_start_year: int = 2024
    term_end_year: Optional[int] = None

    fiscal_stance: FiscalStance = FiscalStance.BALANCED
    monetary_preference: MonetaryPreference = MonetaryPreference.NEUTRAL
    trade_policy: TradePolicy = TradePolicy.MANAGED_TRADE
    sanctions_position: str = "cooperative"  # cooperative, resistant, initiator


# ---------------------------------------------------------------------------
# Preset political actors - the world's key governments
# ---------------------------------------------------------------------------

PRESET_PARTIES: list[PoliticalParty] = [

    # USA
    PoliticalParty("US_DEM", "Democratic Party", "US", Ideology.LIBERAL_PROGRESSIVE,
                   vote_share_pct=48.0, approval_rating=42.0, is_governing=True,
                   fiscal_stance=FiscalStance.EXPANSIONARY, monetary_preference=MonetaryPreference.DOVISH,
                   trade_policy=TradePolicy.MANAGED_TRADE, sanctions_hawk=True, climate_priority=0.8),
    PoliticalParty("US_REP", "Republican Party", "US", Ideology.CONSERVATIVE,
                   vote_share_pct=47.0, approval_rating=44.0, is_governing=False,
                   fiscal_stance=FiscalStance.AUSTERITY, monetary_preference=MonetaryPreference.HAWKISH,
                   trade_policy=TradePolicy.PROTECTIONIST, sanctions_hawk=True, climate_priority=0.2),

    # Germany
    PoliticalParty("DE_SPD", "SPD", "DE", Ideology.SOCIAL_DEMOCRAT,
                   vote_share_pct=16.0, approval_rating=25.0, is_governing=True,
                   fiscal_stance=FiscalStance.BALANCED, climate_priority=0.7),
    PoliticalParty("DE_CDU", "CDU/CSU", "DE", Ideology.CONSERVATIVE,
                   vote_share_pct=30.0, approval_rating=38.0, is_governing=False,
                   fiscal_stance=FiscalStance.AUSTERITY, monetary_preference=MonetaryPreference.HAWKISH),
    PoliticalParty("DE_AFD", "AfD", "DE", Ideology.FAR_RIGHT,
                   vote_share_pct=20.0, approval_rating=28.0, is_governing=False,
                   fiscal_stance=FiscalStance.AUSTERITY, pro_eu=False, sanctions_hawk=False,
                   climate_priority=0.1, trade_policy=TradePolicy.PROTECTIONIST),

    # Italy
    PoliticalParty("IT_FDI", "Fratelli d'Italia", "IT", Ideology.NATIONALIST,
                   vote_share_pct=29.0, approval_rating=47.0, is_governing=True,
                   fiscal_stance=FiscalStance.EXPANSIONARY, pro_eu=True,
                   trade_policy=TradePolicy.MANAGED_TRADE, sanctions_hawk=True),
    PoliticalParty("IT_PD", "Partito Democratico", "IT", Ideology.SOCIAL_DEMOCRAT,
                   vote_share_pct=19.0, approval_rating=32.0, is_governing=False,
                   fiscal_stance=FiscalStance.EXPANSIONARY, climate_priority=0.75),
    PoliticalParty("IT_M5S", "Movimento 5 Stelle", "IT", Ideology.POPULIST,
                   vote_share_pct=16.0, approval_rating=28.0, is_governing=False,
                   fiscal_stance=FiscalStance.EXPANSIONARY, pro_eu=False,
                   sanctions_hawk=False, monetary_preference=MonetaryPreference.DOVISH),

    # China
    PoliticalParty("CN_CCP", "Chinese Communist Party", "CN", Ideology.AUTHORITARIAN,
                   vote_share_pct=100.0, approval_rating=75.0, is_governing=True,
                   fiscal_stance=FiscalStance.EXPANSIONARY,
                   monetary_preference=MonetaryPreference.UNORTHODOX,
                   trade_policy=TradePolicy.MERCANTILIST, pro_eu=False, pro_nato=False,
                   sanctions_hawk=False, climate_priority=0.5),

    # Russia
    PoliticalParty("RU_UR", "United Russia", "RU", Ideology.AUTHORITARIAN,
                   vote_share_pct=77.0, approval_rating=82.0, is_governing=True,
                   fiscal_stance=FiscalStance.CRISIS_SPENDING,
                   trade_policy=TradePolicy.AUTARKY, pro_eu=False, pro_nato=False,
                   sanctions_hawk=False, climate_priority=0.1),

    # Iran
    PoliticalParty("IR_IRGC", "Islamic Revolutionary Guard Corps", "IR", Ideology.THEOCRATIC,
                   vote_share_pct=100.0, approval_rating=30.0, is_governing=True,
                   fiscal_stance=FiscalStance.CRISIS_SPENDING,
                   trade_policy=TradePolicy.AUTARKY, pro_eu=False, pro_nato=False),

    # Turkey
    PoliticalParty("TR_AKP", "AKP", "TR", Ideology.ISLAMIST,
                   vote_share_pct=40.0, approval_rating=44.0, is_governing=True,
                   fiscal_stance=FiscalStance.EXPANSIONARY,
                   monetary_preference=MonetaryPreference.UNORTHODOX,
                   trade_policy=TradePolicy.MANAGED_TRADE),

    # Argentina
    PoliticalParty("AR_LLA", "La Libertad Avanza (Milei)", "AR", Ideology.LIBERTARIAN,
                   vote_share_pct=30.0, approval_rating=52.0, is_governing=True,
                   fiscal_stance=FiscalStance.AUSTERITY,
                   monetary_preference=MonetaryPreference.HAWKISH,
                   trade_policy=TradePolicy.FREE_TRADE, climate_priority=0.1,
                   market_reform_priority=0.95),

    # UK
    PoliticalParty("GB_LAB", "Labour Party", "GB", Ideology.SOCIAL_DEMOCRAT,
                   vote_share_pct=34.0, approval_rating=38.0, is_governing=True,
                   fiscal_stance=FiscalStance.EXPANSIONARY, climate_priority=0.8),
    PoliticalParty("GB_CON", "Conservative Party", "GB", Ideology.CONSERVATIVE,
                   vote_share_pct=24.0, approval_rating=22.0, is_governing=False,
                   fiscal_stance=FiscalStance.AUSTERITY),

    # India
    PoliticalParty("IN_BJP", "BJP", "IN", Ideology.NATIONALIST,
                   vote_share_pct=37.0, approval_rating=68.0, is_governing=True,
                   fiscal_stance=FiscalStance.EXPANSIONARY, climate_priority=0.35,
                   trade_policy=TradePolicy.MANAGED_TRADE, pro_nato=False),
]


PRESET_GOVERNMENTS: list[Government] = [
    Government("US", "Joe Biden", "Joe Biden", ["US_DEM"], majority_strength=0.51,
               fiscal_stance=FiscalStance.EXPANSIONARY, sanctions_position="initiator"),
    Government("DE", "Frank-Walter Steinmeier", "Olaf Scholz", ["DE_SPD", "DE_FDP", "DE_GREENS"],
               coalition=True, majority_strength=0.48, fiscal_stance=FiscalStance.BALANCED,
               sanctions_position="cooperative"),
    Government("IT", "Sergio Mattarella", "Giorgia Meloni", ["IT_FDI", "IT_LEGA", "IT_FI"],
               coalition=True, majority_strength=0.59, fiscal_stance=FiscalStance.EXPANSIONARY,
               sanctions_position="cooperative"),
    Government("CN", "Xi Jinping", "Li Qiang", ["CN_CCP"],
               majority_strength=1.0, fiscal_stance=FiscalStance.EXPANSIONARY,
               sanctions_position="resistant"),
    Government("RU", "Vladimir Putin", "Mikhail Mishustin", ["RU_UR"],
               majority_strength=0.77, fiscal_stance=FiscalStance.CRISIS_SPENDING,
               sanctions_position="resistant"),
    Government("IR", "Ali Khamenei", "Masoud Pezeshkian", ["IR_IRGC"],
               majority_strength=1.0, fiscal_stance=FiscalStance.CRISIS_SPENDING,
               sanctions_position="resistant"),
    Government("TR", "Recep Tayyip Erdogan", "Recep Tayyip Erdogan", ["TR_AKP"],
               majority_strength=0.52, fiscal_stance=FiscalStance.EXPANSIONARY,
               sanctions_position="cooperative"),  # balances between blocs
    Government("AR", "Javier Milei", "Javier Milei", ["AR_LLA"],
               majority_strength=0.30, coalition=True, fiscal_stance=FiscalStance.AUSTERITY,
               sanctions_position="cooperative"),
    Government("GB", "Keir Starmer", "Keir Starmer", ["GB_LAB"],
               majority_strength=0.63, fiscal_stance=FiscalStance.EXPANSIONARY,
               sanctions_position="cooperative"),
    Government("IN", "Droupadi Murmu", "Narendra Modi", ["IN_BJP"],
               coalition=True, majority_strength=0.54, fiscal_stance=FiscalStance.EXPANSIONARY,
               sanctions_position="neutral"),
]


def build_all_parties() -> dict[str, PoliticalParty]:
    return {p.party_id: p for p in PRESET_PARTIES}


def build_all_governments() -> dict[str, Government]:
    return {g.country_iso2: g for g in PRESET_GOVERNMENTS}
