<template>
  <div class="sim-view">

    <!-- Config panel (shown before simulation starts) -->
    <div v-if="!simId" class="config-panel">
      <div class="panel-title">Configure simulation</div>

      <div class="form-group">
        <label>Macro shock</label>
        <div class="shock-options">
          <button
            v-for="s in shockPresets" :key="s.id"
            class="shock-btn"
            :class="{ active: selectedShock === s.id }"
            @click="selectedShock = s.id"
          >
            <span class="shock-source">{{ s.source }}</span>
            <span class="shock-label">{{ s.label }}</span>
          </button>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>Households <span class="val">{{ config.n_households }}</span></label>
          <input type="range" min="50" max="2000" step="50" v-model.number="config.n_households" />
        </div>
        <div class="form-group">
          <label>Rounds <span class="val">{{ config.n_rounds }}</span></label>
          <input type="range" min="3" max="15" step="1" v-model.number="config.n_rounds" />
        </div>
      </div>

      <div class="llm-toggle">
        <label class="toggle-wrap">
          <input type="checkbox" v-model="config.use_llm" />
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
          <span class="toggle-label">Use real LLM</span>
        </label>
        <div class="toggle-note">Off = deterministic stub reactions (fast). On = real language model calls per agent.</div>
      </div>

      <button class="run-btn" :disabled="running" @click="startSimulation">
        {{ running ? 'Starting...' : 'Run simulation →' }}
      </button>
    </div>

    <!-- Live simulation dashboard -->
    <div v-if="simId" class="dashboard">
      <div class="dash-header">
        <div>
          <div class="dash-title">Simulation live</div>
          <div class="dash-id">{{ simId.slice(0, 8) }}... · {{ shockHeadline }}</div>
        </div>
        <div class="status-badge" :class="statusCls">{{ status }}</div>
      </div>

      <!-- Tier sentiment grid -->
      <div class="tier-sentiment-grid">
        <div
          class="tier-block"
          v-for="tier in tiersDisplay"
          :key="tier.id"
        >
          <div class="tier-label">{{ tier.shortName }}</div>
          <div class="sentiment-bar-wrap">
            <div
              class="sentiment-bar"
              :class="tier.sentiment >= 0 ? 'positive' : 'negative'"
              :style="{ width: Math.abs(tier.sentiment) * 100 + '%' }"
            ></div>
          </div>
          <div class="sentiment-val" :class="tier.sentiment >= 0 ? 'pos' : 'neg'">
            {{ tier.sentiment >= 0 ? '+' : '' }}{{ tier.sentiment.toFixed(3) }}
          </div>
        </div>
      </div>

      <!-- Disconnect panel -->
      <div class="disconnect-panel" v-if="disconnectGap !== null">
        <div class="dp-label">MEESE-ROGOFF DISCONNECT WINDOW</div>
        <div class="dp-row">
          <div class="dp-item">
            <div class="dp-name">Hedge funds (t=0)</div>
            <div class="dp-val pos">{{ hfSentiment.toFixed(3) }}</div>
          </div>
          <div class="dp-arrow">→</div>
          <div class="dp-item">
            <div class="dp-name">Households (current)</div>
            <div class="dp-val" :class="hhSentiment > 0.05 ? 'pos' : 'dim'">{{ hhSentiment.toFixed(3) }}</div>
          </div>
          <div class="dp-arrow">→</div>
          <div class="dp-item dp-gap">
            <div class="dp-name">Gap</div>
            <div class="dp-val amber">{{ disconnectGap.toFixed(3) }}</div>
          </div>
        </div>
        <div class="dp-note">This gap is the exchange rate disconnect window. It closes as households absorb the shock.</div>
      </div>

      <!-- Round log -->
      <div class="round-log">
        <div class="log-title">Round log</div>
        <div class="log-row log-header">
          <span class="log-round">Round</span>
          <span class="log-flow">Net USD flow</span>
          <span class="log-active">Active tiers</span>
        </div>
        <div class="log-row" v-for="r in roundLog" :key="r.round">
          <span class="log-round">{{ r.round }}</span>
          <span class="log-flow" :class="r.flow >= 0 ? 'pos' : 'neg'">{{ r.flow >= 0 ? '+' : '' }}{{ r.flow.toFixed(3) }}</span>
          <span class="log-active">{{ r.activeTiers }}</span>
        </div>
        <div class="log-empty" v-if="roundLog.length === 0">Waiting for first round...</div>
      </div>

      <!-- New simulation -->
      <button class="new-btn" @click="reset">New simulation</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import axios from 'axios'

