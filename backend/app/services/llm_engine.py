"""
LLM Engine - drives language model reasoning for each HumanTwin agent.

Each agent call = one LLM subprocess with a distinct prompt
encoding the agent's cognitive architecture and economic identity.
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess

from app.config import settings
from app.models.agent import HumanTwin, AgentTier
from app.models.shock import MacroShock
from app.models.simulation import AgentReaction

# ---------------------------------------------------------------------------
# System prompt templates per tier
# These define the cognitive architecture of each agent type.
# The agent's profile (income, literacy, etc.) is injected at runtime.
# ---------------------------------------------------------------------------

TIER_SYSTEM_PROMPTS: dict[AgentTier, str] = {

    AgentTier.CENTRAL_BANK: """
You are a central bank in the NEXUS macroeconomic simulation.
Your mandate is price stability and financial stability.
You respond to macro shocks by adjusting policy rates and issuing guidance.
You have FULL information and process events instantly.
Your decisions affect ALL other agents in the simulation.

When responding to a macro event, reason as follows:
1. Is this event consistent with your mandate objectives?
2. Does it require a policy response from you?
3. What signal does this send to markets?
4. Do you intervene in FX markets?

Respond ONLY with valid JSON matching this schema:
{"reasoning": "...", "action": "...", "usd_delta": float, "sentiment": float, "policy_signal": "hawkish|dovish|neutral"}
sentiment range: -1.0 (very bearish USD) to +1.0 (very bullish USD)
usd_delta: change in USD exposure as fraction of portfolio (-0.5 to +0.5)
""",

    AgentTier.MACRO_HEDGE_FUND: """
You are a global macro hedge fund manager in the NEXUS simulation.
You trade G10 FX, rates, and equities based on macro fundamentals and momentum.
You have near-complete information, process events in minutes, use leverage (up to 10x).
You actively run carry trades, momentum strategies, and fundamental macro positions.

When responding to a macro event:
1. What does this mean for your existing carry trades?
2. Does this change your macro thesis?
3. What is your immediate position adjustment (size matters - you move markets)?
4. What is your medium-term view (3-month horizon)?

Respond ONLY with valid JSON:
{"reasoning": "...", "action": "...", "usd_delta": float, "sentiment": float, "trade_thesis": "..."}
sentiment range: -1.0 to +1.0
usd_delta: -0.5 to +0.5 (you can make large moves)
""",

    AgentTier.COMMERCIAL_BANK: """
You are the FX trading desk of a major commercial bank in the NEXUS simulation.
You are a market maker: you provide liquidity by quoting bid/ask spreads.
You see client order flow BEFORE it hits the market (information advantage).
Your goal is spread capture and inventory management, not directional trading.

When responding to a macro event:
1. How does this affect your client order flow?
2. Do you widen bid/ask spreads to manage risk?
3. What inventory position do you accumulate?
4. Do you lean into or against the flow?

Respond ONLY with valid JSON:
{"reasoning": "...", "action": "...", "usd_delta": float, "sentiment": float, "spread_action": "widen|tighten|hold"}
usd_delta: -0.3 to +0.3 (inventory positions, not directional bets)
""",

    AgentTier.INSTITUTIONAL_AM: """
You are an institutional asset manager (pension fund/SWF) in the NEXUS simulation.
You manage a large portfolio with liability-matching constraints.
You rebalance FX exposure MECHANICALLY when asset prices change - not based on views.
Your FX decisions are driven by your asset allocation model and hedge ratios.

When responding to a macro event:
1. How does this change your asset prices (bonds, equities)?
2. Does your portfolio drift out of target allocation?
3. How much FX rebalancing is mechanically required?
4. Do you adjust your FX hedge ratio?

Respond ONLY with valid JSON:
{"reasoning": "...", "action": "...", "usd_delta": float, "sentiment": float, "rebalance_required": boolean}
usd_delta: -0.2 to +0.2 (mechanical rebalancing, not speculation)
""",

    AgentTier.PROFESSIONAL_RETAIL: """
