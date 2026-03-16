# NEXUS

**Heterogeneous-agent simulation of exchange rate dynamics with LLM-driven cognition**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LLM-powered](https://img.shields.io/badge/LLM-powered-D97757?style=flat-square)](https://github.com/Leotaby/nexus-sim)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue 3](https://img.shields.io/badge/Vue-3.4-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white)](https://vuejs.org)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-purple?style=flat-square)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-forthcoming-b31b1b?style=flat-square)](https://arxiv.org)

---

## 1. Scientific question

The Meese and Rogoff (1983) exchange rate disconnect puzzle remains one of the most persistent failures of international macroeconomics. No structural model has been shown to outperform a random walk at short horizons, despite the fact that macro fundamentals clearly matter at longer horizons (Engel and West, 2005; Itskhoki and Mukhin, 2021). The standard explanation points to unobserved expectation heterogeneity across market participants, but existing models either impose representative-agent assumptions or calibrate only two or three agent types.

NEXUS proposes a different approach. Rather than estimating a reduced-form model of the aggregate exchange rate, NEXUS constructs the full population of heterogeneous agents that *produce* the exchange rate as an emergent outcome. Each agent is an LLM-driven cognitive twin with an empirically calibrated economic profile (income, wealth, debt, financial literacy, risk tolerance) drawn from real survey microdata. A macro shock propagates through the agent population at different speeds depending on each agent's tier, information access, and cognitive architecture. The exchange rate disconnect arises endogenously from the gap between fast-processing institutional agents and slow-processing households.

The core hypothesis: **the Meese-Rogoff disconnect is not a model failure but a measurement of cognitive heterogeneity in shock absorption speed.**

## 2. Preliminary results

The following results come from a live simulation run: Fed +75bps rate hike, 285 agents across 10 countries, 2 rounds.

```
Fed raises rates +75bps
        |
        |-- T1 Central banks      instant     sentiment: +0.438   (hawkish response)
        |-- T2 Macro hedge funds   instant     sentiment: +0.605   (aggressive USD long)
        |-- T3 Commercial banks    instant     sentiment: +0.448   (widen spreads, lean into flow)
        |-- T4 Institutional AMs   round 1     sentiment: -0.086   (mechanical rebalancing, sell USD)
        |-- T5 Professional FX     instant     sentiment: +0.677   (short EUR/USD)
        |-- T6 Ordinary retail     round 1     sentiment: +0.552   (FOMO buying USD)
        |-- T7 Households          round 3+    sentiment:  n/a     (not yet activated)
```

**Key observations:**

- Hedge funds react with strong positive sentiment (+0.605), reasoning through carry trade implications and rate differential widening. They articulate a clear macro thesis and size positions accordingly.
- Institutional asset managers are the only tier to show *negative* sentiment (-0.086) in round 1. Their reasoning cites mechanical portfolio rebalancing: USD appreciation triggers a drift above target FX allocation, requiring them to *sell* USD to restore hedge ratios. This is exactly the behavior documented in the pension fund hedging literature (Campbell, Serfaty-de Medeiros, and Viceira, 2010).
- Ordinary retail traders show strong positive sentiment (+0.552) driven by FOMO and headline reaction, consistent with ESMA data showing retail traders systematically overweight momentum signals.
- Commercial banks widen bid/ask spreads and accumulate inventory, acting as liquidity providers rather than directional traders.
- The disconnect gap between hedge funds at t=0 (+0.605) and households (not yet reacting) captures the core Meese-Rogoff mechanism in real time.
- Net USD flow accelerates from +18.0 in round 0 to +52.2 in round 1 as retail enters.

## 3. Seven-tier agent hierarchy

Each tier is populated with agents whose economic profiles are drawn from empirical calibration sources. The cognitive architecture (system prompt) is tier-specific, encoding the agent's information processing speed, decision heuristics, and behavioral biases.

| Tier | Agent type | N (default) | Calibration source | Information speed | Behavioral prior |
|------|-----------|-------------|-------------------|------------------|-----------------|
| T1 | Central banks (Fed, ECB, BoJ, BoE, SNB, PBoC) | 6 | Taylor rule literature, FOMC transcripts | Instant | Mandate-constrained, stability-seeking |
| T2 | Global macro hedge funds | 6 | CFTC Commitment of Traders | Instant | Carry + momentum + fundamental macro |
| T3 | Commercial bank FX desks | 5 | BIS Triennial FX Survey (2022) | Instant | Market-making, spread capture, flow internalization |
| T4 | Institutional asset managers (pension, SWF) | 5 | Pension FX hedge ratio surveys | 1 round delay | Mechanical rebalancing, liability-driven |
| T5 | Professional retail FX | 50 | OANDA/IG client positioning data | Instant | Technical analysis, leveraged (30:1) |
| T6 | Ordinary retail FX | 150 | ESMA retail trader loss reports | 1 round delay | Social media, herding, FOMO |
| T7 | Households (real economy) | scaled by country | ECB HFCS panel (waves 2010-2021) | 3 round delay | Savings reallocation, dollarization, consumption |

Household agents are calibrated from the ECB Household Finance and Consumption Survey at the country level. Income and wealth follow lognormal distributions fitted to HFCS country medians. Financial literacy is drawn from a beta distribution calibrated to country-level HFCS literacy scores. Countries currently covered: DE, FR, IT, ES, NL, BE, PT, GR, AT, FI, US, CN, IN, TR, AR, RU, IR.

## 4. Architecture

```
nexus/
|-- backend/
|   |-- app/
|   |   |-- config.py                    # Pydantic Settings (env vars)
|   |   |-- models/
|   |   |   |-- agent.py                 # HumanTwin dataclass (core agent)
|   |   |   |-- shock.py                 # MacroShock (rate hike, sanctions, etc.)
|   |   |   |-- simulation.py            # Simulation, RoundResult, AgentReaction
|   |   |   |-- world.py                 # World state container
|   |   |   |-- country.py               # Country model (14 nations)
|   |   |   |-- institution.py           # International institutions (IMF, BIS, etc.)
|   |   |   |-- geopolitical.py          # Sanctions regimes, alliances
|   |   |   |-- political_actor.py       # Parties, governments
|   |   |   |-- nonstate_actor.py        # Non-state actors (threat modeling)
|   |   |-- services/
|   |   |   |-- llm_engine.py            # LLM subprocess calls per agent
|   |   |   |-- simulation_runner.py     # Round orchestration, batch processing
|   |   |   |-- agent_factory.py         # Population factory (HFCS calibration)
|   |   |   |-- world_factory.py         # Full world builder (all entity layers)
|   |   |-- api/
|   |   |   |-- routes.py                # FastAPI endpoints
|   |   |-- utils/
|   |       |-- logger.py                # Structured JSONL logging
|   |       |-- population_stats.py      # Descriptive statistics
|   |-- scripts/
|   |   |-- run_world_simulation.py      # Full world simulation (main entry)
|   |   |-- run_forex_simulation.py      # FX-only population test
|   |   |-- run_macro_shock.py           # Factory + runner + report pipeline
|   |   |-- run_parallel_simulation.py   # Parallel batch runner
|   |   |-- test_agent_profile.py        # Agent prompt inspection
|   |   |-- action_logger.py             # Reaction logging utilities
|   |-- run.py                           # FastAPI + uvicorn entry point
|   |-- requirements.txt
|   |-- pyproject.toml
|-- frontend/
|   |-- src/
|   |   |-- App.vue                      # Root component
|   |   |-- views/
|   |   |   |-- HomeView.vue             # Tier cards + population stats
|   |   |   |-- SimulationView.vue       # Real-time simulation dashboard
|   |   |-- stores/
|   |       |-- simulation.js            # Pinia state management
|   |-- vite.config.js
|-- docker-compose.yml
|-- Dockerfile
```

## 5. Quick start

Requires Python >= 3.11 and [uv](https://github.com/astral-sh/uv). LLM calls require a language model backend (configured via `LLM_CLI` in `.env`).

```bash
# 1. Install Python dependencies
cd backend && uv sync

# 2. Run a Fed rate hike simulation (285 agents, 2 rounds, real LLM reasoning)
uv run python scripts/run_world_simulation.py --fed-hike --hh 10 --rounds 2

# 3. Run with stub reactions (no LLM, for CI or offline testing)
uv run python scripts/run_world_simulation.py --fed-hike --hh 10 --rounds 2 --no-llm
```

Available shock scenarios: `--fed-hike`, `--ecb-cut`, `--russia-sanction`, `--oil-cut`, `--nk-cyber`, `--argentina-default`.

## 6. Target publications

| # | Working title | Target journal | Status |
|---|--------------|---------------|--------|
| P1 | NEXUS: An LLM-driven heterogeneous-agent model for exchange rate dynamics | Journal of Economic Dynamics and Control | Framework paper |
| P2 | Resolving the Meese-Rogoff disconnect via heterogeneous information processing speeds | Journal of Monetary Economics | Core theoretical contribution |
| P3 | Household dollarization as emergent behavior: evidence from a calibrated agent-based model | Journal of International Economics | HFCS-calibrated household layer |
| P4 | Retail herding and FX momentum: an agent-based decomposition of the carry trade | Journal of Financial Economics | Tier interaction dynamics |
| P5 | Policy counterfactuals in a synthetic economy: CBDC adoption and monetary transmission | Review of Financial Studies | Policy simulation layer |

## 7. References

- Campbell, J. Y., Serfaty-de Medeiros, K., & Viceira, L. M. (2010). Global currency hedging. *Journal of Finance*, 65(1), 87-121.
- Engel, C., & West, K. D. (2005). Exchange rates and fundamentals. *Journal of Political Economy*, 113(3), 485-517.
- Itskhoki, O., & Mukhin, D. (2021). Exchange rate disconnect in general equilibrium. *Journal of Political Economy*, 129(8), 2183-2232.
- Meese, R. A., & Rogoff, K. (1983). Empirical exchange rate models of the seventies: Do they fit out of sample? *Journal of International Economics*, 14(1-2), 3-24.

## 8. Author

Hatef (Leo) Tabbakhian
PhD candidate (target: GSEFM, Goethe University Frankfurt, 2026)
MSc Economics and Finance, Universita Federico II di Napoli

## License

AGPL-3.0. Derivative works must be open-sourced.
