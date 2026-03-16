/**
 * NEXUS = HumanTwin
 * stores/simulation.js — Pinia simulation store
 *
 * Central state for the god's-eye dashboard.
 * Handles: simulation lifecycle, polling, SSE streaming, result accumulation.
 */
import { defineStore } from 'pinia'
import axios from 'axios'

const API = '/api'

export const useSimulationStore = defineStore('simulation', {
  state: () => ({
    // Current simulation
    simId:          null,
    status:         'idle',       // idle | pending | running | completed | failed
    shockHeadline:  '',
    numAgents:      0,
    numRounds:      0,

    // Results
    roundResults:   [],           // [{ round_num, sentiment_by_tier, net_usd_flow, exchange_rate_delta }]

    // Population preview (from GET /agents/population)
    population:     null,

    // UI state
    loading:        false,
    error:          null,

    // Polling
    _pollInterval:  null,
  }),

  getters: {
    latestRound:  (state) => state.roundResults[state.roundResults.length - 1] || null,
    isRunning:    (state) => ['pending', 'running'].includes(state.status),
    isComplete:   (state) => state.status === 'completed',

    // The Meese-Rogoff disconnect gap: HF sentiment at round 0 vs household sentiment now
    disconnectGap(state) {
      const r0   = state.roundResults[0]
      const rNow = this.latestRound
      if (!r0 || !rNow) return null
      const hf = r0.sentiment_by_tier?.T2_macro_hedge_fund ?? 0
      const hh = rNow.sentiment_by_tier?.T7_household       ?? 0
      return parseFloat((hf - hh).toFixed(4))
    },

    // Sentiment series per tier — for charting
    sentimentSeries(state) {
      const tiers = [
        'T1_central_bank', 'T2_macro_hedge_fund', 'T3_commercial_bank',
        'T4_institutional_am', 'T5_professional_retail',
        'T6_ordinary_retail', 'T7_household',
      ]
      return tiers.map(tier => ({
        tier,
        label: tier.split('_').slice(1).join(' '),
        data:  state.roundResults.map(r => ({
          round:     r.round_num,
          sentiment: r.sentiment_by_tier?.[tier] ?? null,
        })),
      }))
    },

    // Net USD flow series — for charting
    flowSeries(state) {
      return state.roundResults.map(r => ({
        round: r.round_num,
        flow:  r.net_usd_flow,
      }))
    },
  },

  actions: {
    async fetchPopulation(nHouseholds = 100) {
      this.loading = true
      try {
        const res = await axios.get(`${API}/agents/population`, {
          params: { n_households: nHouseholds }
        })
        this.population = res.data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
      } finally {
        this.loading = false
      }
    },

    async startSimulation(config) {
      this.loading = true
      this.error   = null
      this.reset()

      try {
        const res = await axios.post(`${API}/simulate`, config)
        this.simId         = res.data.simulation_id
        this.status        = 'pending'
        this.numAgents     = res.data.num_agents
        this.shockHeadline = config.shock_preset === 'ecb_cut_50'
          ? 'ECB announces surprise -50bps rate cut'
          : 'Fed raises federal funds rate +75bps'

        this._startPolling()
      } catch (e) {
        this.error  = e.response?.data?.detail || e.message
        this.status = 'failed'
      } finally {
        this.loading = false
      }
    },

    _startPolling() {
      if (this._pollInterval) clearInterval(this._pollInterval)
      this._pollInterval = setInterval(() => this._poll(), 1200)
    },

    async _poll() {
      if (!this.simId) return
      try {
        const res  = await axios.get(`${API}/simulate/${this.simId}`)
        const data = res.data

        this.status    = data.status
        this.numAgents = data.num_agents
        this.numRounds = data.num_rounds

        if (data.rounds) {
          this.roundResults = data.rounds
        }
        if (data.shock_headline) {
          this.shockHeadline = data.shock_headline
        }

        if (['completed', 'failed'].includes(data.status)) {
          clearInterval(this._pollInterval)
          this._pollInterval = null
        }
      } catch {
        // Network error — keep polling
      }
    },

    reset() {
      if (this._pollInterval) {
        clearInterval(this._pollInterval)
        this._pollInterval = null
      }
      this.simId         = null
      this.status        = 'idle'
      this.shockHeadline = ''
      this.numAgents     = 0
      this.numRounds     = 0
      this.roundResults  = []
      this.error         = null
    },
  },
})
