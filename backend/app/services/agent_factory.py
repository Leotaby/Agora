"""
NEXUS = HumanTwin
services/agent_factory.py

Population factory — spawns calibrated HumanTwin agents.

Calibration sources per tier:
  T1  Central banks    — mandate parameters from Taylor rule literature
  T2  Macro HFs        — CFTC Commitment of Traders positioning data
  T3  Commercial banks — BIS Triennial FX Survey
  T4  Institutional AM — Pension FX hedging surveys
  T5  Professional FX  — OANDA/IG client positioning statistics
  T6  Ordinary retail  — ESMA retail trader loss reports
  T7  Households       — ECB Household Finance and Consumption Survey (HFCS)
                         20 Eurozone countries, waves 2010–2021
                         Key variables: income, wealth, debt, literacy score

Each distribution below mirrors real HFCS summary statistics.
When real data is loaded (Phase 1), these priors are replaced
by empirical draws from the actual survey microdata.
"""
from __future__ import annotations

import random
import math
from typing import Optional

from app.models.agent import HumanTwin, AgentTier, RiskTolerance


# ---------------------------------------------------------------------------
# HFCS-calibrated country profiles
# Source: ECB HFCS Wave 3 (2017) country-level medians
# ---------------------------------------------------------------------------
HFCS_COUNTRY_PROFILES: dict[str, dict] = {
    "DE": {"income_median": 43_000, "wealth_median": 70_600,  "literacy_mean": 0.62, "debt_prob": 0.45},
    "FR": {"income_median": 38_000, "wealth_median": 117_000, "literacy_mean": 0.58, "debt_prob": 0.48},
    "IT": {"income_median": 30_000, "wealth_median": 146_000, "literacy_mean": 0.52, "debt_prob": 0.25},
    "ES": {"income_median": 28_000, "wealth_median": 119_000, "literacy_mean": 0.50, "debt_prob": 0.36},
    "NL": {"income_median": 46_000, "wealth_median": 104_000, "literacy_mean": 0.68, "debt_prob": 0.55},
    "BE": {"income_median": 39_000, "wealth_median": 217_000, "literacy_mean": 0.64, "debt_prob": 0.41},
    "PT": {"income_median": 18_000, "wealth_median": 75_000,  "literacy_mean": 0.44, "debt_prob": 0.38},
    "GR": {"income_median": 14_000, "wealth_median": 51_000,  "literacy_mean": 0.40, "debt_prob": 0.22},
    "AT": {"income_median": 35_000, "wealth_median": 85_000,  "literacy_mean": 0.61, "debt_prob": 0.36},
    "FI": {"income_median": 40_000, "wealth_median": 110_000, "literacy_mean": 0.69, "debt_prob": 0.52},
}
# Fallback for non-Eurozone / unlisted countries
HFCS_DEFAULT = {"income_median": 28_000, "wealth_median": 60_000, "literacy_mean": 0.50, "debt_prob": 0.35}


def _lognormal_params(median: float, cv: float = 0.7) -> tuple[float, float]:
    """Convert a desired median and coefficient-of-variation to lognormal mu/sigma."""
    mu = math.log(median)
    sigma = math.sqrt(math.log(1 + cv ** 2))
    return mu, sigma


def _literacy_to_risk(literacy: float, rng: random.Random) -> RiskTolerance:
    """
    Map financial literacy to risk tolerance.
    Low-literacy households tend to be either very risk-averse
    (hold cash) or recklessly speculative (FOMO crypto).
    Calibrated from HFCS portfolio choice questions.
    """
    if literacy < 0.25:
        return rng.choice([RiskTolerance.VERY_LOW, RiskTolerance.HIGH])
    elif literacy < 0.45:
        return RiskTolerance.LOW
    elif literacy < 0.65:
        return RiskTolerance.MEDIUM
    elif literacy < 0.82:
        return RiskTolerance.HIGH
    else:
        return RiskTolerance.MEDIUM  # sophisticated investors are actually moderate


# ---------------------------------------------------------------------------
# Tier-specific factories
# ---------------------------------------------------------------------------

