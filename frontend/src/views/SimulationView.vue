<template>
  <div class="sim-view">

    <!-- Pre-simulation config overlay -->
    <div v-if="!store.simId" class="config-overlay">
      <div class="config-card">
        <div class="config-title">Configure simulation</div>

        <ShockPanel v-model="selectedShock" :disabled="store.loading" />

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
          <div class="toggle-note">Off = deterministic stubs (fast). On = real language model calls.</div>
        </div>

        <button class="run-btn" :disabled="store.loading" @click="run">
          {{ store.loading ? 'Starting...' : 'Run simulation' }}
        </button>
      </div>
    </div>

    <!-- Dashboard (running / completed) -->
    <div v-else class="dashboard-grid">
      <div class="grid-left">
        <WorldGraph />
      </div>
      <div class="grid-right">
        <SimDashboard />
        <AgentFeed />
        <button class="new-btn" @click="store.reset()">New simulation</button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useSimulationStore } from '@/stores/simulation'
import ShockPanel   from '@/components/ShockPanel.vue'
import WorldGraph   from '@/components/WorldGraph.vue'
import SimDashboard from '@/components/SimDashboard.vue'
import AgentFeed    from '@/components/AgentFeed.vue'

const store = useSimulationStore()
const selectedShock = ref('fed_hike_75')

const config = reactive({
  n_households:          100,
  n_professional_retail:  20,
  n_ordinary_retail:      50,
  n_rounds:                6,
  use_llm:              false,
  seed:                    42,
})

function run() {
  store.startSimulation({
    shock_preset: selectedShock.value,
    ...config,
  })
}
</script>

<style scoped>
.sim-view { padding-top: 32px; }

/* Config overlay */
.config-overlay { display: flex; justify-content: center; }
.config-card {
  max-width: 560px; width: 100%;
  border: 1px solid var(--border); border-radius: 14px;
  padding: 28px 32px; background: var(--bg2);
  display: flex; flex-direction: column; gap: 20px;
}
.config-title { font-size: 15px; font-weight: 600; }

.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-group label {
  font-size: 10px; color: var(--text3); letter-spacing: 0.06em;
  display: flex; justify-content: space-between; margin-bottom: 6px;
}
.form-group label .val { color: var(--accent); }
.form-group input[type=range] { width: 100%; }

.llm-toggle {}
.toggle-wrap { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.toggle-track {
  position: relative; width: 30px; height: 16px;
  background: var(--border2); border-radius: 8px; transition: background 0.2s; flex-shrink: 0;
}
.toggle-wrap:has(input:checked) .toggle-track { background: var(--accent); }
.toggle-wrap input:checked ~ .toggle-track .toggle-thumb { transform: translateX(14px); }
.toggle-thumb {
  position: absolute; top: 2px; left: 2px;
  width: 12px; height: 12px; background: #fff; border-radius: 50%;
  transition: transform 0.2s;
}
.toggle-wrap input { display: none; }
.toggle-label { font-size: 12px; color: var(--text2); }
.toggle-note { font-size: 10px; color: var(--text3); margin-top: 4px; margin-left: 40px; }

.run-btn {
  width: 100%; padding: 13px; border-radius: 8px;
  background: var(--accent); color: #080c14;
  border: none; font-size: 13px; font-weight: 600; cursor: pointer;
  transition: background 0.2s;
}
.run-btn:hover { background: #6ba3fa; }
.run-btn:disabled { opacity: 0.5; cursor: default; }

/* Dashboard grid */
.dashboard-grid {
  display: grid; grid-template-columns: 2fr 1fr; gap: 20px;
  min-height: calc(100vh - 140px);
}
.grid-left { display: flex; flex-direction: column; }
.grid-right {
  display: flex; flex-direction: column; gap: 20px;
  max-height: calc(100vh - 140px); overflow-y: auto;
}
.new-btn {
  padding: 10px 20px; border-radius: 7px; border: 1px solid var(--border2);
  background: transparent; color: var(--text2); font-size: 12px;
  cursor: pointer; transition: all 0.15s; flex-shrink: 0;
}
.new-btn:hover { border-color: var(--text2); color: var(--text); }

@media (max-width: 1024px) {
  .dashboard-grid { grid-template-columns: 1fr; }
  .grid-left { min-height: 400px; }
}
</style>
