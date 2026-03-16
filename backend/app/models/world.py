"""
models/world.py

Top-level simulation container.
Holds all entity layers and tracks global macro state.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.country import Country
    from app.models.institution import Institution
    from app.models.political_actor import PoliticalActor
    from app.models.geopolitical import SanctionsRegime, Alliance
    from app.models.financial_system import CentralBank, CommercialBank, Market
    from app.models.nonstate_actor import NonstateActor
    from app.models.corporation import Corporation
    from app.models.agent import HumanTwin
    from app.models.shock import MacroShock


@dataclass
class GlobalMacroState:
    """
    The world's vital signs at a given simulation tick.
    These aggregate from country-level states upward.
    """
    date: date = field(default_factory=date.today)
    world_gdp_usd_trn: float = 105.0          # ~$105T global GDP (2024)
    global_inflation_pct: float = 3.2
    usd_reserve_share: float = 0.58           # USD share of global FX reserves
    eur_reserve_share: float = 0.20
    cny_reserve_share: float = 0.025
    gold_price_usd: float = 2_400.0
    oil_price_brent: float = 82.0
    bitcoin_price_usd: float = 65_000.0
    vix: float = 18.0                          # global fear index
    global_trade_volume_index: float = 100.0   # indexed to 100
    geopolitical_risk_index: float = 45.0      # 0–100, higher = more risk


@dataclass
class World:
    """
    All entities are stored here. The simulation clock ticks forward
    round by round. Shocks are queued and dispatched to affected entities.

    Usage:
        from app.services.world_factory import WorldFactory
        world = WorldFactory().build()
        world.inject_shock(fed_rate_hike_75bps())
        world.tick()
    """

    # --- Identity ---
    name: str = "NEXUS Earth v0.1"
    simulation_date: date = field(default_factory=lambda: date(2024, 1, 1))
    tick: int = 0

    # --- Macro state ---
    macro: GlobalMacroState = field(default_factory=GlobalMacroState)

    # --- Layer 1: Nation-states ---
    countries: dict[str, "Country"] = field(default_factory=dict)

    # --- Layer 2: Political actors ---
    political_actors: dict[str, "PoliticalActor"] = field(default_factory=dict)

    # --- Layer 3: Institutions ---
    institutions: dict[str, "Institution"] = field(default_factory=dict)

    # --- Geopolitical structure ---
    sanctions_regimes: list["SanctionsRegime"] = field(default_factory=list)
    alliances: list["Alliance"] = field(default_factory=list)

    # --- Layer 4: Financial system ---
    central_banks: dict[str, "CentralBank"] = field(default_factory=dict)
    commercial_banks: list["CommercialBank"] = field(default_factory=list)
    markets: dict[str, "Market"] = field(default_factory=dict)

    # --- Layer 5: Non-state actors ---
    nonstate_actors: list["NonstateActor"] = field(default_factory=list)

    # --- Layer 6: Corporations ---
    corporations: list["Corporation"] = field(default_factory=list)

    # --- Layer 7: Households ---
    households: list["HumanTwin"] = field(default_factory=list)

    # --- Shock queue ---
    pending_shocks: list["MacroShock"] = field(default_factory=list)
    processed_shocks: list["MacroShock"] = field(default_factory=list)

    def inject_shock(self, shock: "MacroShock") -> None:
        """Queue a shock for the next tick."""
        self.pending_shocks.append(shock)

    def get_country(self, iso2: str) -> Optional["Country"]:
        return self.countries.get(iso2.upper())

    def get_institution(self, name: str) -> Optional["Institution"]:
        return self.institutions.get(name)

    def get_sanctioned_countries(self) -> list[str]:
        """Return ISO2 codes of all sanctioned countries."""
        sanctioned = set()
        for regime in self.sanctions_regimes:
            if regime.active:
                sanctioned.update(regime.target_countries)
        return list(sanctioned)

    def is_swift_connected(self, iso2: str) -> bool:
        """Return True if country has SWIFT access."""
        for regime in self.sanctions_regimes:
            if regime.active and iso2 in regime.target_countries:
                if "SWIFT" in regime.measures:
                    return False
        return True

    def bilateral_trade_open(self, iso2_a: str, iso2_b: str) -> bool:
        """Return True if trade between two countries is open."""
        for regime in self.sanctions_regimes:
            if not regime.active:
                continue
            if iso2_a in regime.target_countries and iso2_b in regime.sender_countries:
                return False
            if iso2_b in regime.target_countries and iso2_a in regime.sender_countries:
                return False
        return True

    @property
    def total_agents(self) -> int:
        return len(self.households)

    @property
    def num_countries(self) -> int:
        return len(self.countries)

    def summary(self) -> dict:
        return {
            "name":            self.name,
            "tick":            self.tick,
            "date":            str(self.simulation_date),
            "countries":       self.num_countries,
            "institutions":    len(self.institutions),
            "political_actors":len(self.political_actors),
            "central_banks":   len(self.central_banks),
            "commercial_banks":len(self.commercial_banks),
            "nonstate_actors": len(self.nonstate_actors),
            "corporations":    len(self.corporations),
            "households":      self.total_agents,
            "sanctions_active":sum(1 for s in self.sanctions_regimes if s.active),
            "alliances":       len(self.alliances),
            "vix":             self.macro.vix,
            "geo_risk":        self.macro.geopolitical_risk_index,
        }

    def __repr__(self) -> str:
        return (
            f"World(tick={self.tick}, countries={self.num_countries}, "
            f"agents={self.total_agents}, sanctions={len(self.sanctions_regimes)})"
        )
