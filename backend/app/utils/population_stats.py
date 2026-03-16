"""
Population analytics - summary statistics over the agent population.
Mirrors what an econometrician would compute before estimating a panel model:
  - Distribution of financial literacy by country
  - Income and wealth moments
  - Portfolio composition by tier
  - Tier-level information speed distribution

These are used in:
  - Paper 1: validating that the synthetic population
    matches HFCS real-data moments
  - The frontend population preview endpoint
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import NamedTuple

from app.models.agent import HumanTwin, AgentTier


class TierStats(NamedTuple):
    tier: str
    count: int
    literacy_mean: float
    literacy_std: float
    info_speed_mean: float
    usd_exposure_mean: float
    eur_exposure_mean: float
    crypto_exposure_mean: float


class PopulationStats(NamedTuple):
    total: int
    by_tier: dict[str, TierStats]
    household_income_median: float
    household_wealth_median: float
    household_literacy_mean: float
    household_literacy_gini: float
    country_distribution: dict[str, int]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / len(values))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2


def _gini(values: list[float]) -> float:
    """Gini coefficient - measures inequality. 0 = perfect equality, 1 = max inequality."""
    if not values:
        return 0.0
    s = sorted(v for v in values if v >= 0)
    n = len(s)
    if n == 0 or sum(s) == 0:
        return 0.0
    cumsum = 0.0
    for i, v in enumerate(s):
        cumsum += (2 * (i + 1) - n - 1) * v
    return cumsum / (n * sum(s))


def compute_tier_stats(agents: list[HumanTwin], tier: AgentTier) -> TierStats:
    group = [a for a in agents if a.tier == tier]
    if not group:
        return TierStats(tier.value, 0, 0, 0, 0, 0, 0, 0)
    return TierStats(
        tier=tier.value,
        count=len(group),
        literacy_mean=round(_mean([a.financial_literacy for a in group]), 4),
        literacy_std=round(_std([a.financial_literacy for a in group]), 4),
        info_speed_mean=round(_mean([a.information_speed for a in group]), 4),
        usd_exposure_mean=round(_mean([a.usd_exposure for a in group]), 4),
        eur_exposure_mean=round(_mean([a.eur_exposure for a in group]), 4),
        crypto_exposure_mean=round(_mean([a.crypto_exposure for a in group]), 4),
    )


def compute_population_stats(agents: list[HumanTwin]) -> PopulationStats:
    households = [a for a in agents if a.tier == AgentTier.HOUSEHOLD]

    country_dist: dict[str, int] = defaultdict(int)
    for a in agents:
        country_dist[a.country] += 1

    return PopulationStats(
        total=len(agents),
        by_tier={tier.value: compute_tier_stats(agents, tier) for tier in AgentTier},
        household_income_median=round(_median([a.income_annual_eur for a in households]), 2),
        household_wealth_median=round(_median([a.net_wealth_eur for a in households]), 2),
        household_literacy_mean=round(_mean([a.financial_literacy for a in households]), 4),
        household_literacy_gini=round(_gini([a.financial_literacy for a in households]), 4),
        country_distribution=dict(sorted(country_dist.items(), key=lambda x: -x[1])),
    )


def format_population_report(stats: PopulationStats) -> str:
    """Human-readable ASCII report - used in CLI scripts."""
    lines = [
        "=" * 56,
        "Population Statistics",
        "=" * 56,
        f"Total agents: {stats.total}",
        "",
        "By tier:",
    ]
    for tier_name, ts in stats.by_tier.items():
        if ts.count == 0:
            continue
        short = tier_name.split("_", 1)[-1].replace("_", " ")
        lines.append(
            f"  {short:<22} n={ts.count:<5} "
            f"literacy={ts.literacy_mean:.3f} ± {ts.literacy_std:.3f}  "
            f"speed={ts.info_speed_mean:.3f}"
        )
    lines += [
        "",
        "Household moments (HFCS comparison targets):",
        f"  Income median:     €{stats.household_income_median:>10,.0f}",
        f"  Wealth median:     €{stats.household_wealth_median:>10,.0f}",
        f"  Literacy mean:      {stats.household_literacy_mean:.4f}",
        f"  Literacy Gini:      {stats.household_literacy_gini:.4f}  (0=equal, 1=max inequality)",
        "",
        "Country distribution (households):",
    ]
    for country, count in list(stats.country_distribution.items())[:8]:
        bar = "█" * (count * 30 // max(stats.country_distribution.values()))
        lines.append(f"  {country}  {bar:<32} {count}")
    lines.append("=" * 56)
    return "\n".join(lines)
