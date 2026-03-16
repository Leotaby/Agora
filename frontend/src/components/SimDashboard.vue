<template>
  <div class="sim-dash">
    <!-- Header -->
    <div class="sd-header" v-if="store.simId">
      <div class="sd-id">{{ store.simId.slice(0, 8) }}...</div>
      <div class="status-badge" :class="'st-' + store.status">{{ store.status }}</div>
    </div>
    <div class="sd-headline" v-if="store.shockHeadline">{{ store.shockHeadline }}</div>

    <!-- Round progress -->
    <div class="progress-section" v-if="store.simId">
      <div class="prog-label">
        Round {{ store.roundResults.length }} / {{ store.numRounds }}
      </div>
      <div class="prog-bar-wrap">
        <div class="prog-bar" :style="{ width: (store.roundProgress * 100) + '%' }"></div>
      </div>
    </div>

    <!-- Per-agent spinner (visible during LLM processing) -->
    <div class="agent-spinner" v-if="store.agentProgress">
      <div class="sp-row">
        <div class="sp-dot"></div>
        <div class="sp-text">
          Processing agents {{ store.agentProgress.agents_done }} / {{ store.agentProgress.agents_total }}
        </div>
      </div>
      <div class="sp-bar-wrap">
        <div class="sp-bar" :style="{ width: agentPct + '%' }"></div>
      </div>
      <div class="sp-detail">
        <span>Round {{ store.agentProgress.round_num }}</span>
        <span v-if="store.agentProgress.agents_failed > 0" class="sp-fail">
          {{ store.agentProgress.agents_failed }} failed
        </span>
      </div>
    </div>

    <!-- Pending spinner (no progress data yet) -->
    <div class="agent-spinner" v-else-if="store.status === 'pending'">
      <div class="sp-row">
        <div class="sp-dot"></div>
        <div class="sp-text">Initializing agents...</div>
      </div>
    </div>

    <!-- Agent counts by tier -->
    <div class="agent-counts" v-if="store.simId">
      <div class="ac-title">Agents: {{ store.numAgents }}</div>
    </div>

    <!-- Tier sentiments -->
    <div class="tier-list">
      <div class="tier-row" v-for="t in tiersDisplay" :key="t.id">
        <div class="tier-dot" :style="{ background: t.color }"></div>
        <div class="tier-name">{{ t.short }}</div>
        <div class="tier-bar-wrap">
          <div
            class="tier-bar"
            :class="t.val >= 0 ? 'pos' : 'neg'"
            :style="{ width: Math.min(Math.abs(t.val) * 100, 100) + '%' }"
          ></div>
        </div>
        <div class="tier-val" :class="t.val >= 0 ? 'pos' : 'neg'">
          {{ t.val >= 0 ? '+' : '' }}{{ t.val.toFixed(3) }}
        </div>
      </div>
    </div>

    <!-- Disconnect gap -->
    <div class="disconnect" v-if="store.disconnectGap !== null">
      <div class="dc-label">MEESE-ROGOFF DISCONNECT</div>
      <div class="dc-row">
        <div class="dc-item">
          <div class="dc-name">HF (t=0)</div>
          <div class="dc-val pos">{{ hfVal.toFixed(3) }}</div>
        </div>
        <div class="dc-arrow">&rarr;</div>
        <div class="dc-item">
          <div class="dc-name">HH (now)</div>
          <div class="dc-val" :class="hhVal > 0.05 ? 'pos' : 'dim'">{{ hhVal.toFixed(3) }}</div>
        </div>
        <div class="dc-arrow">&rarr;</div>
        <div class="dc-item dc-gap">
          <div class="dc-name">Gap</div>
          <div class="dc-val amber">{{ store.disconnectGap.toFixed(3) }}</div>
        </div>
      </div>
    </div>

    <!-- Error display -->
    <div class="error-panel" v-if="store.error">
      <div class="err-title">Simulation error</div>
      <div class="err-msg">{{ store.error }}</div>
    </div>

    <div class="error-panel warn" v-if="store.simErrors.length > 0 && !store.error">
      <div class="err-title">Agent errors ({{ store.simErrors.length }})</div>
      <div class="err-item" v-for="(e, i) in store.simErrors.slice(-5)" :key="i">
        <span class="err-agent">{{ e.agent }}</span>
        <span class="err-tier">{{ tierShort(e.tier) }}</span>
        <span class="err-detail">{{ e.error }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSimulationStore } from '@/stores/simulation'

const store = useSimulationStore()

const TIERS = [
  { id: 'T1_central_bank',        short: 'Central banks',   color: '#4f8ef7' },
  { id: 'T2_macro_hedge_fund',    short: 'Macro HF',        color: '#6ba3fa' },
  { id: 'T3_commercial_bank',     short: 'Comm. banks',     color: '#9b7ff4' },
  { id: 'T4_institutional_am',    short: 'Inst. AM',        color: '#b794f6' },
  { id: 'T5_professional_retail', short: 'Pro retail',      color: '#2dd4a0' },
  { id: 'T6_ordinary_retail',     short: 'Ordinary retail', color: '#f0a832' },
  { id: 'T7_household',           short: 'Households',      color: '#f06060' },
]

