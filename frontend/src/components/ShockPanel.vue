<template>
  <div class="shock-panel">
    <div class="sp-title">Macro shock</div>
    <div class="shock-grid">
      <button
        v-for="s in shocks"
        :key="s.id"
        class="shock-btn"
        :class="{ active: modelValue === s.id, disabled: disabled }"
        :disabled="disabled"
        @click="$emit('update:modelValue', s.id)"
      >
        <span class="shock-source">{{ s.source }}</span>
        <span class="shock-label">{{ s.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: 'fed_hike_75' },
  disabled:   { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])

const shocks = [
  { id: 'fed_hike_75',     source: 'Fed',         label: '+75bps rate hike' },
  { id: 'ecb_cut_50',      source: 'ECB',         label: '-50bps surprise cut' },
  { id: 'russia_sanction', source: 'Geopolitical', label: 'Russia sanctions' },
  { id: 'nk_cyber',        source: 'Market',       label: 'NK cyber attack' },
]
</script>

<style scoped>
.sp-title {
  font-size: 10px; color: var(--text3); letter-spacing: 0.08em;
  text-transform: uppercase; margin-bottom: 10px;
}
.shock-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.shock-btn {
  border: 1px solid var(--border2); border-radius: 8px; padding: 10px 12px;
  background: transparent; color: var(--text2); cursor: pointer;
  display: flex; flex-direction: column; gap: 3px; transition: all 0.15s;
  text-align: left;
}
.shock-btn:hover:not(.disabled) { border-color: var(--text3); }
.shock-btn.active { border-color: var(--accent); background: rgba(79,142,247,0.08); }
.shock-btn.disabled { opacity: 0.4; cursor: default; }
.shock-source { font-size: 9px; color: var(--text3); letter-spacing: 0.06em; }
.shock-label  { font-size: 12px; color: var(--text); }
</style>
