"""
services/agent_society.py — Agent-to-agent communication and perspective engine.

Each tick, agents:
  1. Receive messages from their network
  2. Update beliefs based on messages filtered by literacy and trust
  3. Make one decision (buy/sell/save/consume/migrate/protest)
  4. Send messages about what they decided or observed
  5. Collective decisions update country-level macro variables

The society layer sits on top of the HumanTwin population and adds:
  - Rich role-typed characters (shop clerk, soldier, ECB president, etc.)
  - Social network and message propagation
  - Belief dynamics
  - A perspective API (see the world through one agent's eyes)
"""
from __future__ import annotations

import random
import logging
from datetime import datetime
from typing import Optional

from app.models.agent import HumanTwin, AgentTier, RiskTolerance
from app.models.agent_life import (
    AgentLife, AgentRole, Employment, HouseholdLife, ROLE_PROFILES,
)
from app.models.agent_message import (
    AgentMessage, MessageType, MESSAGE_INFLUENCE_WEIGHT,
)

logger = logging.getLogger(__name__)

# Maximum messages kept per agent
MAX_MESSAGE_HISTORY = 100
MAX_RECENT_DECISIONS = 20


class AgentSociety:
    """
    Manages the social layer: roles, connections, messages, beliefs.

    Lifetime: created once per WorldEngine.initialize() call.
    """

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

        # agent_id -> AgentLife
        self.lives: dict[str, AgentLife] = {}

        # Global message log (last N messages, for event feed)
        self.message_log: list[AgentMessage] = []
        self._max_log: int = 2000

        # agent_id -> list of received messages (full history, capped)
        self._mailboxes: dict[str, list[AgentMessage]] = {}

        # Role-typed agent roster (agent_id -> role)
        self.role_agents: dict[str, AgentRole] = {}

    # ------------------------------------------------------------------
    # Initialization: create role-typed agents and wire social networks
    # ------------------------------------------------------------------

    def populate(self, agents: list[HumanTwin], world) -> list[HumanTwin]:
        """
        Given the existing agent population and world state,
        create role-typed agents and attach AgentLife records to all agents.
        Returns the new role-typed agents to be added to world.households.
        """
        new_agents: list[HumanTwin] = []

        # 1. Create the named role-typed agents
        new_agents.extend(self._create_role_agents(world))

        # 2. Attach AgentLife to every existing agent
        all_agents = agents + new_agents
        for agent in all_agents:
            if agent.agent_id not in self.lives:
                life = self._create_life_for_agent(agent, all_agents)
                self.lives[agent.agent_id] = life
                self._mailboxes[agent.agent_id] = []

        # 3. Wire social connections based on proximity and role
        self._wire_social_network(all_agents)

        return new_agents

    def _create_role_agents(self, world) -> list[HumanTwin]:
        """Create the specific narrative-driven agents."""
        agents: list[HumanTwin] = []

        # --- Shop clerks (Italy, France, Germany) ---
        for country, name in [("IT", "Marco Bianchi"), ("FR", "Sophie Dupont"), ("DE", "Anna Müller")]:
            a = HumanTwin(
                name=name, tier=AgentTier.HOUSEHOLD, country=country,
                age=self._rng.randint(24, 45),
                income_annual_eur=self._rng.uniform(16_000, 28_000),
                net_wealth_eur=self._rng.uniform(5_000, 30_000),
                financial_literacy=self._rng.uniform(0.25, 0.45),
                risk_tolerance=RiskTolerance.LOW,
                information_speed=0.12,
                social_influence=self._rng.uniform(0.5, 0.7),
                media_exposure="tv_news",
            )
            agents.append(a)
            self.role_agents[a.agent_id] = AgentRole.SHOP_CLERK
            self.lives[a.agent_id] = AgentLife(
                agent_id=a.agent_id,
                role=AgentRole.SHOP_CLERK,
                employment=Employment(
                    employer_id=f"local_shop_{country}",
                    salary_monthly_eur=a.income_annual_eur / 12,
                    job_title="Shop Clerk",
                ),
                household=HouseholdLife(
                    family_size=self._rng.randint(1, 4),
                    monthly_expenses_eur=self._rng.uniform(1_200, 2_200),
                    savings_rate=self._rng.uniform(0.02, 0.12),
                ),
                beliefs={
                    "inflation_outlook": 0.3,
                    "currency_confidence": 0.6,
                    "market_fear": 0.2,
                    "government_trust": 0.4,
                    "local_price_pressure": 0.3,
                },
            )
            self._mailboxes[a.agent_id] = []

        # --- ECB President ---
        ecb = HumanTwin(
            name="Christine Lagarde", tier=AgentTier.CENTRAL_BANK, country="EU",
            age=68, income_annual_eur=0, net_wealth_eur=0,
            financial_literacy=1.0, risk_tolerance=RiskTolerance.VERY_LOW,
            loss_aversion=5.0, information_speed=1.0,
            social_influence=0.0, media_exposure="proprietary_data_terminal",
            usd_exposure=0.3, eur_exposure=0.6,
        )
        agents.append(ecb)
        self.role_agents[ecb.agent_id] = AgentRole.ECB_PRESIDENT
        self.lives[ecb.agent_id] = AgentLife(
            agent_id=ecb.agent_id,
            role=AgentRole.ECB_PRESIDENT,
            employment=Employment(employer_id="ECB", salary_monthly_eur=0, job_title="President"),
            beliefs={
                "inflation_outlook": 0.5,
                "currency_confidence": 0.8,
                "market_fear": 0.15,
                "employment_mandate": 0.6,
                "rate_bias": 0.0,  # negative = dovish, positive = hawkish
            },
        )
        self._mailboxes[ecb.agent_id] = []

        # --- Soldiers (Ukraine x2, Russia x2) ---
        for country, name, side in [
            ("UA", "Oleksiy Koval", "defender"),
            ("UA", "Daryna Shevchenko", "defender"),
            ("RU", "Dmitry Volkov", "conscript"),
            ("RU", "Sergei Petrov", "conscript"),
        ]:
            a = HumanTwin(
                name=name, tier=AgentTier.HOUSEHOLD, country=country,
                age=self._rng.randint(20, 35),
                income_annual_eur=self._rng.uniform(3_000, 12_000),
                net_wealth_eur=self._rng.uniform(500, 5_000),
                financial_literacy=self._rng.uniform(0.15, 0.35),
                risk_tolerance=RiskTolerance.HIGH,
                information_speed=0.08, social_influence=0.3,
                media_exposure="word_of_mouth",
            )
            agents.append(a)
            self.role_agents[a.agent_id] = AgentRole.SOLDIER
            self.lives[a.agent_id] = AgentLife(
                agent_id=a.agent_id,
                role=AgentRole.SOLDIER,
                employment=Employment(
                    employer_id=f"military_{country}",
                    salary_monthly_eur=a.income_annual_eur / 12,
                    job_title=f"Soldier ({side})",
                ),
                household=HouseholdLife(
                    family_size=self._rng.randint(1, 3),
                    monthly_expenses_eur=self._rng.uniform(300, 800),
                    savings_rate=0.0,
                ),
                beliefs={
                    "conflict_risk": 0.9,
                    "homeland_safety": 0.2 if country == "UA" else 0.5,
                    "government_trust": 0.7 if country == "UA" else 0.3,
                    "inflation_outlook": 0.5,
                    "currency_confidence": 0.3,
                },
            )
            self._mailboxes[a.agent_id] = []

        # --- NK State Workers ---
        for i in range(3):
            a = HumanTwin(
                name=f"Worker {i+1} (Pyongyang)",
                tier=AgentTier.HOUSEHOLD, country="KP",
                age=self._rng.randint(25, 50),
                income_annual_eur=self._rng.uniform(600, 1_200),
                net_wealth_eur=self._rng.uniform(50, 500),
                financial_literacy=self._rng.uniform(0.05, 0.15),
                risk_tolerance=RiskTolerance.VERY_LOW,
                information_speed=0.01, social_influence=0.1,
                media_exposure="state_media",
            )
            agents.append(a)
            self.role_agents[a.agent_id] = AgentRole.NK_STATE_WORKER
            self.lives[a.agent_id] = AgentLife(
                agent_id=a.agent_id,
                role=AgentRole.NK_STATE_WORKER,
                employment=Employment(
                    employer_id="state_enterprise_kp",
                    salary_monthly_eur=a.income_annual_eur / 12,
                    job_title="State Factory Worker",
                ),
                household=HouseholdLife(
                    family_size=self._rng.randint(2, 5),
                    monthly_expenses_eur=self._rng.uniform(30, 80),
                    savings_rate=0.0,
                ),
                beliefs={
                    "government_trust": 0.95,  # state propaganda
                    "inflation_outlook": 0.1,
                    "currency_confidence": 0.9,
                    "market_fear": 0.05,
                    "conflict_risk": 0.1,  # believe state is invincible
                },
            )
            self._mailboxes[a.agent_id] = []

        # --- Hedge Fund Traders ---
        for name, country in [
            ("Jake Morrison", "US"),
            ("Emily Chen", "US"),
            ("Rupert Hargreaves", "GB"),
        ]:
            a = HumanTwin(
                name=name, tier=AgentTier.MACRO_HEDGE_FUND, country=country,
                age=self._rng.randint(30, 50),
                income_annual_eur=self._rng.uniform(500_000, 5_000_000),
                net_wealth_eur=self._rng.uniform(2_000_000, 50_000_000),
                financial_literacy=self._rng.uniform(0.92, 0.99),
                risk_tolerance=RiskTolerance.HIGH,
                loss_aversion=self._rng.uniform(1.0, 1.5),
                information_speed=self._rng.uniform(0.90, 0.98),
                usd_exposure=self._rng.uniform(0.2, 0.5),
                eur_exposure=self._rng.uniform(0.1, 0.3),
                equity_exposure=self._rng.uniform(0.2, 0.4),
                social_influence=self._rng.uniform(0.15, 0.3),
                media_exposure="bloomberg_terminal",
            )
            agents.append(a)
            self.role_agents[a.agent_id] = AgentRole.HEDGE_FUND_TRADER
            self.lives[a.agent_id] = AgentLife(
                agent_id=a.agent_id,
                role=AgentRole.HEDGE_FUND_TRADER,
                employment=Employment(
                    employer_id=f"macro_fund_{country}",
                    salary_monthly_eur=a.income_annual_eur / 12,
                    job_title="Portfolio Manager",
                ),
                beliefs={
                    "inflation_outlook": 0.4,
                    "currency_confidence": 0.7,
                    "market_fear": 0.2,
                    "carry_signal": 0.0,
                    "momentum_signal": 0.0,
                    "risk_appetite": 0.6,
                },
            )
            self._mailboxes[a.agent_id] = []

        # --- Turkish Households ---
        for i in range(4):
            name = self._rng.choice([
                "Mehmet Yilmaz", "Ayse Demir", "Fatma Celik", "Ali Kaya",
                "Zeynep Arslan", "Mustafa Sahin",
            ])
            a = HumanTwin(
                name=f"{name}", tier=AgentTier.HOUSEHOLD, country="TR",
                age=self._rng.randint(28, 60),
                income_annual_eur=self._rng.uniform(6_000, 18_000),
                net_wealth_eur=self._rng.uniform(1_000, 15_000),
                financial_literacy=self._rng.uniform(0.30, 0.55),
                risk_tolerance=RiskTolerance.MEDIUM,
                information_speed=0.15,
                usd_exposure=self._rng.uniform(0.15, 0.45),  # already dollarizing
                eur_exposure=self._rng.uniform(0.1, 0.3),
                crypto_exposure=self._rng.uniform(0.0, 0.08),
                social_influence=self._rng.uniform(0.5, 0.8),
                media_exposure=self._rng.choice(["tv_news", "social_media", "word_of_mouth"]),
            )
            agents.append(a)
            self.role_agents[a.agent_id] = AgentRole.TURKISH_HOUSEHOLD
            self.lives[a.agent_id] = AgentLife(
                agent_id=a.agent_id,
                role=AgentRole.TURKISH_HOUSEHOLD,
                employment=Employment(
                    employer_id="various_tr",
                    salary_monthly_eur=a.income_annual_eur / 12,
                    job_title=self._rng.choice(["Shopkeeper", "Teacher", "Driver", "Tradesman"]),
                ),
                household=HouseholdLife(
                    family_size=self._rng.randint(2, 6),
                    monthly_expenses_eur=self._rng.uniform(400, 1_200),
                    savings_rate=self._rng.uniform(0.0, 0.08),
                    housing_type=self._rng.choice(["owning", "renting"]),
                ),
                beliefs={
                    "inflation_outlook": 0.85,   # very aware of inflation
                    "currency_confidence": 0.15,  # lira distrust
                    "market_fear": 0.6,
                    "government_trust": 0.2,
                    "dollarization_urge": 0.7,
                    "gold_preference": 0.5,
                },
            )
            self._mailboxes[a.agent_id] = []

        # --- Iranian Merchants ---
        for name in ["Hassan Mohammadi", "Reza Ahmadi", "Fatemeh Hosseini"]:
            a = HumanTwin(
                name=name, tier=AgentTier.HOUSEHOLD, country="IR",
                age=self._rng.randint(30, 55),
                income_annual_eur=self._rng.uniform(8_000, 30_000),
                net_wealth_eur=self._rng.uniform(5_000, 50_000),
                financial_literacy=self._rng.uniform(0.50, 0.72),
                risk_tolerance=RiskTolerance.HIGH,
                information_speed=0.20,
                usd_exposure=self._rng.uniform(0.10, 0.30),
                crypto_exposure=self._rng.uniform(0.05, 0.20),
                social_influence=self._rng.uniform(0.4, 0.6),
                media_exposure="word_of_mouth",
            )
            agents.append(a)
            self.role_agents[a.agent_id] = AgentRole.IRANIAN_MERCHANT
            self.lives[a.agent_id] = AgentLife(
                agent_id=a.agent_id,
                role=AgentRole.IRANIAN_MERCHANT,
                employment=Employment(
                    employer_id="bazaar_tehran",
                    salary_monthly_eur=a.income_annual_eur / 12,
                    job_title="Merchant",
                ),
                household=HouseholdLife(
                    family_size=self._rng.randint(3, 7),
                    monthly_expenses_eur=self._rng.uniform(500, 1_500),
                    savings_rate=self._rng.uniform(0.05, 0.15),
                ),
                beliefs={
                    "inflation_outlook": 0.75,
                    "currency_confidence": 0.1,
                    "sanctions_severity": 0.8,
                    "crypto_utility": 0.7,
                    "hawala_reliance": 0.6,
                    "government_trust": 0.15,
                    "market_fear": 0.5,
                },
            )
            self._mailboxes[a.agent_id] = []

        return agents

    def _create_life_for_agent(
        self, agent: HumanTwin, all_agents: list[HumanTwin],
    ) -> AgentLife:
        """Create a default AgentLife for an existing (non-role-typed) agent."""
        # Determine role from tier
        if agent.tier == AgentTier.CENTRAL_BANK:
            role = AgentRole.CENTRAL_BANKER
        elif agent.tier == AgentTier.MACRO_HEDGE_FUND:
            role = AgentRole.HEDGE_FUND_TRADER
        else:
            role = AgentRole.GENERIC

        return AgentLife(
            agent_id=agent.agent_id,
            role=role,
            employment=Employment(
                salary_monthly_eur=agent.income_annual_eur / 12,
                job_title=agent.tier.value.split("_", 1)[-1].replace("_", " ").title(),
            ),
            household=HouseholdLife(
                family_size=self._rng.randint(1, 4),
                monthly_expenses_eur=agent.income_annual_eur / 12 * 0.7,
                savings_rate=0.10,
            ),
            beliefs={
                "inflation_outlook": self._rng.uniform(0.2, 0.5),
                "currency_confidence": self._rng.uniform(0.4, 0.8),
                "market_fear": self._rng.uniform(0.1, 0.3),
                "government_trust": self._rng.uniform(0.3, 0.6),
            },
        )

    def _wire_social_network(self, agents: list[HumanTwin]) -> None:
        """
        Wire social connections:
        - Same-country agents are connected
        - Same-role agents are connected
        - ECB president connects to all EU agents as information source
        - NK workers only connect to each other
        """
        # Index agents by country and role
        by_country: dict[str, list[str]] = {}
        by_role: dict[AgentRole, list[str]] = {}

        for agent in agents:
            by_country.setdefault(agent.country, []).append(agent.agent_id)
            role = self.role_agents.get(agent.agent_id, AgentRole.GENERIC)
            by_role.setdefault(role, []).append(agent.agent_id)

        # Find ECB president for info source wiring
        ecb_ids = by_role.get(AgentRole.ECB_PRESIDENT, [])
        ecb_id = ecb_ids[0] if ecb_ids else None

        eu_countries = {"DE", "FR", "IT", "ES", "NL", "BE", "PT", "GR", "AT", "FI", "EU"}

        for agent in agents:
            life = self.lives.get(agent.agent_id)
            if not life:
                continue

            role = self.role_agents.get(agent.agent_id, AgentRole.GENERIC)

            # NK workers: only connect to other NK workers
            if role == AgentRole.NK_STATE_WORKER:
                nk_peers = [
                    aid for aid in by_role.get(AgentRole.NK_STATE_WORKER, [])
                    if aid != agent.agent_id
                ]
                life.social_connections = nk_peers
                life.information_sources = []  # only state propaganda
                continue

            # Social connections: sample from same country
            country_peers = [
                aid for aid in by_country.get(agent.country, [])
                if aid != agent.agent_id
            ]
            n_connections = min(len(country_peers), self._rng.randint(3, 8))
            life.social_connections = self._rng.sample(country_peers, n_connections) if country_peers else []

            # Same-role connections (cross-country)
            role_peers = [
                aid for aid in by_role.get(role, [])
                if aid != agent.agent_id
            ]
            n_role = min(len(role_peers), self._rng.randint(1, 3))
            if role_peers:
                life.social_connections.extend(
                    self._rng.sample(role_peers, n_role)
                )

            # Information sources
            life.information_sources = []

            # EU agents get ECB as info source
            if ecb_id and agent.country in eu_countries and agent.agent_id != ecb_id:
                life.information_sources.append(ecb_id)

            # HF traders follow each other
            if role == AgentRole.HEDGE_FUND_TRADER:
                hf_peers = [
                    aid for aid in by_role.get(AgentRole.HEDGE_FUND_TRADER, [])
                    if aid != agent.agent_id
                ]
                life.information_sources.extend(hf_peers[:3])

            # Everyone else gets 1-2 random info sources from their country
            if not life.information_sources and country_peers:
                n_info = min(len(country_peers), self._rng.randint(1, 2))
                life.information_sources = self._rng.sample(country_peers, n_info)

            # Deduplicate
            life.social_connections = list(set(life.social_connections))
            life.information_sources = list(set(life.information_sources))

    # ------------------------------------------------------------------
    # Per-tick processing
    # ------------------------------------------------------------------

    def process_tick(self, agents: list[HumanTwin], world, tick: int) -> list[dict]:
        """
        Run one society tick:
        1. Generate context messages (macro events → relevant agents)
        2. Deliver messages to inboxes
        3. Update beliefs from inbox
        4. Each agent makes a decision
        5. Agents send messages about their decisions
        6. Return decisions for WorldEngine to apply

        Returns list of decision dicts: [{agent_id, action, usd_delta, reasoning, messages_sent}]
        """
        sim_date = str(world.simulation_date)
        decisions: list[dict] = []

        # 1. Generate system messages based on world state
        system_messages = self._generate_system_messages(world, tick, sim_date)

        # 2. Deliver system messages to relevant agents
        for msg in system_messages:
            self._deliver_message(msg)

        # 3. Process each agent
        for agent in agents:
            life = self.lives.get(agent.agent_id)
            if not life:
                continue

            # 3a. Collect inbox (messages from network + system)
            inbox = list(life.inbox)
            life.inbox.clear()

            # 3b. Update beliefs based on messages
            self._update_beliefs(agent, life, inbox)

            # 3c. Make a decision
            decision = self._make_decision(agent, life, world)
            if decision:
                life.recent_decisions.append(decision)
                if len(life.recent_decisions) > MAX_RECENT_DECISIONS:
                    life.recent_decisions = life.recent_decisions[-MAX_RECENT_DECISIONS:]
                decisions.append(decision)

                # 3d. Send messages about the decision
                outgoing = self._generate_decision_messages(
                    agent, life, decision, tick, sim_date,
                )
                for msg in outgoing:
                    self._deliver_message(msg)

        return decisions

    def _generate_system_messages(
        self, world, tick: int, sim_date: str,
    ) -> list[AgentMessage]:
        """Generate messages from 'the world' to relevant agents."""
        messages: list[AgentMessage] = []

        # ECB president broadcasts policy if it's a policy tick (every 30 ticks)
        if tick % 30 == 0:
            ecb_ids = [
                aid for aid, role in self.role_agents.items()
                if role == AgentRole.ECB_PRESIDENT
            ]
            for ecb_id in ecb_ids:
                rate_bias = self.lives[ecb_id].beliefs.get("rate_bias", 0)
                stance = "hawkish" if rate_bias > 0.1 else "dovish" if rate_bias < -0.1 else "neutral"
                messages.append(AgentMessage(
                    sender_id=ecb_id,
                    receiver_id="broadcast",
                    content=f"ECB policy stance: {stance}. Inflation at {world.macro.global_inflation_pct:.1f}%.",
                    message_type=MessageType.POLICY_ANNOUNCEMENT,
                    tick=tick,
                    simulation_date=sim_date,
                    metadata={"stance": stance, "inflation": world.macro.global_inflation_pct},
                ))

        # Soldiers send frontline reports each tick
        soldier_ids = [
            aid for aid, role in self.role_agents.items()
            if role == AgentRole.SOLDIER
        ]
        for sid in soldier_ids:
            life = self.lives.get(sid)
            if not life:
                continue
            conflict = life.beliefs.get("conflict_risk", 0.5)
            if self._rng.random() < 0.3:  # 30% chance of report
                messages.append(AgentMessage(
                    sender_id=sid,
                    receiver_id="broadcast",
                    content=f"Frontline report: situation {'intense' if conflict > 0.7 else 'stable'}.",
                    message_type=MessageType.NEWS,
                    tick=tick,
                    simulation_date=sim_date,
                    metadata={"conflict_level": conflict},
                ))

        # Turkish households discuss inflation
        tr_ids = [
            aid for aid, role in self.role_agents.items()
            if role == AgentRole.TURKISH_HOUSEHOLD
        ]
        tr_country = world.countries.get("TR")
        if tr_country and self._rng.random() < 0.4:
            for tid in tr_ids[:2]:  # only some talk each tick
                messages.append(AgentMessage(
                    sender_id=tid,
                    receiver_id="broadcast",
                    content=f"Prices up again. Inflation at {tr_country.economy.inflation_pct:.0f}%. Converting to USD.",
                    message_type=MessageType.RUMOR,
                    tick=tick,
                    simulation_date=sim_date,
                    metadata={"inflation": tr_country.economy.inflation_pct},
                ))

        # Iranian merchants share sanctions intel
        ir_ids = [
            aid for aid, role in self.role_agents.items()
            if role == AgentRole.IRANIAN_MERCHANT
        ]
        if ir_ids and self._rng.random() < 0.25:
            sender = self._rng.choice(ir_ids)
            messages.append(AgentMessage(
                sender_id=sender,
                receiver_id="broadcast",
                content="New hawala route through Dubai. Crypto still works for small transfers.",
                message_type=MessageType.TRADE,
                tick=tick,
                simulation_date=sim_date,
                metadata={"sanctions_evasion": True},
            ))

        # HF traders share signals
        hf_ids = [
            aid for aid, role in self.role_agents.items()
            if role == AgentRole.HEDGE_FUND_TRADER
        ]
        if hf_ids and self._rng.random() < 0.5:
            sender = self._rng.choice(hf_ids)
            vix = world.macro.vix
            signal = "risk-off" if vix > 25 else "risk-on" if vix < 15 else "neutral"
            messages.append(AgentMessage(
                sender_id=sender,
                receiver_id="broadcast",
                content=f"Signal: {signal}. VIX at {vix:.1f}. Oil ${world.macro.oil_price_brent:.0f}.",
                message_type=MessageType.TRADE,
                tick=tick,
                simulation_date=sim_date,
                metadata={"signal": signal, "vix": vix},
            ))

        # NK state propaganda (only to NK workers)
        nk_ids = [
            aid for aid, role in self.role_agents.items()
            if role == AgentRole.NK_STATE_WORKER
        ]
        if nk_ids:
            for nk_id in nk_ids:
                messages.append(AgentMessage(
                    sender_id="state_broadcaster_kp",
                    receiver_id=nk_id,
                    content="Supreme Leader reports record harvests. Economy stronger than ever.",
                    message_type=MessageType.NEWS,
                    tick=tick,
                    simulation_date=sim_date,
                    metadata={"propaganda": True},
                ))

        return messages

    def _deliver_message(self, msg: AgentMessage) -> None:
        """Deliver a message to the appropriate agent(s)."""
        self.message_log.append(msg)
        if len(self.message_log) > self._max_log:
            self.message_log = self.message_log[-self._max_log:]

        if msg.receiver_id == "broadcast":
            # Deliver to sender's social connections
            life = self.lives.get(msg.sender_id)
            if life:
                targets = set(life.social_connections)
                # Also deliver to anyone who has sender as info source
                for aid, alife in self.lives.items():
                    if msg.sender_id in alife.information_sources:
                        targets.add(aid)
                for target_id in targets:
                    target_life = self.lives.get(target_id)
                    if target_life:
                        target_life.inbox.append(msg)
                        self._mailboxes.setdefault(target_id, []).append(msg)
                        if len(self._mailboxes[target_id]) > MAX_MESSAGE_HISTORY:
                            self._mailboxes[target_id] = self._mailboxes[target_id][-MAX_MESSAGE_HISTORY:]
            else:
                # System message (no sender life) — deliver to specific known targets
                # This handles state_broadcaster_kp → NK workers
                target_life = self.lives.get(msg.receiver_id)
                if target_life:
                    target_life.inbox.append(msg)
                    self._mailboxes.setdefault(msg.receiver_id, []).append(msg)
        else:
            # Direct message
            target_life = self.lives.get(msg.receiver_id)
            if target_life:
                target_life.inbox.append(msg)
                self._mailboxes.setdefault(msg.receiver_id, []).append(msg)
                if len(self._mailboxes[msg.receiver_id]) > MAX_MESSAGE_HISTORY:
                    self._mailboxes[msg.receiver_id] = self._mailboxes[msg.receiver_id][-MAX_MESSAGE_HISTORY:]

    def _update_beliefs(
        self, agent: HumanTwin, life: AgentLife, inbox: list[AgentMessage],
    ) -> None:
        """Update agent beliefs based on received messages, filtered by literacy and trust."""
        if not inbox:
            return

        for msg in inbox:
            weight = MESSAGE_INFLUENCE_WEIGHT.get(msg.message_type, 0.2)

            # Literacy filter: low literacy agents are more influenced by rumors,
            # less influenced by complex policy announcements
            if msg.message_type == MessageType.POLICY_ANNOUNCEMENT:
                weight *= agent.financial_literacy
            elif msg.message_type == MessageType.RUMOR:
                weight *= (1.2 - agent.financial_literacy)  # less literate = more susceptible
            elif msg.message_type == MessageType.TRADE:
                weight *= agent.financial_literacy * 0.8

            # Trust filter: messages from info sources have more weight
            if msg.sender_id in life.information_sources:
                weight *= 1.5

            # Hop decay: relayed messages lose influence
            weight *= max(0.2, 1.0 - msg.hops * 0.3)

            # Apply belief updates based on message metadata
            meta = msg.metadata

            if "inflation" in meta:
                inflation_val = meta["inflation"]
                # Normalize to 0-1 belief
                inflation_belief = min(1.0, inflation_val / 100.0)
                life.beliefs["inflation_outlook"] = (
                    life.beliefs.get("inflation_outlook", 0.3) * (1 - weight * 0.3)
                    + inflation_belief * weight * 0.3
                )

            if "stance" in meta:
                if meta["stance"] == "hawkish":
                    life.beliefs["inflation_outlook"] = max(
                        0, life.beliefs.get("inflation_outlook", 0.3) - weight * 0.05
                    )
                elif meta["stance"] == "dovish":
                    life.beliefs["inflation_outlook"] = min(
                        1, life.beliefs.get("inflation_outlook", 0.3) + weight * 0.03
                    )

            if "signal" in meta:
                if meta["signal"] == "risk-off":
                    life.beliefs["market_fear"] = min(
                        1, life.beliefs.get("market_fear", 0.2) + weight * 0.1
                    )
                elif meta["signal"] == "risk-on":
                    life.beliefs["market_fear"] = max(
                        0, life.beliefs.get("market_fear", 0.2) - weight * 0.1
                    )

            if "conflict_level" in meta:
                life.beliefs["conflict_risk"] = (
                    life.beliefs.get("conflict_risk", 0.3) * 0.7
                    + meta["conflict_level"] * 0.3 * weight
                )

            if meta.get("propaganda"):
                life.beliefs["government_trust"] = min(
                    1.0, life.beliefs.get("government_trust", 0.5) + 0.01
                )

            if meta.get("sanctions_evasion"):
                life.beliefs["crypto_utility"] = min(
                    1.0, life.beliefs.get("crypto_utility", 0.3) + weight * 0.05
                )

    def _make_decision(
        self, agent: HumanTwin, life: AgentLife, world,
    ) -> Optional[dict]:
        """
        Agent makes one decision based on their beliefs.
        Returns dict with: agent_id, action, usd_delta, reasoning, tick
        """
        beliefs = life.beliefs
        country = world.countries.get(agent.country)

        action = "hold"
        usd_delta = 0.0
        reasoning = ""

        role = self.role_agents.get(agent.agent_id, AgentRole.GENERIC)

        # --- Role-specific decision logic ---

        if role == AgentRole.SHOP_CLERK:
            inflation = beliefs.get("inflation_outlook", 0.3)
            if inflation > 0.5:
                usd_delta = 0.01 * inflation
                action = "save in USD (prices rising)"
                reasoning = f"Seeing prices rise daily, inflation outlook {inflation:.0%}"
            elif beliefs.get("local_price_pressure", 0.3) > 0.6:
                action = "consume now (prices going up)"
                reasoning = "Buying before prices go higher"
            else:
                return None

        elif role == AgentRole.ECB_PRESIDENT:
            inflation = world.macro.global_inflation_pct
            if inflation > 3.5:
                life.beliefs["rate_bias"] = min(1, beliefs.get("rate_bias", 0) + 0.1)
                action = "signal hawkish stance"
                reasoning = f"Inflation at {inflation:.1f}% above target, tightening"
            elif inflation < 1.5:
                life.beliefs["rate_bias"] = max(-1, beliefs.get("rate_bias", 0) - 0.1)
                action = "signal dovish stance"
                reasoning = f"Inflation at {inflation:.1f}% below target, easing"
            else:
                action = "maintain current stance"
                reasoning = f"Inflation at {inflation:.1f}%, near target"
            return {
                "agent_id": agent.agent_id, "action": action,
                "usd_delta": 0, "reasoning": reasoning,
            }

        elif role == AgentRole.SOLDIER:
            conflict = beliefs.get("conflict_risk", 0.5)
            if conflict > 0.7:
                usd_delta = 0.005
                action = "send money home (conflict intensifying)"
                reasoning = f"Frontline danger high ({conflict:.0%}), securing family finances"
            else:
                return None

        elif role == AgentRole.NK_STATE_WORKER:
            # NK workers don't make meaningful economic decisions
            return None

        elif role == AgentRole.HEDGE_FUND_TRADER:
            fear = beliefs.get("market_fear", 0.2)
            risk_appetite = beliefs.get("risk_appetite", 0.6)
            if fear > 0.5:
                usd_delta = 0.03 * fear
                agent.equity_exposure = max(0, agent.equity_exposure - 0.02)
                action = "risk-off: rotating to USD, cutting equity"
                reasoning = f"Fear elevated ({fear:.0%}), de-risking"
            elif fear < 0.15 and risk_appetite > 0.5:
                usd_delta = -0.02
                agent.equity_exposure = min(1, agent.equity_exposure + 0.01)
                action = "risk-on: adding equity, selling USD"
                reasoning = f"Low fear ({fear:.0%}), adding risk"
            else:
                drift = self._rng.gauss(0, 0.005)
                if abs(drift) < 0.002:
                    return None
                usd_delta = drift
                action = f"micro-adjust {'long' if drift > 0 else 'short'} USD"
                reasoning = "Intraday positioning"

        elif role == AgentRole.TURKISH_HOUSEHOLD:
            inflation = beliefs.get("inflation_outlook", 0.5)
            lira_trust = beliefs.get("currency_confidence", 0.3)
            if inflation > 0.6 or lira_trust < 0.25:
                usd_delta = 0.03 * (1 - lira_trust)
                action = "convert lira to USD/gold"
                reasoning = f"Lira confidence at {lira_trust:.0%}, inflation outlook {inflation:.0%}"
            elif beliefs.get("dollarization_urge", 0.5) > 0.6:
                usd_delta = 0.02
                action = "buy more dollars (neighbors doing it too)"
                reasoning = "Social pressure to dollarize"
            else:
                return None

        elif role == AgentRole.IRANIAN_MERCHANT:
            sanctions = beliefs.get("sanctions_severity", 0.5)
            crypto = beliefs.get("crypto_utility", 0.3)
            if sanctions > 0.6 and crypto > 0.5:
                agent.crypto_exposure = min(1, agent.crypto_exposure + 0.02)
                usd_delta = 0.01
                action = "move value through crypto + hawala"
                reasoning = f"Sanctions at {sanctions:.0%}, crypto utility {crypto:.0%}"
            elif sanctions > 0.7:
                usd_delta = 0.015
                action = "accumulate USD via unofficial channels"
                reasoning = f"Severe sanctions ({sanctions:.0%}), hedging via parallel market"
            else:
                return None

        else:
            # Generic agent: use beliefs for simple decisions
            fear = beliefs.get("market_fear", 0.2)
            inflation = beliefs.get("inflation_outlook", 0.3)
            if fear > 0.5:
                usd_delta = 0.01
                action = "increase savings (fearful)"
                reasoning = f"Market fear at {fear:.0%}"
            elif inflation > 0.6 and country:
                usd_delta = 0.01 * agent.financial_literacy
                action = "shift to USD (inflation concern)"
                reasoning = f"Inflation outlook {inflation:.0%}"
            else:
                return None

        return {
            "agent_id": agent.agent_id,
            "action": action,
            "usd_delta": usd_delta,
            "reasoning": reasoning,
        }

    def _generate_decision_messages(
        self, agent: HumanTwin, life: AgentLife,
        decision: dict, tick: int, sim_date: str,
    ) -> list[AgentMessage]:
        """After making a decision, agent tells their network."""
        messages: list[AgentMessage] = []
        role = self.role_agents.get(agent.agent_id, AgentRole.GENERIC)

        # Only some roles actively share
        if role in (AgentRole.NK_STATE_WORKER,):
            return messages

        # Probability of sharing depends on social influence
        if self._rng.random() > agent.social_influence:
            return messages

        if role == AgentRole.ECB_PRESIDENT:
            msg_type = MessageType.POLICY_ANNOUNCEMENT
        elif role == AgentRole.HEDGE_FUND_TRADER:
            msg_type = MessageType.TRADE
        elif role == AgentRole.IRANIAN_MERCHANT:
            msg_type = MessageType.RUMOR
        else:
            msg_type = MessageType.PERSONAL

        msg = AgentMessage(
            sender_id=agent.agent_id,
            receiver_id="broadcast",
            content=f"{agent.name}: {decision['action']}",
            message_type=msg_type,
            tick=tick,
            simulation_date=sim_date,
            metadata={
                "action": decision["action"],
                "usd_delta": decision.get("usd_delta", 0),
            },
        )
        messages.append(msg)
        return messages

    # ------------------------------------------------------------------
    # Query API (for perspective endpoints)
    # ------------------------------------------------------------------

    def get_perspective(self, agent_id: str, agent: HumanTwin, world) -> Optional[dict]:
        """Get the world as seen through one agent's eyes."""
        life = self.lives.get(agent_id)
        if not life:
            return None

        role = self.role_agents.get(agent_id, AgentRole.GENERIC)
        role_profile = ROLE_PROFILES.get(role.value, ROLE_PROFILES["generic"])

        # Get agent's country data
        country = world.countries.get(agent.country)
        country_data = None
        if country:
            country_data = {
                "name": country.name,
                "inflation_pct": round(country.economy.inflation_pct, 2),
                "unemployment_pct": round(country.economy.unemployment_pct, 2),
                "gdp_usd_bn": round(country.economy.gdp_usd_bn, 2),
                "sanctioned": country.politics.sanctions_target,
                "currency_regime": country.economy.currency_regime.value,
            }

        # Recent messages this agent received
        recent_messages = [
            m.to_dict() for m in self._mailboxes.get(agent_id, [])[-20:]
        ]

        # Social network names
        connections = []
        for cid in life.social_connections[:15]:
            for h in world.households:
                if h.agent_id == cid:
                    c_role = self.role_agents.get(cid, AgentRole.GENERIC)
                    connections.append({
                        "agent_id": cid,
                        "name": h.name,
                        "country": h.country,
                        "role": c_role.value,
                    })
                    break

        info_sources = []
        for sid in life.information_sources[:10]:
            for h in world.households:
                if h.agent_id == sid:
                    s_role = self.role_agents.get(sid, AgentRole.GENERIC)
                    info_sources.append({
                        "agent_id": sid,
                        "name": h.name,
                        "role": s_role.value,
                    })
                    break

        return {
            "agent_id": agent_id,
            "name": agent.name,
            "tier": agent.tier.value,
            "country": agent.country,
            "age": agent.age,
            "role": role.value,
            "role_label": role_profile["label"],
            "role_icon": role_profile["icon"],
            "role_desc": role_profile["desc"],
            "financial_literacy": agent.financial_literacy,
            "risk_tolerance": agent.risk_tolerance.value,
            "portfolio": {
                "usd_exposure": round(agent.usd_exposure, 4),
                "eur_exposure": round(agent.eur_exposure, 4),
                "equity_exposure": round(agent.equity_exposure, 4),
                "crypto_exposure": round(agent.crypto_exposure, 4),
                "net_wealth_eur": round(agent.net_wealth_eur, 2),
            },
            "life": life.to_dict(),
            "country_data": country_data,
            "recent_messages": recent_messages,
            "social_connections": connections,
            "information_sources": info_sources,
            "macro_snapshot": {
                "vix": round(world.macro.vix, 2),
                "oil": round(world.macro.oil_price_brent, 2),
                "gold": round(world.macro.gold_price_usd, 2),
                "bitcoin": round(world.macro.bitcoin_price_usd, 2),
                "inflation": round(world.macro.global_inflation_pct, 2),
            },
        }

    def get_agent_messages(self, agent_id: str, limit: int = 50) -> list[dict]:
        """Get message history for an agent."""
        msgs = self._mailboxes.get(agent_id, [])
        return [m.to_dict() for m in msgs[-limit:]]

    def get_agents_by_role(self, role: str) -> list[str]:
        """Get all agent_ids with a given role."""
        try:
            target_role = AgentRole(role)
        except ValueError:
            return []
        return [aid for aid, r in self.role_agents.items() if r == target_role]

    def get_all_roles(self) -> list[dict]:
        """List all roles with agent counts."""
        from collections import Counter
        counts = Counter(r.value for r in self.role_agents.values())
        result = []
        for role_key, profile in ROLE_PROFILES.items():
            if role_key == "generic":
                continue
            result.append({
                "role": role_key,
                "label": profile["label"],
                "icon": profile["icon"],
                "desc": profile["desc"],
                "count": counts.get(role_key, 0),
            })
        return result