const simId        = ref(null)
const status       = ref('pending')
const shockHeadline= ref('')
const running      = ref(false)
const roundResults = ref([])
const selectedShock= ref('fed_hike_75')

const config = reactive({
  n_households:         100,
  n_professional_retail: 20,
  n_ordinary_retail:     50,
  n_rounds:               6,
  use_llm:             false,
  seed:                   42,
})

const shockPresets = [
  { id: 'fed_hike_75', source: 'Fed',  label: '+75bps rate hike' },
  { id: 'ecb_cut_50',  source: 'ECB',  label: '-50bps surprise cut' },
]

const TIER_ORDER = [
  'T1_central_bank', 'T2_macro_hedge_fund', 'T3_commercial_bank',
  'T4_institutional_am', 'T5_professional_retail', 'T6_ordinary_retail', 'T7_household'
]
const TIER_SHORT = {
  'T1_central_bank':        'Central banks',
  'T2_macro_hedge_fund':    'Macro HF',
  'T3_commercial_bank':     'Comm. banks',
  'T4_institutional_am':    'Inst. AM',
  'T5_professional_retail': 'Pro retail',
  'T6_ordinary_retail':     'Ordinary retail',
  'T7_household':           'Households',
}

const latestRound = computed(() => roundResults.value[roundResults.value.length - 1] || null)

const tiersDisplay = computed(() => {
  if (!latestRound.value) return TIER_ORDER.map(id => ({ id, shortName: TIER_SHORT[id], sentiment: 0 }))
  return TIER_ORDER.map(id => ({
    id,
    shortName: TIER_SHORT[id],
    sentiment: latestRound.value.sentiment_by_tier[id] ?? 0,
  }))
})

const hfSentiment = computed(() => {
  const first = roundResults.value[0]
  return first?.sentiment_by_tier?.T2_macro_hedge_fund ?? 0
})
const hhSentiment = computed(() => latestRound.value?.sentiment_by_tier?.T7_household ?? 0)
const disconnectGap = computed(() => {
  if (roundResults.value.length === 0) return null
  return hfSentiment.value - hhSentiment.value
})

const roundLog = computed(() =>
  roundResults.value.map(r => ({
    round: r.round_num,
    flow:  r.net_usd_flow,
    activeTiers: Object.keys(r.sentiment_by_tier).length,
  }))
)

const statusCls = computed(() => ({
  'status-running':   status.value === 'running',
  'status-completed': status.value === 'completed',
  'status-pending':   status.value === 'pending',
}))

async function startSimulation() {
  running.value = true
  try {
    const res = await axios.post('/api/simulate', {
      shock_preset: selectedShock.value,
      ...config,
    })
    simId.value = res.data.simulation_id
    shockHeadline.value = ''
    roundResults.value = []
    status.value = 'running'
    pollSimulation()
  } catch (e) {
    alert('Failed to start simulation: ' + (e.response?.data?.detail || e.message))
  } finally {
    running.value = false
  }
}

async function pollSimulation() {
  const interval = setInterval(async () => {
    try {
      const res = await axios.get(`/api/simulate/${simId.value}`)
      status.value = res.data.status
      shockHeadline.value = res.data.shock_headline || ''
      roundResults.value = res.data.rounds || []
      if (res.data.status === 'completed' || res.data.status === 'failed') {
        clearInterval(interval)
      }
    } catch { clearInterval(interval) }
  }, 1000)
}

function reset() {
  simId.value = null
  status.value = 'pending'
  roundResults.value = []
}
</script>

<style scoped>
.sim-view { padding-top: 48px; }

.config-panel {
  max-width: 680px; margin: 0 auto;
  border: 1px solid var(--border); border-radius: 14px;
  padding: 32px; background: var(--bg2);
}
.panel-title { font-size: 16px; font-weight: 600; margin-bottom: 28px; }

.form-group { margin-bottom: 20px; }
.form-group label { font-size: 11px; color: var(--text3); letter-spacing: 0.06em; display: flex; justify-content: space-between; margin-bottom: 8px; }
.form-group label .val { color: var(--accent); }
.form-group input[type=range] { width: 100%; }

.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

.shock-options { display: flex; gap: 10px; }
.shock-btn {
  flex: 1; border: 1px solid var(--border2); border-radius: 8px; padding: 12px;
  background: transparent; color: var(--text2); cursor: pointer;
  display: flex; flex-direction: column; gap: 4px; transition: all 0.15s;
}
.shock-btn.active { border-color: var(--accent); background: rgba(79,142,247,0.08); }
.shock-source { font-size: 10px; color: var(--text3); letter-spacing: 0.06em; }
.shock-label  { font-size: 13px; color: var(--text); }

