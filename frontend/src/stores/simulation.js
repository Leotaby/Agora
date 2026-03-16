/**
 * stores/simulation.js — Pinia simulation store
 *
 * Central state for the dashboard.
 * Handles: simulation lifecycle, SSE streaming, world graph, agent feed.
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
    roundResults:   [],           // [{ round_num, sentiment_by_tier, net_usd_flow }]

    // World graph (for D3)
    worldGraph:         null,     // { nodes: [], edges: [] }
    worldGraphLoading:  false,

    // Agent feed (last 10 reactions)
    agentReactions:     [],       // [{ tier, action, sentiment, country, key, round_num }]

    // Population preview
    population:     null,

    // UI state
    loading:        false,
    error:          null,

    // Internal
    _pollInterval:  null,
    _eventSource:   null,
  }),

  getters: {
    latestRound:  (state) => state.roundResults[state.roundResults.length - 1] || null,
    isRunning:    (state) => ['pending', 'running'].includes(state.status),
    isComplete:   (state) => state.status === 'completed',

    roundProgress(state) {
      return state.numRounds > 0 ? state.roundResults.length / state.numRounds : 0
    },

    disconnectGap(state) {
      const r0   = state.roundResults[0]
      const rNow = state.roundResults[state.roundResults.length - 1]
      if (!r0 || !rNow) return null
      const hf = r0.sentiment_by_tier?.T2_macro_hedge_fund ?? 0
      const hh = rNow.sentiment_by_tier?.T7_household       ?? 0
      return parseFloat((hf - hh).toFixed(4))
    },

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

    flowSeries(state) {
      return state.roundResults.map(r => ({
        round: r.round_num,
        flow:  r.net_usd_flow,
      }))
    },
  },

  actions: {
    async fetchWorldGraph() {
      this.worldGraphLoading = true
      try {
        const res = await axios.get(`${API}/world/graph`)
        this.worldGraph = res.data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
      } finally {
        this.worldGraphLoading = false
      }
    },

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
        this.simId     = res.data.simulation_id
        this.status    = 'pending'
        this.numAgents = res.data.num_agents
        this.numRounds = config.n_rounds || 6
        this.startSSE()
      } catch (e) {
        this.error  = e.response?.data?.detail || e.message
        this.status = 'failed'
      } finally {
        this.loading = false
      }
    },

    startSSE() {
      if (this._eventSource) this._eventSource.close()
      if (!this.simId) return

      const es = new EventSource(`${API}/simulate/${this.simId}/stream`)
      this._eventSource = es

      es.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.event === 'complete') {
          this.status = 'completed'
          es.close()
          this._eventSource = null
          // Fetch final state for headline etc.
          this._fetchFinal()
          return
        }
        if (data.event === 'error') {
          this.status = 'failed'
          es.close()
          this._eventSource = null
          return
        }

        this.status = 'running'
        this.roundResults.push({
          round_num: data.round_num,
          sentiment_by_tier: data.sentiment_by_tier,
          net_usd_flow: data.net_usd_flow,
        })

        // Feed agent reactions
        if (data.sample_reactions) {
          for (const r of data.sample_reactions) {
            this.agentReactions.push({
              ...r,
              key: `${data.round_num}-${r.tier}-${Date.now()}-${Math.random()}`,
              round_num: data.round_num,
            })
            if (this.agentReactions.length > 10) {
              this.agentReactions.shift()
            }
          }
        }
      }

      es.onerror = () => {
        es.close()
        this._eventSource = null
        // Fallback to polling
        this._startPolling()
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
        if (data.rounds) this.roundResults = data.rounds
        if (data.shock_headline) this.shockHeadline = data.shock_headline
        if (['completed', 'failed'].includes(data.status)) {
          clearInterval(this._pollInterval)
          this._pollInterval = null
        }
      } catch { /* keep polling */ }
    },

    async _fetchFinal() {
      if (!this.simId) return
      try {
        const res = await axios.get(`${API}/simulate/${this.simId}`)
        if (res.data.shock_headline) this.shockHeadline = res.data.shock_headline
        this.numAgents = res.data.num_agents || this.numAgents
        this.numRounds = res.data.num_rounds || this.numRounds
      } catch { /* ignore */ }
    },

    reset() {
      if (this._pollInterval) { clearInterval(this._pollInterval); this._pollInterval = null }
      if (this._eventSource)  { this._eventSource.close(); this._eventSource = null }
      this.simId          = null
      this.status         = 'idle'
      this.shockHeadline  = ''
      this.numAgents      = 0
      this.numRounds      = 0
      this.roundResults   = []
      this.agentReactions = []
      this.error          = null
    },
  },
})