You are an experienced retail FX trader in the NEXUS simulation.
You use technical analysis, follow economic calendars, and read macro commentary.
You have moderate financial literacy and some understanding of macro drivers.
You trade with leverage (up to 30:1) but are systematically loss-averse.

When responding to a macro event:
1. What does your technical analysis tell you (levels, breakouts)?
2. Is this consistent with the macro narrative you follow?
3. What is your trade entry (with size - you trade EUR/USD, USD/JPY)?
4. What are your stop-loss and take-profit levels?

Consider your financial literacy score when reasoning.
Respond ONLY with valid JSON:
{"reasoning": "...", "action": "...", "usd_delta": float, "sentiment": float, "entry_rationale": "..."}
usd_delta: -0.4 to +0.4 (leveraged retail account)
""",

    AgentTier.ORDINARY_RETAIL: """
You are an ordinary retail FX trader in the NEXUS simulation.
You have LOW financial literacy. You react primarily to:
- Social media posts and viral content
- News headlines (not the underlying analysis)
- What your peers are doing (social proof)
- FOMO and fear of loss

You often make decisions that are WRONG in aggregate (retail loses money on average).
You are highly susceptible to narrative contagion and herding.

When responding to a macro event:
1. What headline or social media signal caught your attention?
2. What are "people" saying about this? (peer signal)
3. Do you feel FOMO or fear?
4. What impulsive action do you take?

Respond ONLY with valid JSON:
{"reasoning": "...", "action": "...", "usd_delta": float, "sentiment": float, "emotional_state": "fomo|fear|greed|confused|excited"}
usd_delta: -0.35 to +0.35 (emotional, often poorly timed)
""",

    AgentTier.HOUSEHOLD: """
You are a household in the real economy in the NEXUS simulation.
You do NOT trade FX directly. Your decisions affect exchange rates indirectly through:
- Savings allocation (do you move savings to USD deposits?)
- Import consumption decisions (does your purchasing power affect demand?)
- Dollarization behavior (in high-inflation environments)
- Mortgage and debt servicing (does this affect your disposable income?)

You process macro events SLOWLY - you feel them through your electricity bill,
supermarket prices, and mortgage rate changes, NOT through Bloomberg terminals.
Your information comes from TV news, neighbors, and daily price experience.

Consider your financial literacy score carefully.
Low literacy (<0.4): you barely understand what "interest rates" means.
Medium literacy (0.4-0.7): you understand the general direction but not mechanisms.
High literacy (>0.7): you understand macro transmission but still act slowly.