.llm-toggle { margin-bottom: 24px; }
.toggle-wrap { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.toggle-track {
  position: relative; width: 32px; height: 18px;
  background: var(--border2); border-radius: 9px; transition: background 0.2s; flex-shrink: 0;
}
.toggle-wrap:has(input:checked) .toggle-track { background: var(--accent); }
.toggle-wrap input:checked ~ .toggle-track .toggle-thumb { transform: translateX(14px); }
.toggle-thumb {
  position: absolute; top: 2px; left: 2px;
  width: 14px; height: 14px; background: #fff; border-radius: 50%;
  transition: transform 0.2s;
}
.toggle-wrap input { display: none; }
.toggle-label { font-size: 13px; color: var(--text2); }
.toggle-note { font-size: 11px; color: var(--text3); margin-top: 6px; margin-left: 42px; }

.run-btn {
  width: 100%; padding: 14px; border-radius: 8px;
  background: var(--accent); color: #080c14;
  border: none; font-size: 14px; font-weight: 600; cursor: pointer;
  transition: background 0.2s;
}
.run-btn:hover { background: #6ba3fa; }
.run-btn:disabled { opacity: 0.5; cursor: default; }

/* Dashboard */
.dashboard { max-width: 900px; margin: 0 auto; }

.dash-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; }
.dash-title { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
.dash-id { font-size: 12px; color: var(--text3); }

.status-badge { font-size: 11px; padding: 4px 12px; border-radius: 5px; font-weight: 600; letter-spacing: 0.06em; }
.status-running   { background: rgba(240,168,50,0.15); color: var(--amber); }
.status-completed { background: rgba(45,212,160,0.12); color: var(--accent2); }
.status-pending   { background: var(--bg3); color: var(--text3); }

.tier-sentiment-grid { display: flex; flex-direction: column; gap: 8px; margin-bottom: 28px; }
.tier-block { display: grid; grid-template-columns: 160px 1fr 60px; align-items: center; gap: 12px; }
.tier-label { font-size: 12px; color: var(--text2); }
.sentiment-bar-wrap { height: 6px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
.sentiment-bar { height: 100%; border-radius: 3px; transition: width 0.4s; }
.sentiment-bar.positive { background: var(--accent2); }
.sentiment-bar.negative { background: #f06060; }
.sentiment-val { font-size: 12px; text-align: right; }
.pos { color: var(--accent2); }
.neg { color: #f06060; }
.dim { color: var(--text3); }
.amber { color: var(--amber); }

.disconnect-panel {
  border: 1px solid rgba(240,168,50,0.25); border-radius: 10px;
  padding: 18px 20px; background: rgba(240,168,50,0.04); margin-bottom: 24px;
}
.dp-label { font-size: 10px; color: var(--amber); letter-spacing: 0.08em; margin-bottom: 12px; }
.dp-row { display: flex; align-items: center; gap: 16px; margin-bottom: 10px; }
.dp-item { text-align: center; }
.dp-item.dp-gap { padding: 8px 16px; background: rgba(240,168,50,0.1); border-radius: 7px; }
.dp-name { font-size: 11px; color: var(--text3); margin-bottom: 4px; }
.dp-val { font-size: 18px; font-weight: 600; }
.dp-arrow { color: var(--text3); font-size: 16px; }
.dp-note { font-size: 11px; color: var(--text3); line-height: 1.5; }

.round-log { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-bottom: 24px; }
.log-title { font-size: 11px; color: var(--text3); padding: 10px 16px; background: var(--bg3); letter-spacing: 0.06em; border-bottom: 1px solid var(--border); }
.log-row { display: grid; grid-template-columns: 60px 1fr 1fr; padding: 9px 16px; font-size: 12px; border-bottom: 1px solid var(--border); }
.log-row:last-child { border-bottom: none; }
.log-header { color: var(--text3); font-size: 11px; }
.log-empty { padding: 16px; font-size: 12px; color: var(--text3); text-align: center; }
.new-btn {
  padding: 11px 24px; border-radius: 8px; border: 1px solid var(--border2);
  background: transparent; color: var(--text2); font-size: 13px; cursor: pointer; transition: all 0.15s;
}
.new-btn:hover { border-color: var(--text2); color: var(--text); }
</style>
