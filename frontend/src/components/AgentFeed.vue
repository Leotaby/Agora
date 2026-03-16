<template>
  <div class="agent-feed">
    <div class="af-title">Agent reactions</div>
    <div class="af-list" ref="listEl">
      <TransitionGroup name="feed">
        <div class="af-card" v-for="r in store.agentReactions" :key="r.key">
          <div class="af-top">
            <span class="af-tier" :style="{ background: tierColor(r.tier) }">{{ tierShort(r.tier) }}</span>
            <span class="af-country">{{ flag(r.country) }} {{ r.country }}</span>
            <span class="af-round">R{{ r.round_num }}</span>
          </div>
          <div class="af-action">{{ r.action }}</div>
          <div class="af-sentiment" :class="r.sentiment >= 0 ? 'pos' : 'neg'">
            {{ r.sentiment >= 0 ? '+' : '' }}{{ r.sentiment.toFixed(3) }}
          </div>
        </div>
      </TransitionGroup>
      <div class="af-empty" v-if="store.agentReactions.length === 0">
        Waiting for agent reactions...
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useSimulationStore } from '@/stores/simulation'

const store = useSimulationStore()
const listEl = ref(null)

const TIER_COLORS = {
  T1_central_bank:        '#4f8ef7',
  T2_macro_hedge_fund:    '#6ba3fa',
  T3_commercial_bank:     '#9b7ff4',
  T4_institutional_am:    '#b794f6',
  T5_professional_retail: '#2dd4a0',
  T6_ordinary_retail:     '#f0a832',
  T7_household:           '#f06060',
}
const TIER_SHORT = {
  T1_central_bank:        'CB',
  T2_macro_hedge_fund:    'HF',
  T3_commercial_bank:     'BK',
  T4_institutional_am:    'AM',
  T5_professional_retail: 'PR',
  T6_ordinary_retail:     'OR',
  T7_household:           'HH',
}

function tierColor(tier) { return TIER_COLORS[tier] || '#666' }
function tierShort(tier) { return TIER_SHORT[tier] || tier.slice(0, 2) }

function flag(iso2) {
  if (!iso2 || iso2.length !== 2) return ''
  return String.fromCodePoint(
    ...iso2.toUpperCase().split('').map(c => 0x1F1E6 + c.charCodeAt(0) - 65)
  )
}

watch(() => store.agentReactions.length, async () => {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
})
</script>

<style scoped>
.agent-feed { display: flex; flex-direction: column; gap: 8px; min-height: 0; }
.af-title {
  font-size: 10px; color: var(--text3); letter-spacing: 0.08em;
  text-transform: uppercase; flex-shrink: 0;
}
.af-list {
  display: flex; flex-direction: column; gap: 6px;
  overflow-y: auto; max-height: 320px;
}
.af-card {
  border: 1px solid var(--border); border-radius: 7px; padding: 10px 12px;
  background: var(--bg2);
}
.af-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.af-tier {
  font-size: 9px; font-weight: 700; color: #080c14; padding: 2px 6px;
  border-radius: 3px; letter-spacing: 0.06em;
}
.af-country { font-size: 11px; color: var(--text2); }
.af-round { font-size: 10px; color: var(--text3); margin-left: auto; }
.af-action { font-size: 11px; color: var(--text); line-height: 1.4; margin-bottom: 4px; }
.af-sentiment { font-size: 12px; font-weight: 600; }
.pos { color: var(--accent2); }
.neg { color: #f06060; }
.af-empty { font-size: 11px; color: var(--text3); text-align: center; padding: 20px 0; }

.feed-enter-active { transition: all 0.3s ease; }
.feed-enter-from { opacity: 0; transform: translateY(-10px); }
.feed-leave-active { transition: all 0.2s ease; }
.feed-leave-to { opacity: 0; transform: translateX(10px); }
</style>