Respond ONLY with valid JSON:
{"reasoning": "...", "action": "...", "usd_delta": float, "sentiment": float, "real_economy_impact": "..."}
usd_delta: -0.05 to +0.05 (very small, gradual shifts in savings allocation)
""",
}


# ---------------------------------------------------------------------------
# LLM Engine
# ---------------------------------------------------------------------------

class LLMEngine:
    """
    Drives agent reasoning via the LLM backend.
    Each call spawns a subprocess with the agent's full prompt.
    """

    def __init__(self):
        self.cli = settings.LLM_CLI
        self.cli_args = settings.LLM_CLI_ARGS.split()
        self.model = settings.MODEL_NAME

    def _build_user_prompt(self, agent: HumanTwin, shock: MacroShock, round_num: int) -> str:
        """Combine agent profile + shock into user message."""
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
        """Combine system prompt + user message into a single prompt."""
        system = TIER_SYSTEM_PROMPTS[agent.tier].strip()
        user = self._build_user_prompt(agent, shock, round_num)
        return f"{system}\n\n---\n\n{user}"

    def react(
        self,
        agent: HumanTwin,
        shock: MacroShock,
        round_num: int,
        max_tokens: int = 400,
    ) -> AgentReaction:
        """
        Synchronous single-agent reaction via LLM subprocess.
        """
        prompt = self._build_full_prompt(agent, shock, round_num)

        try:
            result = subprocess.run(
                [self.cli, *self.cli_args, "--model", self.model],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr[:200])
            raw = result.stdout.strip()
            data = self._parse_response(raw)

            return AgentReaction(
                agent_id=agent.agent_id,
                tier=agent.tier,
                round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=data.get("reasoning", ""),
                action=data.get("action", "hold"),
                usd_delta=float(data.get("usd_delta", 0.0)),
                sentiment=float(data.get("sentiment", 0.0)),
            )

        except Exception as e:
            return AgentReaction(
                agent_id=agent.agent_id,
                tier=agent.tier,
                round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=f"[LLM ERROR] {str(e)[:120]}",
                action="hold",
                usd_delta=0.0,
                sentiment=0.0,
            )

    async def react_async(
        self,
        agent: HumanTwin,
        shock: MacroShock,
        round_num: int,
    ) -> AgentReaction:
        """Async version using async subprocess for parallel batch processing."""
        prompt = self._build_full_prompt(agent, shock, round_num)

        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli, *self.cli_args, "--model", self.model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode()[:200])
            raw = stdout.decode().strip()
            data = self._parse_response(raw)

            return AgentReaction(
                agent_id=agent.agent_id,
                tier=agent.tier,
                round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=data.get("reasoning", ""),
                action=data.get("action", "hold"),
                usd_delta=float(data.get("usd_delta", 0.0)),
                sentiment=float(data.get("sentiment", 0.0)),
            )

        except Exception as e:
            return AgentReaction(
                agent_id=agent.agent_id,
                tier=agent.tier,
                round_num=round_num,
                shock_id=shock.shock_id,
                reasoning=f"[LLM ERROR] {str(e)[:120]}",
                action="hold",
                usd_delta=0.0,
                sentiment=0.0,
            )

    async def react_batch(
        self,
        agents: list[HumanTwin],
        shock: MacroShock,
        round_num: int,
        concurrency: int = 10,
        progress: dict | None = None,
    ) -> list[AgentReaction]:
        """
        Process a batch of agents concurrently.
        concurrency controls max parallel LLM subprocesses.
        If progress dict is provided, updates agents_done/agents_failed live.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _limited(agent: HumanTwin) -> AgentReaction:
            async with semaphore:
                reaction = await self.react_async(agent, shock, round_num)
                if progress is not None:
                    progress["agents_done"] += 1
                    if reaction.reasoning.startswith("[LLM ERROR]"):
                        progress["agents_failed"] += 1
                        progress["errors"].append({
                            "agent": agent.name,
                            "tier": agent.tier.value,
                            "error": reaction.reasoning[12:],
                        })
                        # Cap stored errors at 20
                        if len(progress["errors"]) > 20:
                            progress["errors"] = progress["errors"][-20:]
                return reaction

        tasks = [_limited(agent) for agent in agents]
        return await asyncio.gather(*tasks)

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """
        Parse JSON from LLM response.
        Handles common LLM formatting issues: markdown fences, trailing text.
        """
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}


# ---------------------------------------------------------------------------
# Convenience: single-agent demo call (used in tests)
# ---------------------------------------------------------------------------

def demo_single_agent_reaction(tier: AgentTier = AgentTier.MACRO_HEDGE_FUND) -> None:
    """
    Quick demo: spawn one agent of the given tier, inject a Fed hike, print reaction.
    Uses LLM backend via subprocess.
    """
    from app.models.shock import fed_rate_hike_75bps
    from app.services.agent_factory import AgentFactory
    import json as _json

    factory = AgentFactory(seed=42)
    agents = factory.build(n_households=0, n_professional_retail=0, n_ordinary_retail=0)
    target = next((a for a in agents if a.tier == tier), None)
    if not target:
        print(f"No agent of tier {tier} found")
        return

    shock = fed_rate_hike_75bps()
    engine = LLMEngine()
    reaction = engine.react(target, shock, round_num=0)

    print(f"\nAgent: {target.name} ({target.tier.value})")
    print(f"Shock: {shock.headline}")
    print(f"\nReaction:")
    print(f"  Action:    {reaction.action}")
    print(f"  Sentiment: {reaction.sentiment:+.3f}")
    print(f"  USD delta: {reaction.usd_delta:+.4f}")
    print(f"  Reasoning: {reaction.reasoning[:200]}...")
