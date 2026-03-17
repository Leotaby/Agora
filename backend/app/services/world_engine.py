"""
services/world_engine.py - Living world tick engine.

The WorldEngine drives NEXUS as an autonomous living world.
Each tick advances the simulation date, evaluates threshold rules,
processes agent decisions by tier frequency, applies state mutations,
and broadcasts events to all SSE subscribers.

Module-level singleton via get_engine().
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta
from typing import Optional

from app.models.agent import AgentTier, HumanTwin
from app.models.country import CurrencyRegime, GeopoliticalBloc
from app.models.shock import (
    MacroShock, ShockType, ShockSource,
    shock_nk_cyber_attack,
)
from app.models.world import World
from app.models.world_event import (
    WorldEvent, EventType, EventSeverity, HumanIntervention,
)
from app.services.world_factory import WorldFactory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier evaluation frequency (ticks between evaluations)
# ---------------------------------------------------------------------------

TIER_EVAL_FREQUENCY: dict[AgentTier, int] = {
    AgentTier.CENTRAL_BANK:        30,   # monthly policy meetings
    AgentTier.MACRO_HEDGE_FUND:    1,    # daily monitoring
    AgentTier.COMMERCIAL_BANK:     1,    # daily market-making
    AgentTier.INSTITUTIONAL_AM:    5,    # weekly rebalancing
    AgentTier.PROFESSIONAL_RETAIL: 2,    # every 2 days
    AgentTier.ORDINARY_RETAIL:     5,    # weekly app checks
    AgentTier.HOUSEHOLD:           14,   # biweekly price awareness
}


class WorldEngine:
    """
    Autonomous living world tick engine.

    Manages the world state, runs threshold rules, evaluates agents,
    applies state mutations, and broadcasts events via asyncio.Queue
    subscriptions (push-based SSE).
    """

    def __init__(self):
        self.world: Optional[World] = None
        self._running: bool = False
        self._tick_task: Optional[asyncio.Task] = None
        self._tick_interval_seconds: float = 1.0
        self._days_per_tick: int = 1

        # Event system
        self._event_log: list[WorldEvent] = []
        self._max_event_log: int = 10_000
        self._event_subscribers: list[asyncio.Queue] = []

        # Human intervention queue
        self._intervention_queue: asyncio.Queue = asyncio.Queue()

        # GDP history for consecutive-decline detection
        self._gdp_history: dict[str, list[float]] = {}

        # LLM engine (lazy init)
        self._use_llm: bool = False
        self._llm_engine = None

        # Threshold rule cooldowns: rule_key -> last triggered tick
        self._rule_cooldowns: dict[str, int] = {}

        # Tick lock
        self._tick_lock: asyncio.Lock = asyncio.Lock()

        # Track critical events this tick (for override eval frequency)
        self._critical_this_tick: bool = False

        # RNG
        self._rng: random.Random = random.Random(42)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize(
        self,
        seed: int = 42,
        n_households_per_country: int = 50,
        use_llm: bool = False,
    ) -> World:
        """Initialize or reset the world. Stops ticking if running."""
        if self._running and self._tick_task:
            self._running = False

        self._rng = random.Random(seed)
        self._use_llm = use_llm
        self._event_log.clear()
        self._rule_cooldowns.clear()
        self._gdp_history.clear()
        self._intervention_queue = asyncio.Queue()
        self._critical_this_tick = False

        if use_llm:
            from app.services.llm_engine import LLMEngine
            self._llm_engine = LLMEngine()

        factory = WorldFactory(seed=seed)
        self.world = factory.build(
            n_households_per_major_country=n_households_per_country,
            verbose=False,
        )

        # Initialize GDP history
        for iso2, country in self.world.countries.items():
            self._gdp_history[iso2] = [country.economy.gdp_usd_bn]

        return self.world

    async def start(
        self,
        tick_interval: float = 1.0,
        days_per_tick: int = 1,
    ) -> None:
        """Start autonomous ticking."""
        if self.world is None:
            raise RuntimeError("World not initialized. Call initialize() first.")
        if self._running:
            return

        self._tick_interval_seconds = tick_interval
        self._days_per_tick = days_per_tick
        self._running = True
        self._tick_task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        """Stop autonomous ticking."""
        self._running = False
        if self._tick_task:
            try:
                await asyncio.wait_for(self._tick_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            self._tick_task = None

    async def manual_tick(self) -> list[WorldEvent]:
        """Advance one tick manually. Fails if auto-running."""
        if self._running:
            raise RuntimeError("Cannot manual tick while auto-running. Stop first.")
        if self.world is None:
            raise RuntimeError("World not initialized.")
        return await self._execute_tick()

    def get_state(self) -> dict:
        """Full world snapshot + engine metadata."""
        if self.world is None:
            return {"initialized": False}

        return {
            "initialized": True,
            "running": self._running,
            "tick": self.world.tick,
            "simulation_date": str(self.world.simulation_date),
            "tick_interval_seconds": self._tick_interval_seconds,
            "days_per_tick": self._days_per_tick,
            "total_events": len(self._event_log),
            "subscribers": len(self._event_subscribers),
            "world_summary": self.world.summary(),
            "macro": {
                "world_gdp_usd_trn": round(self.world.macro.world_gdp_usd_trn, 2),
                "global_inflation_pct": round(self.world.macro.global_inflation_pct, 2),
                "vix": round(self.world.macro.vix, 2),
                "oil_price_brent": round(self.world.macro.oil_price_brent, 2),
                "gold_price_usd": round(self.world.macro.gold_price_usd, 2),
                "bitcoin_price_usd": round(self.world.macro.bitcoin_price_usd, 2),
                "geopolitical_risk_index": round(self.world.macro.geopolitical_risk_index, 2),
                "usd_reserve_share": round(self.world.macro.usd_reserve_share, 4),
            },
            "countries": {
                iso2: {
                    "name": c.name,
                    "gdp_usd_bn": round(c.economy.gdp_usd_bn, 2),
                    "inflation_pct": round(c.economy.inflation_pct, 2),
                    "unemployment_pct": round(c.economy.unemployment_pct, 2),
                    "fx_reserves_usd_bn": round(c.economy.fx_reserves_usd_bn, 2),
                    "debt_to_gdp": round(c.economy.debt_to_gdp, 2),
                    "dollarization_pct": round(c.economy.dollarization_pct, 4),
                    "currency_regime": c.economy.currency_regime.value,
                    "sanctioned": c.politics.sanctions_target,
                }
                for iso2, c in self.world.countries.items()
            },
        }

    async def inject_intervention(
        self, agent_id: str, intervention: HumanIntervention,
    ) -> WorldEvent:
        """Queue a human intervention for the next tick."""
        intervention.agent_id = agent_id
        await self._intervention_queue.put(intervention)

        event = WorldEvent(
            event_type=EventType.HUMAN_INTERVENTION,
            severity=EventSeverity.INFO,
            tick=self.world.tick if self.world else 0,
            simulation_date=str(self.world.simulation_date) if self.world else "",
            headline=f"Human intervention queued for agent {agent_id[:8]}",
            description=f"Action: {intervention.action}, USD delta: {intervention.usd_delta:+.3f}",
            actor_type="human",
            actor_id=agent_id,
            mutations={"action": intervention.action, "usd_delta": intervention.usd_delta},
        )
        self._record_event(event)
        return event

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to live events. Returns a queue for SSE streaming."""
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._event_subscribers.append(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from live events."""
        if queue in self._event_subscribers:
            self._event_subscribers.remove(queue)

    def get_event_log(
        self, since_tick: int = 0, limit: int = 100,
    ) -> list[WorldEvent]:
        """Return historical events."""
        filtered = [e for e in self._event_log if e.tick >= since_tick]
        return filtered[-limit:]

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------

    async def _tick_loop(self) -> None:
        """Main autonomous tick loop."""
        while self._running:
            try:
                await self._execute_tick()
            except Exception as e:
                logger.error(f"Tick error: {e}", exc_info=True)
            await asyncio.sleep(self._tick_interval_seconds)

    async def _execute_tick(self) -> list[WorldEvent]:
        """Execute a single world tick."""
        async with self._tick_lock:
            tick_events: list[WorldEvent] = []
            self._critical_this_tick = False

            # 1. Advance clock
            self.world.tick += 1
            self.world.simulation_date += timedelta(days=self._days_per_tick)
            self.world.macro.date = self.world.simulation_date

            # 2. TICK_START
            start_event = WorldEvent(
                event_type=EventType.TICK_START,
                severity=EventSeverity.INFO,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"Tick {self.world.tick} — {self.world.simulation_date}",
            )
            tick_events.append(start_event)
            self._broadcast(start_event)

            # 3. Process pending interventions
            intervention_events = await self._process_interventions()
            tick_events.extend(intervention_events)

            # 4. Process pending shocks
            shock_events = self._process_pending_shocks()
            tick_events.extend(shock_events)

            # 5. Evaluate threshold rules -> generate events and shocks
            rule_events = self._evaluate_threshold_rules()
            tick_events.extend(rule_events)

            # 6. Evaluate agents (by tier frequency)
            agent_events = await self._evaluate_agents()
            tick_events.extend(agent_events)

            # 7. Apply state mutations
            mutation_events = self._apply_state_mutations()
            tick_events.extend(mutation_events)

            # 8. TICK_END
            end_event = WorldEvent(
                event_type=EventType.TICK_END,
                severity=EventSeverity.INFO,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"Tick {self.world.tick} complete — {len(tick_events)} events",
                mutations={
                    "vix": round(self.world.macro.vix, 2),
                    "geo_risk": round(self.world.macro.geopolitical_risk_index, 2),
                    "world_gdp_trn": round(self.world.macro.world_gdp_usd_trn, 2),
                },
            )
            tick_events.append(end_event)
            self._broadcast(end_event)

            # Record all events
            for ev in tick_events:
                self._record_event(ev)

            return tick_events

    # ------------------------------------------------------------------
    # Intervention processing
    # ------------------------------------------------------------------

    async def _process_interventions(self) -> list[WorldEvent]:
        """Drain intervention queue and apply human overrides."""
        events: list[WorldEvent] = []
        while not self._intervention_queue.empty():
            try:
                intervention: HumanIntervention = self._intervention_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            # Find agent
            agent = self._find_agent(intervention.agent_id)
            if not agent:
                continue

            # Apply portfolio deltas
            agent.usd_exposure = max(0, min(1, agent.usd_exposure + intervention.usd_delta))
            agent.eur_exposure = max(0, min(1, agent.eur_exposure + intervention.eur_delta))
            agent.equity_exposure = max(0, min(1, agent.equity_exposure + intervention.equity_delta))
            agent.crypto_exposure = max(0, min(1, agent.crypto_exposure + intervention.crypto_delta))

            event = WorldEvent(
                event_type=EventType.HUMAN_INTERVENTION,
                severity=EventSeverity.WARNING,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"Human override: {agent.name} ({agent.tier.value})",
                description=f"{intervention.action} — {intervention.reasoning}",
                actor_type="human",
                actor_id=agent.agent_id,
                mutations={
                    "usd_delta": intervention.usd_delta,
                    "eur_delta": intervention.eur_delta,
                    "equity_delta": intervention.equity_delta,
                    "crypto_delta": intervention.crypto_delta,
                },
            )
            events.append(event)
            self._broadcast(event)

        return events

    # ------------------------------------------------------------------
    # Shock processing
    # ------------------------------------------------------------------

    def _process_pending_shocks(self) -> list[WorldEvent]:
        """Process any manually injected shocks from world.pending_shocks."""
        events: list[WorldEvent] = []
        while self.world.pending_shocks:
            shock = self.world.pending_shocks.pop(0)
            self.world.processed_shocks.append(shock)

            event = WorldEvent(
                event_type=EventType.SHOCK_INJECTED,
                severity=EventSeverity.CRITICAL,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=shock.headline,
                description=shock.description,
                actor_type="system",
                actor_id=shock.source.value,
                generated_shock_id=shock.shock_id,
            )
            events.append(event)
            self._broadcast(event)
            self._critical_this_tick = True

        return events

    # ------------------------------------------------------------------
    # Threshold rules
    # ------------------------------------------------------------------

    def _check_cooldown(self, rule_key: str, cooldown_ticks: int) -> bool:
        """Return True if rule can fire (cooldown expired)."""
        last = self._rule_cooldowns.get(rule_key, -999999)
        return (self.world.tick - last) >= cooldown_ticks

    def _set_cooldown(self, rule_key: str) -> None:
        self._rule_cooldowns[rule_key] = self.world.tick

    def _evaluate_threshold_rules(self) -> list[WorldEvent]:
        """Evaluate all 10 threshold rules against current world state."""
        events: list[WorldEvent] = []

        events.extend(self._rule_iran_hyperinflation())
        events.extend(self._rule_nk_crypto_depleted())
        events.extend(self._rule_gdp_decline())
        events.extend(self._rule_unemployment_crisis())
        events.extend(self._rule_debt_crisis())
        events.extend(self._rule_vix_panic())
        events.extend(self._rule_oil_spike())
        events.extend(self._rule_sanctions_inflation_spiral())
        events.extend(self._rule_election_triggered())
        events.extend(self._rule_fx_reserves_crisis())

        return events

    # --- Rule 1: Iran hyperinflation ---
    def _rule_iran_hyperinflation(self) -> list[WorldEvent]:
        ir = self.world.countries.get("IR")
        if not ir:
            return []
        key = "iran_hyperinflation"
        if not self._check_cooldown(key, 90):
            return []
        if ir.economy.inflation_pct <= 50:
            return []

        self._set_cooldown(key)
        ir.economy.currency_regime = CurrencyRegime.HYPERINFLATION
        ir.economy.dollarization_pct = min(1.0, ir.economy.dollarization_pct + 0.05)

        shock = MacroShock(
            shock_type=ShockType.CURRENCY_CRISIS,
            source=ShockSource.MARKET,
            magnitude_pct=-20.0, direction=-1,
            headline=f"Iran hyperinflation: {ir.economy.inflation_pct:.0f}% — rial collapses",
            description="Iranian rial enters hyperinflation. Dollarization accelerates. Capital controls tightened.",
            primary_currency="IRR", secondary_currency="USD",
        )
        self.world.inject_shock(shock)

        event = WorldEvent(
            event_type=EventType.CURRENCY_DEVALUATION,
            severity=EventSeverity.CRITICAL,
            tick=self.world.tick,
            simulation_date=str(self.world.simulation_date),
            headline=shock.headline,
            description=shock.description,
            actor_type="country", actor_id="IR",
            mutations={"currency_regime": "hyperinflation", "dollarization_pct": ir.economy.dollarization_pct},
            generated_shock_id=shock.shock_id,
        )
        self._broadcast(event)
        self._critical_this_tick = True
        return [event]

    # --- Rule 2: NK crypto depleted -> Lazarus cyber attack ---
    def _rule_nk_crypto_depleted(self) -> list[WorldEvent]:
        lazarus = next((a for a in self.world.nonstate_actors if a.actor_id == "LAZARUS"), None)
        if not lazarus:
            return []
        key = "nk_crypto_depleted"
        if not self._check_cooldown(key, 60):
            return []
        if lazarus.crypto_holdings_usd_mn >= 500:
            return []

        self._set_cooldown(key)
        stolen = self._rng.randint(200, 800)
        lazarus.crypto_holdings_usd_mn += stolen

        shock = shock_nk_cyber_attack()
        self.world.inject_shock(shock)

        event = WorldEvent(
            event_type=EventType.CYBER_ATTACK,
            severity=EventSeverity.CRITICAL,
            tick=self.world.tick,
            simulation_date=str(self.world.simulation_date),
            headline=f"Lazarus Group steals ${stolen}mn in crypto — banks targeted",
            description=shock.description,
            actor_type="nonstate_actor", actor_id="LAZARUS",
            mutations={"crypto_stolen_usd_mn": stolen, "crypto_holdings": lazarus.crypto_holdings_usd_mn},
            generated_shock_id=shock.shock_id,
        )
        self._broadcast(event)
        self._critical_this_tick = True
        return [event]

    # --- Rule 3: GDP 3-tick consecutive decline ---
    def _rule_gdp_decline(self) -> list[WorldEvent]:
        events: list[WorldEvent] = []
        for iso2, country in self.world.countries.items():
            key = f"gdp_decline_{iso2}"
            if not self._check_cooldown(key, 30):
                continue

            history = self._gdp_history.get(iso2, [])
            if len(history) < 3:
                continue

            last3 = history[-3:]
            if last3[0] > last3[1] > last3[2]:
                self._set_cooldown(key)

                # Find governing party and reduce approval
                for actor in self.world.political_actors.values():
                    if hasattr(actor, "country_iso2") and actor.country_iso2 == iso2:
                        if hasattr(actor, "is_governing") and actor.is_governing:
                            actor.approval_rating = max(0, actor.approval_rating - 8)
                    if hasattr(actor, "country_iso2") and actor.country_iso2 == iso2:
                        if hasattr(actor, "opposition_strength"):
                            pass  # opposition_strength is on PoliticalProfile

                country.politics.opposition_strength = min(1.0, country.politics.opposition_strength + 0.05)

                event = WorldEvent(
                    event_type=EventType.APPROVAL_DROP,
                    severity=EventSeverity.WARNING,
                    tick=self.world.tick,
                    simulation_date=str(self.world.simulation_date),
                    headline=f"{country.name}: 3-period GDP decline — government approval falling",
                    description=f"GDP declined from {last3[0]:.1f}bn to {last3[2]:.1f}bn. Opposition strengthens.",
                    actor_type="country", actor_id=iso2,
                    mutations={"opposition_strength": country.politics.opposition_strength},
                )
                events.append(event)
                self._broadcast(event)

        return events

    # --- Rule 4: Unemployment crisis ---
    def _rule_unemployment_crisis(self) -> list[WorldEvent]:
        events: list[WorldEvent] = []
        for iso2, country in self.world.countries.items():
            key = f"unemployment_{iso2}"
            if not self._check_cooldown(key, 60):
                continue
            if country.economy.unemployment_pct <= 15:
                continue

            self._set_cooldown(key)

            if country.politics.democracy_score < 6.0:
                country.politics.democracy_score = max(0, country.politics.democracy_score - 0.3)
            country.politics.opposition_strength = min(1.0, country.politics.opposition_strength + 0.08)
            self.world.macro.geopolitical_risk_index = min(100, self.world.macro.geopolitical_risk_index + 2)

            event = WorldEvent(
                event_type=EventType.SOCIAL_UNREST,
                severity=EventSeverity.WARNING,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"{country.name}: unemployment at {country.economy.unemployment_pct:.1f}% — social unrest",
                description="High unemployment drives political instability and social tension.",
                actor_type="country", actor_id=iso2,
                mutations={
                    "unemployment_pct": country.economy.unemployment_pct,
                    "democracy_score": country.politics.democracy_score,
                    "opposition_strength": country.politics.opposition_strength,
                },
            )
            events.append(event)
            self._broadcast(event)

        return events

    # --- Rule 5: Debt crisis ---
    def _rule_debt_crisis(self) -> list[WorldEvent]:
        events: list[WorldEvent] = []
        # Exclude US and JP (reserve currency / unique cases)
        excluded = {"US", "JP"}
        for iso2, country in self.world.countries.items():
            if iso2 in excluded:
                continue
            key = f"debt_crisis_{iso2}"
            if not self._check_cooldown(key, 180):
                continue
            if country.economy.debt_to_gdp <= 120:
                continue

            self._set_cooldown(key)
            country.economy.inflation_pct += 2
            country.economy.fx_reserves_usd_bn *= 0.95

            event = WorldEvent(
                event_type=EventType.SOVEREIGN_DOWNGRADE,
                severity=EventSeverity.CRITICAL,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"{country.name}: debt/GDP at {country.economy.debt_to_gdp:.0f}% — sovereign downgrade risk",
                description="Debt sustainability concerns trigger rating agency review. Inflation rises, reserves drain.",
                actor_type="country", actor_id=iso2,
                mutations={
                    "debt_to_gdp": country.economy.debt_to_gdp,
                    "inflation_pct": country.economy.inflation_pct,
                    "fx_reserves_usd_bn": country.economy.fx_reserves_usd_bn,
                },
            )
            events.append(event)
            self._broadcast(event)
            self._critical_this_tick = True

        return events

    # --- Rule 6: VIX panic ---
    def _rule_vix_panic(self) -> list[WorldEvent]:
        if not self._check_cooldown("vix_panic", 14):
            return []
        if self.world.macro.vix <= 40:
            return []

        self._set_cooldown("vix_panic")

        # All countries lose FX reserves, gold up, bitcoin down
        for country in self.world.countries.values():
            country.economy.fx_reserves_usd_bn *= 0.98
        self.world.macro.gold_price_usd *= 1.05
        self.world.macro.bitcoin_price_usd *= 0.90

        # HF agents reduce equity exposure
        for agent in self.world.households:
            if agent.tier == AgentTier.MACRO_HEDGE_FUND:
                agent.equity_exposure = max(0, agent.equity_exposure - 0.1)

        event = WorldEvent(
            event_type=EventType.RISK_OFF_CASCADE,
            severity=EventSeverity.CRITICAL,
            tick=self.world.tick,
            simulation_date=str(self.world.simulation_date),
            headline=f"VIX at {self.world.macro.vix:.1f} — global risk-off cascade",
            description="Extreme fear grips markets. Flight to gold, crypto sell-off, FX reserves declining.",
            actor_type="system", actor_id="global",
            mutations={
                "vix": self.world.macro.vix,
                "gold_price_usd": self.world.macro.gold_price_usd,
                "bitcoin_price_usd": self.world.macro.bitcoin_price_usd,
            },
        )
        self._broadcast(event)
        self._critical_this_tick = True
        return [event]

    # --- Rule 7: Oil price spike ---
    def _rule_oil_spike(self) -> list[WorldEvent]:
        if not self._check_cooldown("oil_spike", 30):
            return []
        if self.world.macro.oil_price_brent <= 120:
            return []

        self._set_cooldown("oil_spike")

        # Oil importers get inflation, OPEC members get reserves
        opec_countries = {iso2 for iso2, c in self.world.countries.items()
                         if GeopoliticalBloc.OPEC in c.blocs}

        for iso2, country in self.world.countries.items():
            if iso2 in opec_countries:
                country.economy.fx_reserves_usd_bn *= 1.03
            else:
                country.economy.inflation_pct += 1.0

        event = WorldEvent(
            event_type=EventType.OIL_PRICE_SHOCK,
            severity=EventSeverity.WARNING,
            tick=self.world.tick,
            simulation_date=str(self.world.simulation_date),
            headline=f"Oil at ${self.world.macro.oil_price_brent:.0f}/bbl — energy inflation spike",
            description="High oil prices drive inflation in importing nations. OPEC reserves grow.",
            actor_type="system", actor_id="global",
            mutations={"oil_price_brent": self.world.macro.oil_price_brent},
        )
        self._broadcast(event)
        return [event]

    # --- Rule 8: Sanctions + inflation spiral ---
    def _rule_sanctions_inflation_spiral(self) -> list[WorldEvent]:
        events: list[WorldEvent] = []
        for iso2, country in self.world.countries.items():
            key = f"sanctions_spiral_{iso2}"
            if not self._check_cooldown(key, 90):
                continue
            if not country.politics.sanctions_target:
                continue
            if country.economy.inflation_pct <= 30:
                continue

            self._set_cooldown(key)

            # Push toward capital controls
            if country.economy.currency_regime not in (
                CurrencyRegime.CAPITAL_CONTROLS, CurrencyRegime.HYPERINFLATION
            ):
                country.economy.currency_regime = CurrencyRegime.CAPITAL_CONTROLS
            country.economy.dollarization_pct = min(1.0, country.economy.dollarization_pct + 0.03)

            event = WorldEvent(
                event_type=EventType.SANCTIONS_ESCALATION,
                severity=EventSeverity.WARNING,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"{country.name}: sanctions + {country.economy.inflation_pct:.0f}% inflation — capital controls tighten",
                description="Sanctioned country with high inflation moves to capital controls. Dollarization rises.",
                actor_type="country", actor_id=iso2,
                mutations={
                    "currency_regime": country.economy.currency_regime.value,
                    "dollarization_pct": country.economy.dollarization_pct,
                },
            )
            events.append(event)
            self._broadcast(event)

        return events

    # --- Rule 9: Election triggered ---
    def _rule_election_triggered(self) -> list[WorldEvent]:
        events: list[WorldEvent] = []
        for iso2, country in self.world.countries.items():
            key = f"election_{iso2}"
            if not self._check_cooldown(key, 365):
                continue
            if country.politics.election_due_year is None:
                continue
            if self.world.simulation_date.year < country.politics.election_due_year:
                continue

            # Find governing party approval
            governing_parties = [
                p for p in self.world.political_actors.values()
                if hasattr(p, "country_iso2") and p.country_iso2 == iso2
                and hasattr(p, "is_governing") and p.is_governing
            ]

            if not governing_parties:
                continue

            gov_party = governing_parties[0]
            if gov_party.approval_rating >= 35:
                continue

            self._set_cooldown(key)

            # Check if opposition can win
            opposition_wins = country.politics.opposition_strength > 0.45
            if opposition_wins:
                # Swap governing party
                opposition_parties = [
                    p for p in self.world.political_actors.values()
                    if hasattr(p, "country_iso2") and p.country_iso2 == iso2
                    and hasattr(p, "is_governing") and not p.is_governing
                ]
                if opposition_parties:
                    # Find strongest opposition
                    strongest = max(opposition_parties, key=lambda p: getattr(p, "vote_share_pct", 0))
                    gov_party.is_governing = False
                    strongest.is_governing = True
                    country.politics.ruling_party = strongest.name

            country.politics.election_due_year += 4

            event = WorldEvent(
                event_type=EventType.ELECTION_TRIGGERED,
                severity=EventSeverity.WARNING,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"{country.name}: election — {'opposition wins' if opposition_wins else 'government survives'}",
                description=f"Approval at {gov_party.approval_rating:.0f}%, opposition strength {country.politics.opposition_strength:.2f}.",
                actor_type="country", actor_id=iso2,
                mutations={
                    "ruling_party": country.politics.ruling_party,
                    "election_due_year": country.politics.election_due_year,
                    "opposition_wins": opposition_wins,
                },
            )
            events.append(event)
            self._broadcast(event)

        return events

    # --- Rule 10: FX reserves crisis ---
    def _rule_fx_reserves_crisis(self) -> list[WorldEvent]:
        events: list[WorldEvent] = []
        # Exclude reserve currency issuers
        excluded = {"US", "JP"}
        for iso2, country in self.world.countries.items():
            if iso2 in excluded:
                continue
            key = f"fx_reserves_{iso2}"
            if not self._check_cooldown(key, 180):
                continue

            threshold = country.economy.gdp_usd_bn * 0.02
            if country.economy.fx_reserves_usd_bn >= threshold:
                continue

            self._set_cooldown(key)

            # Economic damage
            country.economy.gdp_usd_bn *= 0.98
            country.economy.inflation_pct += 5

            shock = MacroShock(
                shock_type=ShockType.CURRENCY_CRISIS,
                source=ShockSource.MARKET,
                magnitude_pct=-15.0, direction=-1,
                headline=f"{country.name}: FX reserves critically low — currency crisis",
                description=f"FX reserves at ${country.economy.fx_reserves_usd_bn:.1f}bn vs GDP ${country.economy.gdp_usd_bn:.0f}bn. Currency collapses.",
                primary_currency=country.economy.currency_code,
                secondary_currency="USD",
            )
            self.world.inject_shock(shock)

            event = WorldEvent(
                event_type=EventType.CAPITAL_FLIGHT,
                severity=EventSeverity.CRITICAL,
                tick=self.world.tick,
                simulation_date=str(self.world.simulation_date),
                headline=shock.headline,
                description=shock.description,
                actor_type="country", actor_id=iso2,
                mutations={
                    "fx_reserves_usd_bn": country.economy.fx_reserves_usd_bn,
                    "gdp_usd_bn": country.economy.gdp_usd_bn,
                    "inflation_pct": country.economy.inflation_pct,
                },
                generated_shock_id=shock.shock_id,
            )
            events.append(event)
            self._broadcast(event)
            self._critical_this_tick = True

        return events

    # ------------------------------------------------------------------
    # Agent evaluation
    # ------------------------------------------------------------------

    async def _evaluate_agents(self) -> list[WorldEvent]:
        """Evaluate agents based on tier frequency. Stub decisions for no-LLM mode."""
        events: list[WorldEvent] = []
        tick = self.world.tick

        for agent in self.world.households:
            freq = TIER_EVAL_FREQUENCY.get(agent.tier, 14)

            # Override: critical event + fast information -> evaluate anyway
            should_eval = (tick % freq == 0)
            if self._critical_this_tick and agent.information_speed > 0.5:
                should_eval = True

            if not should_eval:
                continue

            # Generate stub decision (no-LLM mode)
            decision = self._stub_agent_decision(agent)
            if decision is None:
                continue

            # Apply decision
            usd_delta = decision["usd_delta"]
            agent.usd_exposure = max(0, min(1, agent.usd_exposure + usd_delta))
            # Balance EUR exposure
            agent.eur_exposure = max(0, min(1, 1.0 - agent.usd_exposure - agent.equity_exposure - agent.crypto_exposure))

            event = WorldEvent(
                event_type=EventType.AGENT_DECISION,
                severity=EventSeverity.INFO,
                tick=tick,
                simulation_date=str(self.world.simulation_date),
                headline=f"{agent.name} ({agent.tier.value}): {decision['action']}",
                description=decision.get("reasoning", ""),
                actor_type="agent",
                actor_id=agent.agent_id,
                mutations={
                    "usd_delta": usd_delta,
                    "usd_exposure": agent.usd_exposure,
                    "country": agent.country,
                },
            )
            events.append(event)
            # Only broadcast non-household decisions to avoid spam
            if agent.tier != AgentTier.HOUSEHOLD:
                self._broadcast(event)

        return events

    def _stub_agent_decision(self, agent: HumanTwin) -> Optional[dict]:
        """Generate a stub decision based on world state (no-LLM mode)."""
        country = self.world.countries.get(agent.country)
        if not country:
            return None

        action = "hold"
        usd_delta = 0.0
        reasoning = ""

        # Rule: Home country inflation > 20% -> dollarize
        if country.economy.inflation_pct > 20:
            usd_delta = 0.02 * agent.financial_literacy
            action = "increase USD (dollarization)"
            reasoning = f"Home inflation at {country.economy.inflation_pct:.0f}%, shifting to USD"

        # Rule: VIX > 30 and risk-averse -> reduce equity/crypto
        elif self.world.macro.vix > 30 and agent.risk_tolerance.value in ("very_low", "low"):
            usd_delta = 0.01
            agent.equity_exposure = max(0, agent.equity_exposure - 0.02)
            agent.crypto_exposure = max(0, agent.crypto_exposure - 0.01)
            action = "risk-off: reduce equity/crypto"
            reasoning = f"VIX at {self.world.macro.vix:.0f}, risk-averse agent de-risking"

        # Rule: Home country sanctioned -> increase crypto (evasion)
        elif country.politics.sanctions_target:
            agent.crypto_exposure = min(1.0, agent.crypto_exposure + 0.01)
            action = "increase crypto (sanctions evasion)"
            reasoning = f"Home country {country.name} sanctioned, diversifying to crypto"

        # Otherwise: small random drift
        else:
            drift = self._rng.gauss(0, 0.005) * agent.financial_literacy
            if abs(drift) < 0.001:
                return None  # No meaningful action
            usd_delta = drift
            action = f"drift {'buy' if drift > 0 else 'sell'} USD"
            reasoning = "Normal portfolio micro-adjustment"

        return {"action": action, "usd_delta": usd_delta, "reasoning": reasoning}

    # ------------------------------------------------------------------
    # State mutations (end of tick)
    # ------------------------------------------------------------------

    def _apply_state_mutations(self) -> list[WorldEvent]:
        """
        End-of-tick state mutations:
        - Agent USD deltas aggregate by country -> net FX flow
        - FX flow adjusts country fx_reserves
        - Country GDP micro-drift
        - Global aggregates recomputed
        """
        events: list[WorldEvent] = []

        # 1. Aggregate agent USD flows by country
        country_usd_flow: dict[str, float] = {}
        for agent in self.world.households:
            iso2 = agent.country
            country_usd_flow[iso2] = country_usd_flow.get(iso2, 0) + agent.usd_exposure

        # 2. Apply FX flow effects to countries
        for iso2, country in self.world.countries.items():
            flow = country_usd_flow.get(iso2, 0)
            agents_in_country = sum(1 for a in self.world.households if a.country == iso2)
            if agents_in_country == 0:
                agents_in_country = 1

            avg_usd = flow / agents_in_country
            # High aggregate USD buying -> dollarization drifts up
            if avg_usd > 0.3:
                country.economy.dollarization_pct = min(
                    1.0, country.economy.dollarization_pct + 0.001
                )

            # FX reserves micro-adjustment (scaled by agent population)
            reserves_delta = (avg_usd - 0.15) * 0.01 * country.economy.fx_reserves_usd_bn
            country.economy.fx_reserves_usd_bn += reserves_delta

        # 3. Country GDP daily micro-drift
        total_gdp = 0.0
        weighted_inflation = 0.0
        for iso2, country in self.world.countries.items():
            # Annual growth rate -> daily
            annual_rate = 0.02  # base 2% growth assumption
            if country.economy.inflation_pct > 10:
                annual_rate -= 0.01  # high inflation drags growth
            if country.politics.sanctions_target:
                annual_rate -= 0.005

            daily_factor = 1 + (annual_rate / 365 * self._days_per_tick)
            country.economy.gdp_usd_bn *= daily_factor

            # Track GDP history
            if iso2 not in self._gdp_history:
                self._gdp_history[iso2] = []
            self._gdp_history[iso2].append(country.economy.gdp_usd_bn)
            if len(self._gdp_history[iso2]) > 10:
                self._gdp_history[iso2] = self._gdp_history[iso2][-10:]

            total_gdp += country.economy.gdp_usd_bn
            weighted_inflation += country.economy.inflation_pct * country.economy.gdp_usd_bn

        # 4. Update global aggregates
        self.world.macro.world_gdp_usd_trn = total_gdp / 1000  # bn -> trn

        if total_gdp > 0:
            self.world.macro.global_inflation_pct = weighted_inflation / total_gdp

        # VIX mean-reverts toward 18, bumped by critical events
        vix_target = 18.0
        if self._critical_this_tick:
            self.world.macro.vix += self._rng.uniform(2, 8)
        else:
            self.world.macro.vix += (vix_target - self.world.macro.vix) * 0.05

        # Geopolitical risk decays toward 45
        geo_target = 45.0
        self.world.macro.geopolitical_risk_index += (geo_target - self.world.macro.geopolitical_risk_index) * 0.01

        return events

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_agent(self, agent_id: str) -> Optional[HumanTwin]:
        """Find an agent by ID."""
        for agent in self.world.households:
            if agent.agent_id == agent_id:
                return agent
        return None

    def _record_event(self, event: WorldEvent) -> None:
        """Record event to log, cap at max."""
        self._event_log.append(event)
        if len(self._event_log) > self._max_event_log:
            self._event_log = self._event_log[-self._max_event_log:]

    def _broadcast(self, event: WorldEvent) -> None:
        """Push event to all SSE subscribers."""
        dead: list[asyncio.Queue] = []
        for q in self._event_subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._event_subscribers.remove(q)

    def __repr__(self) -> str:
        if self.world:
            return f"WorldEngine(tick={self.world.tick}, running={self._running}, agents={self.world.total_agents})"
        return "WorldEngine(not initialized)"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_engine: Optional[WorldEngine] = None


def get_engine() -> WorldEngine:
    """Return the singleton WorldEngine instance."""
    global _engine
    if _engine is None:
        _engine = WorldEngine()
    return _engine