def spawn_central_bank(country: str = "US", institution: str = "Federal Reserve") -> HumanTwin:
    return HumanTwin(
        name=institution,
        tier=AgentTier.CENTRAL_BANK,
        country=country,
        income_annual_eur=0,
        net_wealth_eur=0,
        financial_literacy=1.0,
        risk_tolerance=RiskTolerance.VERY_LOW,
        loss_aversion=5.0,          # CBs are very loss-averse (mandate: stability)
        information_speed=1.0,
        usd_exposure=1.0 if country == "US" else 0.3,
        eur_exposure=0.0 if country == "US" else 0.6,
        social_influence=0.0,       # CBs don't follow peers; they SET the signal
        media_exposure="proprietary_data_terminal",
    )


def spawn_macro_hf(name: str, rng: random.Random) -> HumanTwin:
    aum = rng.uniform(2e9, 200e9)
    return HumanTwin(
        name=name,
        tier=AgentTier.MACRO_HEDGE_FUND,
        country="US",
        income_annual_eur=aum * rng.uniform(0.01, 0.02),  # ~1-2% mgmt fee
        net_wealth_eur=aum,
        financial_literacy=0.97 + rng.uniform(-0.02, 0.02),
        risk_tolerance=RiskTolerance.HIGH,
        loss_aversion=rng.uniform(1.0, 1.5),   # HFs have low loss aversion
        information_speed=rng.uniform(0.92, 0.98),
        usd_exposure=rng.uniform(0.2, 0.6),
        eur_exposure=rng.uniform(0.1, 0.3),
        equity_exposure=rng.uniform(0.2, 0.5),
        social_influence=rng.uniform(0.1, 0.3),  # some herding among HFs
        media_exposure="bloomberg_terminal",
    )


def spawn_commercial_bank(name: str, rng: random.Random) -> HumanTwin:
    return HumanTwin(
        name=name,
        tier=AgentTier.COMMERCIAL_BANK,
        country=rng.choice(["US", "GB", "DE", "FR", "CH"]),
        net_wealth_eur=rng.uniform(50e9, 2e12),
        financial_literacy=0.95 + rng.uniform(-0.03, 0.03),
        risk_tolerance=RiskTolerance.MEDIUM,
        loss_aversion=rng.uniform(2.0, 3.0),
        information_speed=rng.uniform(0.88, 0.95),
        usd_exposure=0.4,
        eur_exposure=0.4,
        social_influence=0.2,
        media_exposure="interbank_feed",
    )


def spawn_institutional_am(name: str, rng: random.Random) -> HumanTwin:
    aum = rng.uniform(5e9, 500e9)
    fx_hedge_ratio = rng.uniform(0.4, 0.9)  # % of FX exposure hedged
    return HumanTwin(
        name=name,
        tier=AgentTier.INSTITUTIONAL_AM,
        country=rng.choice(["DE", "NL", "FR", "NO", "SE", "JP"]),
        net_wealth_eur=aum,
        financial_literacy=rng.uniform(0.88, 0.96),
        risk_tolerance=RiskTolerance.LOW,
        loss_aversion=rng.uniform(3.0, 4.5),
        information_speed=rng.uniform(0.60, 0.78),
        usd_exposure=rng.uniform(0.25, 0.45) * (1 - fx_hedge_ratio),
        eur_exposure=rng.uniform(0.40, 0.65),
        equity_exposure=rng.uniform(0.30, 0.70),
        social_influence=0.1,
        media_exposure="bloomberg_terminal",
    )


def spawn_professional_retail(rng: random.Random) -> HumanTwin:
    country = rng.choice(["IT", "DE", "FR", "ES", "GB", "PL", "RO"])
    return HumanTwin(
        name=f"ProTrader_{rng.randint(1000, 9999)}",
        tier=AgentTier.PROFESSIONAL_RETAIL,
        country=country,
        age=rng.randint(28, 52),
        income_annual_eur=rng.uniform(40_000, 150_000),
        net_wealth_eur=rng.lognormvariate(*_lognormal_params(80_000, 0.8)),
        financial_literacy=rng.uniform(0.62, 0.84),
        risk_tolerance=rng.choice([RiskTolerance.HIGH, RiskTolerance.VERY_HIGH]),
        loss_aversion=rng.uniform(1.2, 2.0),
        information_speed=rng.uniform(0.50, 0.68),
        usd_exposure=rng.uniform(0.10, 0.55),
        eur_exposure=rng.uniform(0.20, 0.60),
        crypto_exposure=rng.uniform(0.0, 0.15),
        social_influence=rng.uniform(0.25, 0.55),
        media_exposure=rng.choice(["twitter_fintwit", "tradingview", "bloomberg_lite"]),
    )


