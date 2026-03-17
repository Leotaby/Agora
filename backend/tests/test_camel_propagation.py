"""
Test: ECB rate cut propagation through the NEXUS persona system.

Traces a -50bps ECB rate cut through the information chain:
  1. ECBPresident (Christine Lagarde) announces — tick 0, instant
  2. HedgeFundTrader (James) reacts — tick 0, within minutes
  3. TurkishHousehold (Ayşe) hears via WhatsApp — tick ~7
  4. ItalianShopClerk (Mario) feels it via supplier prices — tick ~42
  5. NKStateWorker (Jong-su) never hears about it — state media only

This test works with or without CAMEL installed:
  - With CAMEL: full LLM-powered in-character responses
  - Without CAMEL: uses the stub decision system + persona message formatting
"""
import asyncio
import sys
import os

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.world_engine import WorldEngine
from app.models.agent_life import AgentRole
from app.services.agent_personas import (
    get_persona_prompt,
    get_info_delay,
    build_event_message_for_persona,
    INFO_DELAY,
    ROLE_TO_PERSONA,
)


def divider(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


async def main():
    divider("NEXUS CAMEL Integration Test: ECB Rate Cut Propagation")

    # 1. Initialize world
    engine = WorldEngine()
    world = engine.initialize(seed=42, n_households_per_country=5, use_llm=False)
    society = engine._society
    llm = engine._llm_engine

    print(f"World initialized: {world.total_agents} agents")
    print(f"Role agents: {len(society.role_agents)}")

    # Find our key personas
    personas = {}
    for agent_id, role in society.role_agents.items():
        agent = engine._find_agent(agent_id)
        if not agent:
            continue
        if role == AgentRole.ECB_PRESIDENT and "ecb_president" not in personas:
            personas["ecb_president"] = (agent, role)
        elif role == AgentRole.HEDGE_FUND_TRADER and "hedge_fund_trader" not in personas:
            personas["hedge_fund_trader"] = (agent, role)
        elif role == AgentRole.SHOP_CLERK and agent.country == "IT" and "shop_clerk" not in personas:
            personas["shop_clerk"] = (agent, role)
        elif role == AgentRole.TURKISH_HOUSEHOLD and "turkish_household" not in personas:
            personas["turkish_household"] = (agent, role)
        elif role == AgentRole.NK_STATE_WORKER and "nk_state_worker" not in personas:
            personas["nk_state_worker"] = (agent, role)

    print(f"\nKey personas found:")
    for key, (agent, role) in personas.items():
        delay = get_info_delay(role)
        print(f"  {role.value}: {agent.name} ({agent.country}) — info delay: {delay} ticks")

    # 2. Simulate ECB rate cut event
    ecb_headline = "ECB cuts rates by 50 basis points to combat slowing growth"
    ecb_description = (
        "The European Central Bank has cut its main refinancing rate by 50 basis points, "
        "citing deteriorating growth prospects across the Eurozone. President Lagarde "
        "stated the decision was unanimous and signaled further easing if inflation "
        "remains below target. Markets reacted sharply — EUR/USD dropped 80 pips."
    )

    divider("EVENT: ECB Rate Cut -50bps")
    print(f"Headline: {ecb_headline}")
    print(f"Description: {ecb_description[:100]}...")

    # 3. Show how each persona perceives this event
    divider("INFORMATION PROPAGATION: How each agent receives the news")

    for key in ["ecb_president", "hedge_fund_trader", "turkish_household", "shop_clerk", "nk_state_worker"]:
        if key not in personas:
            continue
        agent, role = personas[key]
        delay = get_info_delay(role)
        perceived = build_event_message_for_persona(
            ecb_headline, ecb_description, role, agent, world,
        )

        print(f"\n--- {agent.name} ({role.value}) — delay: {delay} ticks ---")
        print(perceived)

    # 4. Queue the event for all persona agents and simulate ticks
    divider("TICK SIMULATION: Running ticks to see delayed delivery")

    # Queue the event at tick 0
    for agent_id, role in society.role_agents.items():
        if role in ROLE_TO_PERSONA:
            llm.queue_event_for_persona(
                agent_id, role,
                ecb_headline, ecb_description,
                current_tick=0,
            )

    # Run ticks and check who gets events when
    check_ticks = [0, 1, 3, 5, 7, 14, 42, 43]
    for tick_num in check_ticks:
        agents_receiving = []
        for key in ["ecb_president", "hedge_fund_trader", "turkish_household", "shop_clerk", "nk_state_worker"]:
            if key not in personas:
                continue
            agent, role = personas[key]
            due = llm.get_due_events(agent.agent_id, tick_num)
            if due:
                agents_receiving.append(f"{agent.name} ({role.value})")
                # Put events back for display purposes
                for h, d in due:
                    llm.queue_event_for_persona(
                        agent.agent_id, role, h, d,
                        current_tick=tick_num,  # will be immediately due next check
                    )

        if agents_receiving:
            print(f"  Tick {tick_num:3d}: {', '.join(agents_receiving)}")
        else:
            print(f"  Tick {tick_num:3d}: (no new deliveries)")

    # 5. Run actual world ticks to see society decisions
    divider("LIVE TICK: Running world engine with society decisions")

    # Reset event queues since we consumed them above
    llm._pending_events.clear()

    for i in range(3):
        events = await engine.manual_tick()
        interesting = [
            e for e in events
            if e.event_type.value == "agent_decision"
            and e.actor_id in {a.agent_id for _, (a, _) in personas.items()}
        ]
        if interesting:
            for ev in interesting:
                print(f"  Tick {world.tick}: {ev.headline}")
                if ev.description:
                    print(f"    Reasoning: {ev.description[:120]}")

    # 6. Show persona system prompts (trimmed)
    divider("PERSONA SYSTEM PROMPTS (first 300 chars)")

    for key in ["ecb_president", "hedge_fund_trader", "shop_clerk", "turkish_household", "nk_state_worker"]:
        if key not in personas:
            continue
        agent, role = personas[key]
        prompt = get_persona_prompt(role, agent, world)
        if prompt:
            print(f"\n--- {agent.name} ({role.value}) ---")
            print(prompt[:300].strip() + "...")

    # 7. Check CAMEL availability
    divider("CAMEL STATUS")
    try:
        from camel.agents import ChatAgent
        from camel.messages import BaseMessage
        print("CAMEL-AI: INSTALLED and importable")
        print(f"  ChatAgent: {ChatAgent}")
        print(f"  BaseMessage: {BaseMessage}")
        print("\n  To run with full LLM personas, set use_llm=True in world init")
        print("  and ensure ANTHROPIC_API_KEY is set in your environment.")
    except ImportError:
        print("CAMEL-AI: NOT INSTALLED")
        print("  Install with: pip install 'camel-ai[all]'")
        print("  Persona agents will use the stub decision system instead.")
        print("  Message formatting and information delays work without CAMEL.")

    divider("TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
