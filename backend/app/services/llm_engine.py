"""
LLM Engine — drives agent reasoning via CAMEL ChatAgent instances.

Each HumanTwin with a persona becomes a CAMEL ChatAgent with persistent
memory across ticks. The agent's rich persona prompt (from agent_personas.py)
becomes the system message. World events are filtered by information access
level before being delivered as user messages.

Falls back to subprocess CLI calls for agents without CAMEL personas.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from typing import Optional

from app.config import settings
from app.models.agent import HumanTwin, AgentTier
from app.models.agent_life import AgentRole
from app.models.shock import MacroShock
from app.models.simulation import AgentReaction
from app.services.agent_personas import (
    PERSONA_PROMPTS,
    ROLE_TO_PERSONA,
    get_persona_prompt,
    get_info_delay,
    build_event_message_for_persona,
    parse_persona_response,
    INFO_DELAY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legacy tier prompts (for non-persona agents using subprocess fallback)
# ---------------------------------------------------------------------------

TIER_SYSTEM_PROMPTS: dict[AgentTier, str] = {
    AgentTier.CENTRAL_BANK: "You are a central bank in a macro simulation. Respond ONLY with JSON: {\"reasoning\": \"...\", \"action\": \"...\", \"usd_delta\": float, \"sentiment\": float}",
    AgentTier.MACRO_HEDGE_FUND: "You are a macro hedge fund. Respond ONLY with JSON: {\"reasoning\": \"...\", \"action\": \"...\", \"usd_delta\": float, \"sentiment\": float}",
    AgentTier.COMMERCIAL_BANK: "You are a commercial bank FX desk. Respond ONLY with JSON: {\"reasoning\": \"...\", \"action\": \"...\", \"usd_delta\": float, \"sentiment\": float}",
    AgentTier.INSTITUTIONAL_AM: "You are an institutional asset manager. Respond ONLY with JSON: {\"reasoning\": \"...\", \"action\": \"...\", \"usd_delta\": float, \"sentiment\": float}",
    AgentTier.PROFESSIONAL_RETAIL: "You are a professional retail FX trader. Respond ONLY with JSON: {\"reasoning\": \"...\", \"action\": \"...\", \"usd_delta\": float, \"sentiment\": float}",
    AgentTier.ORDINARY_RETAIL: "You are an ordinary retail trader. Respond ONLY with JSON: {\"reasoning\": \"...\", \"action\": \"...\", \"usd_delta\": float, \"sentiment\": float}",
    AgentTier.HOUSEHOLD: "You are a household. Respond ONLY with JSON: {\"reasoning\": \"...\", \"action\": \"...\", \"usd_delta\": float, \"sentiment\": float}",
}


def _try_import_camel():
    """Lazily import CAMEL components. Returns None if not installed."""
    try:
        from camel.agents import ChatAgent
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType
        return ChatAgent, ModelFactory, ModelPlatformType
    except ImportError:
        logger.warning("camel-ai not installed — persona agents will use stub decisions")
        return None


class LLMEngine:
    """
    Drives agent reasoning via CAMEL ChatAgent (primary) or CLI subprocess (fallback).

    CAMEL ChatAgents are created lazily per persona and persist across ticks,
    maintaining conversation history for contextual reasoning.
    """

    def __init__(self):
        self.cli = settings.LLM_CLI
        self.cli_args = settings.LLM_CLI_ARGS.split()
        self.model = settings.MODEL_NAME

        # CAMEL agents: agent_id -> ChatAgent instance
        self._camel_agents: dict[str, object] = {}
        self._camel_available: Optional[bool] = None
        self._camel_modules = None

        # Pending events queue per agent (delayed delivery)
        # agent_id -> [(delivery_tick, event_headline, event_description)]
        self._pending_events: dict[str, list[tuple[int, str, str]]] = {}

    def _ensure_camel(self) -> bool:
        """Check if CAMEL is available, cache the result."""
        if self._camel_available is None:
            result = _try_import_camel()
            if result is None:
                self._camel_available = False
            else:
                self._camel_available = True
                self._camel_modules = result
        return self._camel_available

    def _get_or_create_camel_agent(
        self,
        agent: HumanTwin,
        role: AgentRole,
        world,
    ) -> Optional[object]:
        """Get or create a CAMEL ChatAgent for this persona."""
        if not self._ensure_camel():
            return None

        ChatAgent, ModelFactory, ModelPlatformType = self._camel_modules

        if agent.agent_id in self._camel_agents:
            return self._camel_agents[agent.agent_id]

        # Build the persona system prompt
        system_prompt = get_persona_prompt(role, agent, world)
        if not system_prompt:
            return None

        # Create the CAMEL model instance
        model = None
        try:
            model = ModelFactory.create(
                model_platform=ModelPlatformType.ANTHROPIC,
                model_type=self.model,
                model_config_dict={
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to create CAMEL Anthropic model: {e}")
            try:
                model = ModelFactory.create(
                    model_platform=ModelPlatformType.DEFAULT,
                    model_type="gpt-4o-mini",
                    model_config_dict={"max_tokens": 500, "temperature": 0.7},
                )
            except Exception:
                return None

        # Create the ChatAgent — CAMEL accepts str for system_message
        chat_agent = ChatAgent(
            system_message=system_prompt,
            model=model,
        )

        self._camel_agents[agent.agent_id] = chat_agent
        logger.info(f"Created CAMEL agent for {agent.name} ({role.value})")
        return chat_agent

    def queue_event_for_persona(
        self,
        agent_id: str,
        role: AgentRole,
        event_headline: str,
        event_description: str,
        current_tick: int,
    ) -> None:
        """
        Queue a world event for delayed delivery to a persona agent.
        The event will be delivered after INFO_DELAY[role] ticks.
        """
        delay = get_info_delay(role)
        delivery_tick = current_tick + delay

        if agent_id not in self._pending_events:
            self._pending_events[agent_id] = []

        self._pending_events[agent_id].append(
            (delivery_tick, event_headline, event_description)
        )

    def get_due_events(self, agent_id: str, current_tick: int) -> list[tuple[str, str]]:
        """Get events that are due for delivery to this agent at the current tick."""
        if agent_id not in self._pending_events:
            return []

        due = []
        remaining = []
        for delivery_tick, headline, description in self._pending_events[agent_id]:
            if delivery_tick <= current_tick:
                due.append((headline, description))
            else:
                remaining.append((delivery_tick, headline, description))

        self._pending_events[agent_id] = remaining
        return due

    async def react_persona(
        self,
        agent: HumanTwin,
        role: AgentRole,
        world,
        tick: int,
        inbox_messages: list[str] = None,
    ) -> Optional[dict]:
        """
        Get a CAMEL ChatAgent response for a persona agent.

        Collects due events + inbox messages, builds a user prompt,
        and gets the agent's in-character response.

        Returns dict with: reasoning, action, usd_delta, sentiment, communication
        Returns None if CAMEL is not available or agent has nothing to respond to.
        """
        camel_agent = self._get_or_create_camel_agent(agent, role, world)
        if camel_agent is None:
            return None

        # Collect due events (delayed delivery)
        due_events = self.get_due_events(agent.agent_id, tick)

        # Build the user message from events + inbox
        parts = []

        if due_events:
            for headline, description in due_events:
                # Transform raw event into what this persona would perceive
                perceived = build_event_message_for_persona(
                    headline, description, role, agent, world,
                )
                parts.append(perceived)

        if inbox_messages:
            parts.append("--- Messages from your network ---")
            for msg in inbox_messages[-5:]:  # last 5 messages
                parts.append(msg)

        if not parts:
            # Nothing to react to this tick
            return None

        parts.append(f"\n[Simulation tick {tick}, date: {world.simulation_date}]")
        parts.append("How do you react? Respond in character with JSON.")

        user_content = "\n\n".join(parts)

        # Send to CAMEL agent (step() accepts a plain string)
        try:
            response = await asyncio.to_thread(camel_agent.step, user_content)

            # Extract text from response
            if hasattr(response, 'msgs') and response.msgs:
                raw_text = response.msgs[0].content
            elif hasattr(response, 'msg') and response.msg:
                raw_text = response.msg.content
            else:
                raw_text = str(response)

            result = parse_persona_response(raw_text)
            result["raw_response"] = raw_text[:500]
            return result

        except Exception as e:
            logger.error(f"CAMEL agent error for {agent.name}: {e}")
            return {
                "reasoning": f"[CAMEL ERROR] {str(e)[:120]}",
                "action": "hold",
                "usd_delta": 0.0,
                "sentiment": 0.0,
                "communication": "",
            }

    def reset_agents(self):
        """Clear all CAMEL agent instances (called on world re-init)."""
        self._camel_agents.clear()
        self._pending_events.clear()
        logger.info("Reset all CAMEL persona agents")

    # ------------------------------------------------------------------
    # Legacy subprocess methods (for non-CAMEL agents / batch simulation)
    # ------------------------------------------------------------------

    def _build_user_prompt(self, agent: HumanTwin, shock: MacroShock, round_num: int) -> str:
        return f"""
