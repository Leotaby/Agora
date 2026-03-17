# AGORA

**Agent-Based Banking Stability Simulator**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue 3](https://img.shields.io/badge/Vue-3.4-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white)](https://vuejs.org)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-purple?style=flat-square)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-forthcoming-b31b1b?style=flat-square)](https://arxiv.org)

---

## 1. Research question

How does a localized banking shock, a sovereign debt write-down, a sudden funding freeze, a fire-sale spiral, cascade through the interbank network to produce systemic collapse? AGORA simulates the transmission of financial contagion through an agent-based model of interconnected bank balance sheets, calibrated to the European banking system.

The simulator models five contagion channels:

1. **Solvency channel** - Asset write-downs erode CET1 capital, triggering forced deleveraging
2. **Liquidity channel** - Wholesale funding freezes propagate through the network
3. **Counterparty channel** - Interbank exposure losses cascade from defaulting banks to creditors
4. **Fire sale channel** - Forced asset sales depress prices, triggering mark-to-market losses system-wide
5. **Confidence channel** - Credit spreads widen, funding costs spike, marginal banks become unviable

## 2. Bank network

Five preset banks form a core-periphery interbank network:

| Bank | Type | Country | Role |
|------|------|---------|------|
| ECB | Central bank | EU | Lender of last resort (ELA, TLTRO) |
| Deutsche Bank | G-SIB | DE | Dense core, massive derivatives book |
| BNP Paribas | G-SIB | FR | Diversified eurozone exposure |
| UniCredit | National champion | IT | Italian sovereign concentration |
| Bayerische Landesbank | Landesbank | DE | Small, concentrated, fragile |

Each bank is a fully specified balance sheet: assets (loans, securities, interbank lending, CB reserves), liabilities (deposits, wholesale funding, interbank borrowing, bonds), capital (CET1 ratio, leverage ratio), and liquidity buffers (LCR, NSFR).

## 3. Architecture

```
agora/
|-- backend/
|   |-- app/
|   |   |-- models/
|   |   |   |-- bank.py                 # Bank balance sheets, funding stress, regulatory ratios
|   |   |   |-- interbank_network.py    # Directed weighted interbank lending graph
|   |   |   |-- agent.py               # HumanTwin agent dataclass
|   |   |   |-- shock.py               # MacroShock definitions
|   |   |   |-- simulation.py          # Simulation state, round results
|   |   |-- services/
|   |   |   |-- contagion_engine.py     # Five-channel contagion propagation
|   |   |   |-- llm_engine.py          # LLM calls per agent
|   |   |   |-- simulation_runner.py   # Round orchestration
|   |   |   |-- agent_factory.py       # Agent population factory
|   |   |-- api/
|   |   |   |-- banking_routes.py      # Banking contagion simulation API
|   |   |   |-- routes.py             # Core FastAPI endpoints
|   |-- run.py                         # Uvicorn entry point
|-- frontend/
|   |-- src/
|   |   |-- views/
|   |   |   |-- BankingView.vue        # D3 network graph, contagion timeline, narrative panel
|-- docker-compose.yml
|-- Dockerfile
```

## 4. Quick start

Requires Python >= 3.11 and [uv](https://github.com/astral-sh/uv).

```bash
# Install dependencies
cd backend && uv sync

# Run the Italian sovereign crisis scenario
uv run python -c "from app.services.contagion_engine import ContagionEngine, BankingShock; e = ContagionEngine.build(); e.apply_shock(BankingShock.ITALIAN_SOVEREIGN_CRISIS); e.run_contagion()"

# Start the API server
uv run python run.py
```

## 5. Scenario: Italian sovereign crisis

The default scenario simulates a 30% write-down on Italian government bonds:

1. UniCredit takes an immediate solvency hit from sovereign exposure
2. Interbank counterparties (Deutsche Bank, BNP) mark down UniCredit lending
3. Wholesale funding freezes as confidence drops
4. Fire sales of liquid assets depress market prices
5. ECB intervenes as lender of last resort (ELA facility)

## 6. Target publications

| # | Working title | Target journal | Status |
|---|--------------|---------------|--------|
| P1 | Systemic risk transmission in a heterogeneous banking network: an agent-based approach | Journal of Financial Stability | Framework paper |
| P2 | Contagion channels and central bank intervention: lessons from a simulated Italian sovereign crisis | Journal of Money, Credit and Banking | Core contribution |

## 7. Author

Hatef Tabbakhian (Leo)
PhD candidate
  
MSc Economics and Finance, Universita Federico II di Napoli

## License

AGPL-3.0. Derivative works must be open-sourced.
