/**
 * stores/world.js — Pinia store for the living world engine
 *
 * Manages: world lifecycle, SSE event streaming, auto-tick, interventions.
 */
import { defineStore } from 'pinia'
import axios from 'axios'

const API = '/api'
const MAX_EVENTS = 200

export const useWorldStore = defineStore('world', {
  state: () => ({
    // World state
    initialized: false,
    running:     false,
    tick:        0,
    simulationDate: '',
    totalAgents: 0,

    // Macro indicators
    macro: null,

    // Countries snapshot
    countries: {},

    // World graph (D3)
    worldGraph:        null,
    worldGraphLoading: false,

    // Event feed (from SSE)
    events: [],

    // Auto-tick
    autoTick:          false,
    _autoTickInterval: null,

    // SSE
    _eventSource: null,

    // UI
    loading: false,
    error:   null,
  }),

  getters: {
    eventFeed: (state) => [...state.events].reverse(),
  },

  actions: {
    // ---------------------------------------------------------------
    // Fetch world graph for D3
    // ---------------------------------------------------------------
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

    // ---------------------------------------------------------------
    // Fetch full world state snapshot
    // ---------------------------------------------------------------
    async fetchState() {
      try {
        const res = await axios.get(`${API}/world/state`)
        const d = res.data
        this.initialized    = d.initialized
        this.running        = d.running
        this.tick           = d.tick
        this.simulationDate = d.simulation_date
        this.macro          = d.macro || null
        this.countries      = d.countries || {}
        this.totalAgents    = d.world_summary?.total_agents || 0
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
      }
    },

    // ---------------------------------------------------------------
    // Initialize world
    // ---------------------------------------------------------------
    async initWorld(config = {}) {
      this.loading = true
      this.error = null
      try {
        const res = await axios.post(`${API}/world/init`, {
          seed: config.seed ?? 42,
          n_households_per_country: config.nHouseholds ?? 50,
          use_llm: config.useLlm ?? false,
        })
        this.initialized    = true
        this.tick           = res.data.tick
        this.simulationDate = res.data.date
        this.totalAgents    = res.data.agents
        this.events = []
        await this.fetchWorldGraph()
        await this.fetchState()
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
      } finally {
        this.loading = false
      }
    },

    // ---------------------------------------------------------------
    // Manual tick
    // ---------------------------------------------------------------
    async manualTick() {
      try {
        const res = await axios.post(`${API}/world/tick`)
        this.tick           = res.data.tick
        this.simulationDate = res.data.date
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
      }
    },

    // ---------------------------------------------------------------
    // Start / stop autonomous ticking
    // ---------------------------------------------------------------
    async startTicking(interval = 1.0, daysPerTick = 1) {
      try {
        await axios.post(`${API}/world/start`, {
          tick_interval_seconds: interval,
          days_per_tick: daysPerTick,
        })
        this.running = true
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
      }
    },

    async stopTicking() {
      try {
        await axios.post(`${API}/world/stop`)
        this.running = false
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
      }
    },

    // ---------------------------------------------------------------
    // Auto-tick toggle (every 3s, manual ticks from frontend)
    // ---------------------------------------------------------------
    toggleAutoTick() {
      this.autoTick = !this.autoTick
      if (this.autoTick) {
        this._autoTickInterval = setInterval(() => this.manualTick(), 3000)
      } else {
        clearInterval(this._autoTickInterval)
        this._autoTickInterval = null
      }
    },

    // ---------------------------------------------------------------
    // SSE: connect to /api/world/events/stream
    // ---------------------------------------------------------------
    startSSE() {
      if (this._eventSource) this._eventSource.close()

      const es = new EventSource(`${API}/world/events/stream`)
      this._eventSource = es

      es.onmessage = (msg) => {
        const data = JSON.parse(msg.data)
        if (data.event === 'keepalive') return

        this.events.push(data)
        if (this.events.length > MAX_EVENTS) this.events.shift()

        // Update tick/date from tick events
        if (data.event_type === 'tick_end') {
          this.tick = data.tick
          if (data.simulation_date) this.simulationDate = data.simulation_date
        }
      }

      es.onerror = () => {
        es.close()
        this._eventSource = null
        // Retry after 3s
        setTimeout(() => {
          if (!this._eventSource) this.startSSE()
        }, 3000)
      }
    },

    stopSSE() {
      if (this._eventSource) {
        this._eventSource.close()
        this._eventSource = null
      }
    },

    // ---------------------------------------------------------------
    // Agent intervention
    // ---------------------------------------------------------------
    async intervene(agentId, intervention) {
      try {
        const res = await axios.post(`${API}/world/agent/${agentId}/intervene`, intervention)
        return res.data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        return null
      }
    },

    // ---------------------------------------------------------------
    // Shock injection
    // ---------------------------------------------------------------
    async injectShock(preset) {
      try {
        const res = await axios.post(`${API}/world/shock/inject`, { shock_preset: preset })
        return res.data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        return null
      }
    },

    // ---------------------------------------------------------------
    // Cleanup
    // ---------------------------------------------------------------
    cleanup() {
      this.stopSSE()
      if (this._autoTickInterval) {
        clearInterval(this._autoTickInterval)
        this._autoTickInterval = null
      }
      this.autoTick = false
    },
  },
})
