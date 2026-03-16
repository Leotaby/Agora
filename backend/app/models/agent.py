"""
models/agent.py

HumanTwin agent dataclass.

Tiers:
    T1 - Central bank       (Fed, ECB, BoJ, PBoC, BoE, SNB)
    T2 - Macro hedge fund   (Bridgewater-type)
    T3 - Commercial bank    (JPMorgan FX desk)
    T4 - Institutional AM   (pension fund, SWF)
    T5 - Professional FX    (OANDA-type trader)
    T6 - Ordinary retail FX (social media driven)
    T7 - Household          (real economy)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class AgentTier(str, Enum):
    CENTRAL_BANK        = "T1_central_bank"
    MACRO_HEDGE_FUND    = "T2_macro_hedge_fund"
    COMMERCIAL_BANK     = "T3_commercial_bank"
    INSTITUTIONAL_AM    = "T4_institutional_am"
    PROFESSIONAL_RETAIL = "T5_professional_retail"
    ORDINARY_RETAIL     = "T6_ordinary_retail"
    HOUSEHOLD           = "T7_household"


class RiskTolerance(str, Enum):
    VERY_LOW   = "very_low"
    LOW        = "low"
    MEDIUM     = "medium"
    HIGH       = "high"
    VERY_HIGH  = "very_high"


@dataclass
class HumanTwin:
    """
    A single agent in the NEXUS simulation.

    Each HumanTwin has:
    - A persistent identity (uuid + zep_memory_id for cross-session memory)
    - An economic profile calibrated from real data
    - A cognitive architecture that determines how it processes macro shocks
    - A portfolio state that evolves over simulation rounds
    """

    # --- Identity ---
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: AgentTier = AgentTier.HOUSEHOLD

    # --- Economic profile (calibrated from ECB HFCS / CFTC CoT / etc.) ---
    country: str = "IT"                  # ISO-3166 country code
    age: int = 35
    income_annual_eur: float = 30_000.0  # gross annual income
    net_wealth_eur: float = 20_000.0     # net financial wealth
    debt_eur: float = 0.0               # total liabilities

    # --- Cognitive parameters (econometrically calibrated) ---
    financial_literacy: float = 0.5      # 0–1, calibrated from HFCS literacy questions
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    loss_aversion: float = 2.25          # Kahneman-Tversky default; calibrated from surveys
    information_speed: float = 1.0       # 1.0 = instant (T1), lower = slower (T7 ~0.05)

    # --- Portfolio state ---
    usd_exposure: float = 0.0            # USD holdings as fraction of net wealth
    eur_exposure: float = 1.0            # EUR holdings as fraction of net wealth
    equity_exposure: float = 0.0         # Equity as fraction of net wealth
    crypto_exposure: float = 0.0         # Crypto as fraction of net wealth

    # --- Social network ---
    social_influence: float = 0.5        # How much peers affect decisions (0–1)
    media_exposure: str = "tv_news"      # Primary information source

    # --- Memory ---
    zep_memory_id: Optional[str] = None  # Zep Cloud session ID for persistent memory
    memory_buffer: list[str] = field(default_factory=list)

    # --- Internal state ---
    is_active: bool = True
    rounds_active: int = 0

    def to_prompt_context(self) -> str:
        """
        Serialize this agent's profile into a natural-language context string
        for the LLM prompt.
        """
        tier_descriptions = {
            AgentTier.CENTRAL_BANK:        "You are a central bank (e.g. ECB/Fed). Your mandate is price stability and financial stability. You set policy rates and conduct FX interventions.",
            AgentTier.MACRO_HEDGE_FUND:    "You are a global macro hedge fund manager. You trade carry, momentum, and fundamental macro signals across G10 FX pairs with significant leverage.",
            AgentTier.COMMERCIAL_BANK:     "You are the FX trading desk of a major commercial bank. You make markets, manage inventory risk, and process client order flow.",
            AgentTier.INSTITUTIONAL_AM:    "You are an institutional asset manager (pension fund / SWF). You rebalance FX exposure mechanically when asset prices move.",
            AgentTier.PROFESSIONAL_RETAIL: "You are an experienced retail FX trader using leveraged positions and technical analysis. You follow economic calendars and macro commentary.",
            AgentTier.ORDINARY_RETAIL:     "You are an ordinary retail FX trader. You react to social media and news headlines. You are susceptible to FOMO and loss aversion.",
            AgentTier.HOUSEHOLD:           "You are a household in the real economy. You do not trade FX directly, but you make savings, consumption, and portfolio decisions that reflect macro conditions.",
        }

        return f"""
{tier_descriptions[self.tier]}

Your profile:
- Country: {self.country}
- Age: {self.age}
- Annual income: €{self.income_annual_eur:,.0f}
- Net wealth: €{self.net_wealth_eur:,.0f}
- Financial literacy: {self.financial_literacy:.1f}/1.0 ({'low' if self.financial_literacy < 0.4 else 'medium' if self.financial_literacy < 0.7 else 'high'})
- Risk tolerance: {self.risk_tolerance.value}
- Primary information source: {self.media_exposure}
- Current USD exposure: {self.usd_exposure:.1%} of wealth
- Current EUR exposure: {self.eur_exposure:.1%} of wealth
        """.strip()

    def __repr__(self) -> str:
        return f"HumanTwin(tier={self.tier.value}, country={self.country}, literacy={self.financial_literacy:.2f})"
