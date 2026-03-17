"""
models/agent_life.py

Rich life context for each HumanTwin agent.

Extends the economic profile with:
- A role that defines how they perceive and act in the world
- Employment details (employer, salary, title)
- Household composition (family size, expenses, savings)
- Social network (who they know, who they trust for information)
- Dynamic beliefs that update each tick based on incoming messages
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentRole(str, Enum):
    """Narrative role that shapes an agent's worldview and behavior."""
    SHOP_CLERK         = "shop_clerk"
    ECB_PRESIDENT      = "ecb_president"
    SOLDIER            = "soldier"
    NK_STATE_WORKER    = "nk_state_worker"
    HEDGE_FUND_TRADER  = "hedge_fund_trader"
    TURKISH_HOUSEHOLD  = "turkish_household"
    IRANIAN_MERCHANT   = "iranian_merchant"
    CENTRAL_BANKER     = "central_banker"
    GENERIC            = "generic"


# Human-readable labels and short descriptions for each role
ROLE_PROFILES: dict[str, dict] = {
    "shop_clerk": {
        "label": "Shop Clerk",
        "icon": "🏪",
        "desc": "Watches prices daily, talks to neighbors about cost of living",
        "countries": ["IT", "FR", "DE"],
    },
    "ecb_president": {
        "label": "ECB President",
        "icon": "🏛️",
        "desc": "Sets eurozone monetary policy, broadcasts to all European agents",
        "countries": ["EU"],
    },
    "soldier": {
        "label": "Soldier",
        "icon": "🎖️",
        "desc": "Processes conflict reality, sends frontline reports to family",
        "countries": ["UA", "RU"],
    },
    "nk_state_worker": {
        "label": "NK State Worker",
        "icon": "🏭",
        "desc": "Isolated from global info, receives only state propaganda",
        "countries": ["KP"],
    },
    "hedge_fund_trader": {
        "label": "Hedge Fund Trader",
        "icon": "📈",
        "desc": "Reads Bloomberg, sends trade signals to network",
        "countries": ["US", "GB"],
    },
    "turkish_household": {
        "label": "Turkish Household",
        "icon": "🇹🇷",
        "desc": "Living through hyperinflation, converting lira to USD/gold",
        "countries": ["TR"],
    },
    "iranian_merchant": {
        "label": "Iranian Merchant",
        "icon": "🕌",
        "desc": "Evading sanctions via crypto and hawala networks",
        "countries": ["IR"],
    },
    "central_banker": {
        "label": "Central Banker",
        "icon": "🏦",
        "desc": "Sets interest rates, issues forward guidance",
        "countries": ["US", "EU", "JP", "GB", "CH", "CN"],
    },
    "generic": {
        "label": "Citizen",
        "icon": "👤",
        "desc": "Ordinary person navigating the global economy",
        "countries": [],
    },
}


@dataclass
class Employment:
    """Agent's current employment status."""
    employer_id: str = ""         # agent_id of employer or institution name
    salary_monthly_eur: float = 0.0
    job_title: str = ""
    is_employed: bool = True


@dataclass
class HouseholdLife:
    """Agent's household composition and spending."""
    family_size: int = 1
    monthly_expenses_eur: float = 0.0
    savings_rate: float = 0.10     # fraction of income saved
    housing_type: str = "renting"  # renting | owning | family


@dataclass
class AgentLife:
    """
    The 'life layer' attached to each HumanTwin.

    Maps agent_id -> rich life context including social network,
    beliefs, employment, and decision history.
    """
    agent_id: str = ""
    role: AgentRole = AgentRole.GENERIC

    # Employment
    employment: Employment = field(default_factory=Employment)

    # Household
    household: HouseholdLife = field(default_factory=HouseholdLife)

    # Social network
    information_sources: list[str] = field(default_factory=list)   # agent_ids they trust for info
    social_connections: list[str] = field(default_factory=list)    # agent_ids they know personally

    # Dynamic beliefs (updated each tick from messages)
    # Keys: inflation_outlook, currency_confidence, market_fear, conflict_risk,
    #        sanctions_severity, crypto_utility, government_trust, etc.
    beliefs: dict[str, float] = field(default_factory=dict)

    # Recent decisions (last N, for perspective view)
    recent_decisions: list[dict] = field(default_factory=list)

    # Inbox: messages received this tick (cleared each tick)
    inbox: list = field(default_factory=list)   # list[AgentMessage]

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "employment": {
                "employer_id": self.employment.employer_id,
                "salary_monthly_eur": self.employment.salary_monthly_eur,
                "job_title": self.employment.job_title,
                "is_employed": self.employment.is_employed,
            },
            "household": {
                "family_size": self.household.family_size,
                "monthly_expenses_eur": self.household.monthly_expenses_eur,
                "savings_rate": self.household.savings_rate,
                "housing_type": self.household.housing_type,
            },
            "information_sources": self.information_sources,
            "social_connections": self.social_connections,
            "beliefs": self.beliefs,
            "recent_decisions": self.recent_decisions[-10:],
        }