YOUR PROFILE:
{agent.to_prompt_context()}

CURRENT SIMULATION ROUND: {round_num}

MACRO EVENT JUST ANNOUNCED:
{shock.to_prompt_text()}

Based on your profile and cognitive architecture, how do you react to this event?
Remember: you must respond ONLY with valid JSON. No prose, no markdown, no explanation outside the JSON.
        """.strip()

    def _build_full_prompt(self, agent: HumanTwin, shock: MacroShock, round_num: int) -> str:
        system = TIER_SYSTEM_PROMPTS.get(agent.tier, "Respond with JSON.").strip()
        user = self._build_user_prompt(agent, shock, round_num)
        return f"{system}\n\n---\n\n{user}"

    def react(self, agent: HumanTwin, shock: MacroShock, round_num: int, max_tokens: int = 400) -> AgentReaction:
        """Synchronous single-agent reaction via subprocess."""
        prompt = self._build_full_prompt(agent, shock, round_num)
        try:
            result = subprocess.run(
                [self.cli, *self.cli_args, "--model", self.model],
                input=prompt, capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr[:200])
            data = self._parse_response(result.stdout.strip())
            return AgentReaction(
                agent_id=agent.agent_id, tier=agent.tier, round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=data.get("reasoning", ""),
                action=data.get("action", "hold"),
                usd_delta=float(data.get("usd_delta", 0.0)),
                sentiment=float(data.get("sentiment", 0.0)),
            )
        except Exception as e:
            return AgentReaction(
                agent_id=agent.agent_id, tier=agent.tier, round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=f"[LLM ERROR] {str(e)[:120]}",
                action="hold", usd_delta=0.0, sentiment=0.0,
            )

    async def react_async(self, agent: HumanTwin, shock: MacroShock, round_num: int) -> AgentReaction:
        """Async subprocess version."""
        prompt = self._build_full_prompt(agent, shock, round_num)
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli, *self.cli_args, "--model", self.model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()), timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode()[:200])
            data = self._parse_response(stdout.decode().strip())
            return AgentReaction(
                agent_id=agent.agent_id, tier=agent.tier, round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=data.get("reasoning", ""),
                action=data.get("action", "hold"),
                usd_delta=float(data.get("usd_delta", 0.0)),
                sentiment=float(data.get("sentiment", 0.0)),
            )
        except Exception as e:
            return AgentReaction(
                agent_id=agent.agent_id, tier=agent.tier, round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=f"[LLM ERROR] {str(e)[:120]}",
                action="hold", usd_delta=0.0, sentiment=0.0,
            )

    async def react_batch(
        self, agents: list[HumanTwin], shock: MacroShock, round_num: int,
        concurrency: int = 10, progress: dict | None = None,
    ) -> list[AgentReaction]:
        """Process a batch of agents concurrently."""
        semaphore = asyncio.Semaphore(concurrency)
        async def _limited(agent):
            async with semaphore:
                reaction = await self.react_async(agent, shock, round_num)
                if progress is not None:
                    progress["agents_done"] += 1
                    if reaction.reasoning.startswith("[LLM ERROR]"):
                        progress["agents_failed"] += 1
                        progress["errors"].append({
                            "agent": agent.name, "tier": agent.tier.value,
                            "error": reaction.reasoning[12:],
                        })
                        if len(progress["errors"]) > 20:
                            progress["errors"] = progress["errors"][-20:]
                return reaction
        return await asyncio.gather(*[_limited(a) for a in agents])

    @staticmethod
    def _parse_response(raw: str) -> dict:
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}