const TIER_SHORT = {
  T1_central_bank: 'CB', T2_macro_hedge_fund: 'HF', T3_commercial_bank: 'BK',
  T4_institutional_am: 'AM', T5_professional_retail: 'PR',
  T6_ordinary_retail: 'OR', T7_household: 'HH',
}
function tierShort(tier) { return TIER_SHORT[tier] || tier.slice(0, 2) }

const tiersDisplay = computed(() => {
  const latest = store.latestRound
  return TIERS.map(t => ({
    ...t,
    val: latest?.sentiment_by_tier?.[t.id] ?? 0,
  }))
})

const agentPct = computed(() => {
  const p = store.agentProgress
  if (!p || !p.agents_total) return 0
  return Math.round((p.agents_done / p.agents_total) * 100)
})

const hfVal = computed(() => {
  const first = store.roundResults[0]
  return first?.sentiment_by_tier?.T2_macro_hedge_fund ?? 0
})
const hhVal = computed(() => store.latestRound?.sentiment_by_tier?.T7_household ?? 0)
</script>

<style scoped>
.sim-dash { display: flex; flex-direction: column; gap: 16px; }

.sd-header { display: flex; justify-content: space-between; align-items: center; }
.sd-id { font-size: 11px; color: var(--text3); }
.sd-headline { font-size: 12px; color: var(--text2); line-height: 1.4; }

.status-badge {
  font-size: 10px; padding: 3px 10px; border-radius: 4px;
  font-weight: 600; letter-spacing: 0.06em;
}
.st-running   { background: rgba(240,168,50,0.15); color: var(--amber); }
.st-completed { background: rgba(45,212,160,0.12); color: var(--accent2); }
.st-pending   { background: var(--bg3); color: var(--text3); }
.st-idle      { background: var(--bg3); color: var(--text3); }
.st-failed    { background: rgba(240,96,96,0.12); color: #f06060; }

.progress-section { display: flex; flex-direction: column; gap: 6px; }
.prog-label { font-size: 11px; color: var(--text3); }
.prog-bar-wrap { height: 4px; background: var(--bg3); border-radius: 2px; overflow: hidden; }
.prog-bar { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.4s; }

/* Agent spinner */
.agent-spinner {
  border: 1px solid var(--border); border-radius: 8px;
  padding: 12px 14px; background: var(--bg3);
}
.sp-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.sp-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--amber);
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}
.sp-text { font-size: 11px; color: var(--text2); }
.sp-bar-wrap { height: 3px; background: var(--bg); border-radius: 2px; overflow: hidden; margin-bottom: 6px; }
.sp-bar {
  height: 100%; background: var(--amber); border-radius: 2px;
  transition: width 0.3s;
}
.sp-detail { display: flex; justify-content: space-between; font-size: 10px; color: var(--text3); }
.sp-fail { color: #f06060; }

.ac-title { font-size: 11px; color: var(--text3); }

.tier-list { display: flex; flex-direction: column; gap: 6px; }
.tier-row { display: grid; grid-template-columns: 10px 100px 1fr 54px; align-items: center; gap: 8px; }
.tier-dot { width: 8px; height: 8px; border-radius: 50%; }
.tier-name { font-size: 11px; color: var(--text2); }
.tier-bar-wrap { height: 5px; background: var(--bg3); border-radius: 2px; overflow: hidden; }
.tier-bar { height: 100%; border-radius: 2px; transition: width 0.4s; }
.tier-bar.pos { background: var(--accent2); }
.tier-bar.neg { background: #f06060; }
.tier-val { font-size: 11px; text-align: right; }
.pos { color: var(--accent2); }
.neg { color: #f06060; }
.dim { color: var(--text3); }
.amber { color: var(--amber); }

.disconnect {
  border: 1px solid rgba(240,168,50,0.25); border-radius: 8px;
  padding: 14px 16px; background: rgba(240,168,50,0.04);
}
.dc-label { font-size: 9px; color: var(--amber); letter-spacing: 0.08em; margin-bottom: 10px; }
.dc-row { display: flex; align-items: center; gap: 12px; }
.dc-item { text-align: center; }
.dc-item.dc-gap { padding: 6px 12px; background: rgba(240,168,50,0.1); border-radius: 6px; }
.dc-name { font-size: 10px; color: var(--text3); margin-bottom: 2px; }
.dc-val { font-size: 16px; font-weight: 600; }
.dc-arrow { color: var(--text3); font-size: 14px; }

/* Error panels */
.error-panel {
  border: 1px solid rgba(240,96,96,0.3); border-radius: 8px;
  padding: 12px 14px; background: rgba(240,96,96,0.06);
}
.error-panel.warn {
  border-color: rgba(240,168,50,0.3); background: rgba(240,168,50,0.04);
}
.err-title {
  font-size: 10px; font-weight: 600; letter-spacing: 0.06em;
  color: #f06060; margin-bottom: 8px;
}
.error-panel.warn .err-title { color: var(--amber); }
.err-msg { font-size: 11px; color: var(--text2); line-height: 1.4; word-break: break-word; }
.err-item {
  display: flex; align-items: baseline; gap: 6px;
  font-size: 10px; color: var(--text2); padding: 3px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.err-item:last-child { border-bottom: none; }
.err-agent { color: var(--text); font-weight: 500; }
.err-tier {
  font-size: 9px; background: var(--bg3); padding: 1px 5px;
  border-radius: 3px; color: var(--text3);
}
.err-detail {
  flex: 1; color: var(--text3); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
</style>
