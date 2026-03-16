# NEXUS = HumanTwin

**A Living Synthetic Economy of Human Agents, Predicting Markets from Households to Central Banks**

> *One million heterogeneous agents — from central banks to ordinary households — inhabiting a persistent twin of Earth's financial system. When macro shocks hit, every tier reacts differently. Exchange rate disconnect, banking contagion, and household dollarization emerge from the bottom up.*

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square)](https://python.org)
[![Vue](https://img.shields.io/badge/Vue-3.4-green?style=flat-square)](https://vuejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal?style=flat-square)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-AGPL--3.0-purple?style=flat-square)](LICENSE)

---

## What is NEXUS?

NEXUS is a PhD research platform that builds a living synthetic twin of the global economy. Unlike [MiroFish](https://github.com/666ghj/MiroFish) (which generates agents from documents to simulate social media reactions), NEXUS builds a **persistent, econometrically-calibrated population** of economic agents. Each agent has a real identity — income, debt, financial literacy, risk tolerance — drawn from real survey data (ECB Household Finance and Consumption Survey).

The central scientific question: **why does the Meese-Rogoff Exchange Rate Disconnect exist?** Why can't macro models predict short-run FX rates despite fundamentals clearly mattering long-run? NEXUS answers this by showing the mechanism: hedge funds react to a Fed announcement in 2 minutes; Italian households react 6 weeks later through their grocery bill. That gap *is* the disconnect.

```
Fed raises rates +75bps
        │
        ├─ T1 Central banks      → react instantly   (sentiment: +1.000)
        ├─ T2 Macro hedge funds  → react in 2 min    (sentiment: +0.924) ← price overshoots
        ├─ T3 Commercial banks   → react in minutes  (sentiment: +0.854)
        ├─ T4 Institutional AMs  → react in 1 day    (sentiment: +0.651)
        ├─ T5 Professional FX    → react in hours    (sentiment: +0.436)
        ├─ T6 Ordinary retail    → react in 1 day    (sentiment: +0.127)
        └─ T7 Households         → react in 3 weeks  (sentiment: +0.087) ← fundamental correction
                                                         ↑
                                              Disconnect window = 0.924 - 0.087 = 0.837
```

## Quick start

### Requirements

| Tool | Version |
|------|---------|
| Python | ≥ 3.11, ≤ 3.12 |
| Node.js | ≥ 18 |
| uv | latest |

### 1. Clone and configure

```bash
git clone https://github.com/Leotaby/nexus-sim.git
cd nexus-sim
cp .env.example .env
# Edit .env with your API keys
```

### 2. Install dependencies

```bash
npm run setup:all
```

### 3. Run the simulation (no API keys needed — stub mode)

```bash
cd backend
uv run python scripts/run_macro_shock.py
```

### 4. Start the full stack

```bash
npm run dev
```

Frontend: `http://localhost:3000` · Backend API: `http://localhost:5001`

---

## File structure

```
nexus-sim/
├── .env.example
├── package.json                  # npm scripts: dev, setup:all
├── docker-compose.yml
│
├── backend/
│   ├── run.py                    # FastAPI + uvicorn entry point
│   ├── requirements.txt
│   ├── pyproject.toml
│   │
│   ├── app/
│   │   ├── config.py             # All env vars via pydantic Settings
│   │   ├── models/
│   │   │   ├── agent.py          # HumanTwin dataclass — the core agent
│   │   │   ├── shock.py          # MacroShock — Fed hike, ECB cut, etc.
│   │   │   └── simulation.py     # Simulation session + AgentReaction
│   │   ├── services/
│   │   │   ├── agent_factory.py  # Spawns calibrated populations (HFCS data)
│   │   │   ├── llm_engine.py     # Claude API calls per agent
│   │   │   └── simulation_runner.py  # Orchestrates full simulation
│   │   └── api/
│   │       └── routes.py         # FastAPI endpoints
│   │
│   └── scripts/
│       ├── run_forex_simulation.py   # First runnable: population test
│       └── run_macro_shock.py        # Full pipeline: factory + runner + report
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    └── src/
        ├── main.js
        ├── App.vue               # Root component + nav
        └── views/
            ├── HomeView.vue      # Landing: tier cards + stats
            └── SimulationView.vue  # God's-eye dashboard
```

---

## Seven-tier agent hierarchy

| Tier | Agent type | Calibration source | Speed |
|------|-----------|-------------------|-------|
| T1 | Central banks (Fed, ECB, BoJ…) | Taylor rule, FOMC transcripts | Instant |
| T2 | Global macro hedge funds | CFTC Commitment of Traders | 2 minutes |
| T3 | Commercial / investment banks | BIS Triennial FX Survey | Seconds |
| T4 | Institutional asset managers | Pension FX hedge surveys | 1–3 days |
| T5 | Professional retail FX | OANDA/IG positioning data | Hours |
| T6 | Ordinary retail FX | ESMA retail loss statistics | Days |
| T7 | Households & real economy | **ECB HFCS panel data** | Weeks |

---

## Research agenda (5 PhD papers)

| # | Title | Target journal | Phase |
|---|-------|---------------|-------|
| P1 | NEXUS: A calibrated multi-agent framework for heterogeneous FX dynamics | JEDC / JFM | Phase 1 |
| P2 | Resolving the exchange rate disconnect via heterogeneous agent information processing | JME / AER | Phase 2 |
| P3 | Currency substitution as emergent behavior: household heterogeneity and dollarization | JIE / IMF ER | Phase 3 |
| P4 | Crypto adoption dynamics and disruption of monetary transmission | JFE / RFS | Phase 3 |
| P5 | Digital currencies and policy counterfactuals: a simulation-based evaluation | Econ Policy | Phase 4 |

---

## Roadmap

- **Phase 0 (now):** Core data models, population factory, stub simulation, FastAPI + Vue scaffold
- **Phase 1:** LLM engine active (real Claude API calls per agent), FX order book, 2022 Fed cycle backtest
- **Phase 2:** Banking module, Meese-Rogoff formal test, SNB 2015 replication
- **Phase 3:** Crypto market layer, EM household dollarization, business management module
- **Phase 4:** Policy sandbox (CBDC counterfactuals), DiD evaluation, open-source release

---

## Academic context

PhD candidate: **Hatef (Leo) Tabbakhian**
Target programme: GSEFM — Goethe University Frankfurt (May 2026)
Background: MSc Economics & Finance (Federico II), System-GMM econometrics, KPMG credit risk

The simulation engine architecture is inspired by [OASIS](https://github.com/camel-ai/oasis) (CAMEL-AI).

---

## License

AGPL-3.0 — same as MiroFish. Derivative works must be open-sourced.