def spawn_ordinary_retail(rng: random.Random) -> HumanTwin:
    country = rng.choice(["IT", "DE", "FR", "ES", "RO", "PL", "HU", "CZ"])
    literacy = rng.betavariate(1.8, 4.0)  # skewed low — most retail traders have poor literacy
    return HumanTwin(
        name=f"RetailTrader_{rng.randint(10_000, 99_999)}",
        tier=AgentTier.ORDINARY_RETAIL,
        country=country,
        age=rng.randint(22, 55),
        income_annual_eur=rng.uniform(18_000, 65_000),
        net_wealth_eur=max(500, rng.lognormvariate(*_lognormal_params(8_000, 1.2))),
        financial_literacy=round(literacy, 3),
        risk_tolerance=rng.choice([RiskTolerance.HIGH, RiskTolerance.VERY_HIGH, RiskTolerance.VERY_HIGH]),
        loss_aversion=rng.uniform(2.0, 4.5),
        information_speed=rng.uniform(0.25, 0.48),
        usd_exposure=rng.uniform(0.0, 0.35),
        eur_exposure=rng.uniform(0.40, 0.90),
        crypto_exposure=rng.uniform(0.0, 0.20),
        social_influence=rng.uniform(0.55, 0.90),  # very peer-influenced
        media_exposure=rng.choice(["tiktok", "reddit_wallstreetbets", "telegram_signals", "youtube_finance"]),
    )


def spawn_household(rng: random.Random, country: Optional[str] = None) -> HumanTwin:
    """
    Spawn a household agent calibrated from HFCS country-level statistics.
    This is the most scientifically important factory function —
    the household population is what makes NEXUS different from MiroFish.
    """
    if country is None:
        # Weight by Eurozone population share
        country = rng.choices(
            list(HFCS_COUNTRY_PROFILES.keys()),
            weights=[82, 68, 60, 47, 17, 11, 10, 11, 9, 6],  # DE FR IT ES NL BE PT GR AT FI (millions)
            k=1
        )[0]

    profile = HFCS_COUNTRY_PROFILES.get(country, HFCS_DEFAULT)

    # Income: lognormal calibrated to country median
    income = max(8_000, rng.lognormvariate(*_lognormal_params(profile["income_median"], 0.65)))

    # Wealth: lognormal, more dispersed than income (HFCS shows high Gini for wealth)
    wealth = max(0, rng.lognormvariate(*_lognormal_params(profile["wealth_median"], 1.4)))

    # Debt: Bernoulli on debt_prob, then lognormal amount
    has_debt = rng.random() < profile["debt_prob"]
    debt = rng.lognormvariate(*_lognormal_params(60_000, 0.7)) if has_debt else 0.0

    # Literacy: Beta distribution calibrated to country mean
    # Beta params chosen so mean ≈ literacy_mean with realistic variance
    lit_mean = profile["literacy_mean"]
    a, b = lit_mean * 5, (1 - lit_mean) * 5
    literacy = round(rng.betavariate(max(0.1, a), max(0.1, b)), 3)

    # Crypto: Young + low literacy → FOMO adoption; High literacy → deliberate small allocation
    age = rng.randint(22, 72)
    if age < 35 and literacy < 0.4:
        crypto = rng.uniform(0.0, 0.12)  # FOMO crypto
    elif literacy > 0.7:
        crypto = rng.uniform(0.0, 0.05)  # deliberate small allocation
    else:
        crypto = rng.uniform(0.0, 0.02)

    # FX exposure: households mostly in domestic currency
    # Some USD savings in high-inflation perception countries
    usd_savings_prob = 0.25 if country in ["IT", "GR", "PT"] else 0.10
    usd_exp = rng.uniform(0.02, 0.12) if rng.random() < usd_savings_prob else 0.0

    return HumanTwin(
        name=f"HH_{country}_{rng.randint(100_000, 999_999)}",
        tier=AgentTier.HOUSEHOLD,
        country=country,
        age=age,
        income_annual_eur=round(income, 2),
        net_wealth_eur=round(max(0, wealth - debt), 2),
        debt_eur=round(debt, 2),
        financial_literacy=literacy,
        risk_tolerance=_literacy_to_risk(literacy, rng),
        loss_aversion=round(rng.uniform(1.8, 4.2), 3),
        information_speed=round(literacy * 0.18 + 0.02, 4),  # max ~0.20 for households
        usd_exposure=round(usd_exp, 4),
        eur_exposure=round(1.0 - usd_exp - crypto, 4),
        crypto_exposure=round(crypto, 4),
        social_influence=round(rng.uniform(0.40, 0.88), 3),
        media_exposure=rng.choice([
            "tv_news", "tv_news", "newspaper",  # weighted: most watch TV
            "word_of_mouth", "social_media", "none"
        ]),
    )


