"""
NEXUS = HumanTwin
shock.py — MacroShock: the events that hit the twin earth

A MacroShock is the equivalent of MiroFish's "seed material" —
but instead of a news article, it is a structured economic event
with a quantitative magnitude and a known set of affected agent tiers.

Examples:
    - Fed raises rate +75bps
    - ECB announces surprise cut
    - Bank failure (SVB-type)
    - Inflation print above expectations
    - Currency crisis (TRY devaluation)
    - Crypto crash (LUNA-type)
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

    This is the core input mechanism — the equivalent of MiroFish's
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


# ---- Preset shocks for development and testing ----

def fed_rate_hike_75bps() -> MacroShock:
    """The canonical NEXUS test shock: Fed +75bps, 2022-style."""
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
    """ECB emergency cut — dovish shock."""
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
