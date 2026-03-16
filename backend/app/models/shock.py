"""
models/shock.py

MacroShock: structured economic event injected into the simulation.
Carries quantitative magnitude, affected tiers, and per-tier response delays.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid


class ShockType(str, Enum):
    # Monetary policy
    RATE_HIKE           = "rate_hike"
    RATE_CUT            = "rate_cut"
    FORWARD_GUIDANCE    = "forward_guidance"
    QE_ANNOUNCEMENT     = "qe_announcement"

    # Macro data
    INFLATION_SURPRISE  = "inflation_surprise"
    EMPLOYMENT_SHOCK    = "employment_shock"
    GDP_SURPRISE        = "gdp_surprise"

    # Financial stability
    BANK_FAILURE        = "bank_failure"
    CREDIT_CRUNCH       = "credit_crunch"
    LIQUIDITY_CRISIS    = "liquidity_crisis"

    # FX specific
    CURRENCY_CRISIS     = "currency_crisis"
    FX_INTERVENTION     = "fx_intervention"
    CAPITAL_CONTROLS    = "capital_controls"

    # Crypto
    CRYPTO_CRASH        = "crypto_crash"
    STABLECOIN_DEPEG    = "stablecoin_depeg"

    # Geopolitical
    SANCTIONS           = "sanctions"
    TRADE_WAR           = "trade_war"


class ShockSource(str, Enum):
    FED     = "Federal Reserve"
    ECB     = "European Central Bank"
    BOJ     = "Bank of Japan"
    BOE     = "Bank of England"
    SNB     = "Swiss National Bank"
    PBOC    = "People's Bank of China"
    MARKET  = "Market Event"
    CRYPTO  = "Crypto Market"
    GEO     = "Geopolitical"


@dataclass
class MacroShock:
    """
    A structured macro event injected into the NEXUS simulation.

    This is the core input mechanism - the equivalent of MiroFish's
    seed upload, but with quantitative precision and econometric structure.
    """

    # --- Identity ---
    shock_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    shock_type: ShockType = ShockType.RATE_HIKE
    source: ShockSource = ShockSource.FED
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # --- Quantitative magnitude ---
    magnitude_bps: Optional[float] = None    # For rate changes (basis points)
    magnitude_pct: Optional[float] = None    # For % changes (e.g. GDP surprise)
    direction: int = 1                        # +1 = positive/hawkish, -1 = negative/dovish

    # --- Narrative (fed to LLM agents) ---
    headline: str = ""                        # Short headline (e.g. "Fed raises rates +75bps")
    description: str = ""                     # Full announcement text
    forward_guidance: str = ""               # Any forward guidance signal

    # --- Affected currencies ---
    primary_currency: str = "USD"
    secondary_currency: str = "EUR"

    # --- Tier-specific salience weights ---
    # How strongly this shock hits each tier (0–1)
    # Higher = tier reacts more strongly and immediately
    tier_salience: dict[str, float] = field(default_factory=lambda: {
        "T1_central_bank":        1.0,
        "T2_macro_hedge_fund":    0.95,
        "T3_commercial_bank":     0.90,
        "T4_institutional_am":    0.70,
        "T5_professional_retail": 0.60,
        "T6_ordinary_retail":     0.40,
        "T7_household":           0.15,   # households feel it last and weakest directly
    })

    # --- Processing delay by tier (in simulation rounds) ---
    tier_delay_rounds: dict[str, int] = field(default_factory=lambda: {
        "T1_central_bank":        0,
        "T2_macro_hedge_fund":    0,
        "T3_commercial_bank":     0,
        "T4_institutional_am":    1,
        "T5_professional_retail": 0,
        "T6_ordinary_retail":     1,
        "T7_household":           3,   # households lag by ~3 rounds
    })

    def to_prompt_text(self) -> str:
        """Serialize shock as natural language for agent prompts."""
        text = f"MACRO EVENT: {self.headline}\n"
        if self.magnitude_bps:
            text += f"Magnitude: {'+' if self.direction > 0 else ''}{self.magnitude_bps:.0f} basis points\n"
        if self.magnitude_pct:
            text += f"Magnitude: {'+' if self.direction > 0 else ''}{self.magnitude_pct:.2f}%\n"
        if self.description:
            text += f"Details: {self.description}\n"
        if self.forward_guidance:
            text += f"Forward guidance: {self.forward_guidance}\n"
        text += f"Primary currency affected: {self.primary_currency}/{self.secondary_currency}"
        return text

    def __repr__(self) -> str:
        return f"MacroShock(type={self.shock_type.value}, source={self.source.value}, magnitude_bps={self.magnitude_bps})"


# Preset shocks

def fed_rate_hike_75bps() -> MacroShock:
    """Fed +75bps (2022 style)."""
    return MacroShock(
        shock_type=ShockType.RATE_HIKE,
        source=ShockSource.FED,
        magnitude_bps=75.0,
        direction=1,
        headline="Federal Reserve raises federal funds rate by 75 basis points",
        description=(
            "The Federal Open Market Committee decided to raise the target range "
            "for the federal funds rate by 75 basis points to 3.75–4.00 percent. "
            "The Committee is strongly committed to returning inflation to its 2 percent objective."
        ),
        forward_guidance="The Committee anticipates that ongoing increases in the target range will be appropriate.",
        primary_currency="USD",
        secondary_currency="EUR",
    )


def ecb_surprise_cut_50bps() -> MacroShock:
    """ECB -50bps surprise cut."""
    return MacroShock(
        shock_type=ShockType.RATE_CUT,
        source=ShockSource.ECB,
        magnitude_bps=50.0,
        direction=-1,
        headline="ECB announces surprise 50bps rate cut amid growth concerns",
        description=(
            "The ECB Governing Council decided to lower the three key ECB interest rates "
            "by 50 basis points in response to deteriorating growth outlook and easing inflation."
        ),
        forward_guidance="The Governing Council remains data-dependent and stands ready to adjust all instruments.",
        primary_currency="EUR",
        secondary_currency="USD",
    )


def shock_russia_new_sanctions() -> MacroShock:
    """USA + EU expand Russia sanctions."""
    return MacroShock(
        shock_type=ShockType.SANCTIONS,
        source=ShockSource.FED,
        magnitude_pct=-8.0,
        direction=-1,
        headline="USA + EU expand Russia sanctions: new energy embargo and secondary sanctions",
        description=(
            "The US Treasury and EU Commission announce a new package targeting "
            "Russian LNG exports and imposing secondary sanctions on third-country "
            "entities trading with Russia. Turkey and India face financial penalties "
            "for continued Russian oil imports."
        ),
        forward_guidance="Secondary sanctions enforcement begins in 90 days.",
        primary_currency="RUB",
        secondary_currency="USD",
        tier_salience={
            "T1_central_bank": 1.0, "T2_macro_hedge_fund": 0.90,
            "T3_commercial_bank": 0.85, "T4_institutional_am": 0.60,
            "T5_professional_retail": 0.50, "T6_ordinary_retail": 0.25,
            "T7_household": 0.10,
        },
        tier_delay_rounds={
            "T1_central_bank": 0, "T2_macro_hedge_fund": 0,
            "T3_commercial_bank": 0, "T4_institutional_am": 1,
            "T5_professional_retail": 1, "T6_ordinary_retail": 2,
            "T7_household": 4,
        },
    )


def shock_opec_cut() -> MacroShock:
    """OPEC+ surprise 10% production cut."""
    return MacroShock(
        shock_type=ShockType.TRADE_WAR,
        source=ShockSource.FED,
        magnitude_pct=15.0,
        direction=1,
        headline="OPEC+ agrees surprise 10% production cut - Brent spikes to $98",
        description=(
            "Saudi Arabia and Russia announce a coordinated 10% production cut effective "
            "next month. Brent crude surges 15% on announcement. Energy inflation "
            "expectations jump across Europe and Asia."
        ),
        forward_guidance="Cut maintained for minimum 6 months.",
        primary_currency="USD",
        secondary_currency="EUR",
        tier_salience={
            "T1_central_bank": 0.95, "T2_macro_hedge_fund": 0.85,
            "T3_commercial_bank": 0.65, "T4_institutional_am": 0.70,
            "T5_professional_retail": 0.55, "T6_ordinary_retail": 0.40,
            "T7_household": 0.30,
        },
        tier_delay_rounds={
            "T1_central_bank": 0, "T2_macro_hedge_fund": 0,
            "T3_commercial_bank": 1, "T4_institutional_am": 1,
            "T5_professional_retail": 1, "T6_ordinary_retail": 2,
            "T7_household": 5,
        },
    )


def shock_nk_cyber_attack() -> MacroShock:
    """Lazarus Group cyberattack on Western banks."""
    return MacroShock(
        shock_type=ShockType.LIQUIDITY_CRISIS,
        source=ShockSource.MARKET,
        magnitude_bps=-200.0,
        direction=-1,
        headline="Lazarus Group cyberattack disables three major Western banks",
        description=(
            "The FBI and CISA confirm a coordinated cyberattack by the Lazarus Group "
            "has disabled payment processing at three major US banks and one European bank. "
            "SWIFT messaging disrupted for 6 hours. $1.2bn in crypto stolen from DeFi bridges."
        ),
        forward_guidance="OFAC imposes new sanctions on DPRK front companies. G7 emergency meeting called.",
        primary_currency="USD",
        secondary_currency="EUR",
        tier_salience={
            "T1_central_bank": 1.0, "T2_macro_hedge_fund": 0.95,
            "T3_commercial_bank": 1.0, "T4_institutional_am": 0.75,
            "T5_professional_retail": 0.70, "T6_ordinary_retail": 0.50,
            "T7_household": 0.20,
        },
        tier_delay_rounds={
            "T1_central_bank": 0, "T2_macro_hedge_fund": 0,
            "T3_commercial_bank": 0, "T4_institutional_am": 0,
            "T5_professional_retail": 0, "T6_ordinary_retail": 1,
            "T7_household": 2,
        },
    )


def shock_argentina_default() -> MacroShock:
    """Argentina sovereign default."""
    return MacroShock(
        shock_type=ShockType.CURRENCY_CRISIS,
        source=ShockSource.MARKET,
        magnitude_pct=-40.0,
        direction=-1,
        headline="Argentina misses IMF repayment - 9th sovereign default, peso collapses 40%",
        description=(
            "Argentina fails to make a $2.1bn IMF payment. Talks collapse. "
            "The peso collapses 40% overnight. Capital controls tightened. "
            "Contagion spreads to Turkey, Pakistan, and other high-debt EM economies."
        ),
        forward_guidance="IMF emergency team dispatched. New austerity program under negotiation.",
        primary_currency="ARS",
        secondary_currency="USD",
        tier_salience={
            "T1_central_bank": 0.70, "T2_macro_hedge_fund": 0.95,
            "T3_commercial_bank": 0.60, "T4_institutional_am": 0.75,
            "T5_professional_retail": 0.65, "T6_ordinary_retail": 0.45,
            "T7_household": 0.55,
        },
        tier_delay_rounds={
            "T1_central_bank": 0, "T2_macro_hedge_fund": 0,
            "T3_commercial_bank": 1, "T4_institutional_am": 1,
            "T5_professional_retail": 1, "T6_ordinary_retail": 1,
            "T7_household": 2,
        },
    )