# ---------------------------------------------------------------------------
# Population builder — the main entry point
# ---------------------------------------------------------------------------

class AgentFactory:
    """
    Builds a full NEXUS agent population calibrated from empirical data.

    Usage:
        factory = AgentFactory(seed=42)
        agents = factory.build(n_households=1000)
    """

    # Default institutional roster (fixed set, always included)
    CENTRAL_BANKS = [
        ("US", "Federal Reserve"),
        ("EU", "European Central Bank"),
        ("JP", "Bank of Japan"),
        ("GB", "Bank of England"),
        ("CH", "Swiss National Bank"),
        ("CN", "People's Bank of China"),
    ]

    MACRO_HFS = [
        "Bridgewater Associates",
        "Brevan Howard",
        "BlueCrest Capital",
        "Caxton Associates",
        "Tudor Investment Corp",
        "Millennium Management",
    ]

    COMMERCIAL_BANKS = [
        "JPMorgan FX Desk",
        "Deutsche Bank FX",
        "Citigroup FX",
        "UBS FX Desk",
        "Barclays FX",
    ]

    INSTITUTIONAL_AMS = [
        "ABP Pension Fund (NL)",
        "CalPERS",
        "Norwegian GPFG",
        "Japanese GPIF",
        "BNP Paribas AM",
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def build(
        self,
        n_households: int = 1000,
        n_professional_retail: int = 50,
        n_ordinary_retail: int = 200,
        country_mix: Optional[list[str]] = None,
    ) -> list[HumanTwin]:
        agents: list[HumanTwin] = []

        # T1 — Central banks (fixed roster)
        for country, name in self.CENTRAL_BANKS:
            agents.append(spawn_central_bank(country, name))

        # T2 — Macro hedge funds
        for name in self.MACRO_HFS:
            agents.append(spawn_macro_hf(name, self.rng))

        # T3 — Commercial banks
        for name in self.COMMERCIAL_BANKS:
            agents.append(spawn_commercial_bank(name, self.rng))

        # T4 — Institutional AMs
        for name in self.INSTITUTIONAL_AMS:
            agents.append(spawn_institutional_am(name, self.rng))

        # T5 — Professional retail
        for _ in range(n_professional_retail):
            agents.append(spawn_professional_retail(self.rng))

        # T6 — Ordinary retail
        for _ in range(n_ordinary_retail):
            agents.append(spawn_ordinary_retail(self.rng))

        # T7 — Households (the majority)
        countries = country_mix or [None] * n_households
        for c in countries:
            agents.append(spawn_household(self.rng, country=c))

        return agents

    def summary(self, agents: list[HumanTwin]) -> dict:
        from collections import Counter
        tier_counts = Counter(a.tier.value for a in agents)
        country_counts = Counter(a.country for a in agents)
        hh = [a for a in agents if a.tier == AgentTier.HOUSEHOLD]
        return {
            "total_agents": len(agents),
            "by_tier": dict(tier_counts),
            "household_countries": dict(country_counts.most_common(10)),
            "household_literacy_mean": round(sum(a.financial_literacy for a in hh) / max(1, len(hh)), 4),
            "household_income_median": sorted(a.income_annual_eur for a in hh)[len(hh) // 2] if hh else 0,
        }
