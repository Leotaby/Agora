<template>
  <div class="banking-view">
    <!-- D3 graph -->
    <div class="bv-graph" ref="graphEl">
      <svg ref="svgEl"></svg>
    </div>

    <!-- Controls (top-left overlay) -->
    <div class="bv-controls">
      <button class="bc-btn" @click="toggleAnimate" :disabled="!simData" :class="{ active: animating }">
        {{ animating ? 'Pause' : 'Animate' }}
      </button>
      <button class="bc-btn" @click="selectRound(-1)" :disabled="!simData || animating">
        Reset
      </button>
      <span class="bc-round" v-if="simData">
        {{ currentRoundLabel }}
      </span>
    </div>

    <!-- Shock info (top-center overlay) -->
    <div class="bv-shock" v-if="simData">
      <span class="bsh-label">SCENARIO</span>
      <span class="bsh-val">{{ simData.shock.description }}</span>
    </div>

    <!-- Timeline panel (right sidebar) -->
    <div class="bv-timeline" v-if="simData">
      <div class="bt-header">
        <span class="bt-title">Contagion Timeline</span>
        <span class="bt-count">{{ simData.rounds.length + 1 }} steps</span>
      </div>
      <div class="bt-list">
        <!-- Pre-shock -->
        <button
          class="bt-step"
          :class="{ active: selectedRound === -1 }"
          @click="selectRound(-1)"
        >
          <div class="bt-step-top">
            <span class="bt-num">--</span>
            <span class="bt-label">Pre-Shock</span>
          </div>
          <div class="bt-dots">
            <span
              v-for="(b, id) in simData.pre_shock.bank_states"
              :key="id"
              class="bt-dot"
              :style="{ background: statusColor(b.status) }"
              :title="b.short_name + ' ' + b.status"
            ></span>
          </div>
        </button>

        <!-- Simulation rounds -->
        <button
          v-for="round in simData.rounds"
          :key="round.round_num"
          class="bt-step"
          :class="{
            active: selectedRound === round.round_num,
            ecb: round.label === 'ECB Intervention',
          }"
          @click="selectRound(round.round_num)"
        >
          <div class="bt-step-top">
            <span class="bt-num">{{ round.round_num === 0 ? 'S' : round.label === 'ECB Intervention' ? 'E' : round.round_num }}</span>
            <span class="bt-label">{{ round.label }}</span>
            <span class="bt-loss" v-if="round.round_loss_eur_bn > 0">
              -{{ round.round_loss_eur_bn.toFixed(1) }}
            </span>
          </div>
          <div class="bt-channels">
            <span
              v-for="ch in uniqueChannels(round.events)"
              :key="ch"
              class="bt-ch"
              :class="'ch-' + ch"
            >{{ channelLabel(ch) }}</span>
          </div>
          <div class="bt-dots">
            <span
              v-for="(b, id) in round.bank_states"
              :key="id"
              class="bt-dot"
              :style="{ background: statusColor(b.status) }"
              :title="b.short_name + ' ' + b.status"
            ></span>
          </div>
        </button>
      </div>

      <!-- Event detail for selected round -->
      <div class="bt-detail" v-if="selectedRoundData && selectedRound >= 0">
        <div class="btd-header">
          {{ selectedRoundData.label }}
          <span class="btd-loss" v-if="selectedRoundData.round_loss_eur_bn > 0">
            {{ selectedRoundData.round_loss_eur_bn.toFixed(1) }}bn
          </span>
        </div>
        <div class="btd-events">
          <div
            v-for="(ev, i) in selectedRoundData.events"
            :key="i"
            class="btd-ev"
            :class="'ch-' + ev.channel"
          >
            <span class="btd-ch">{{ channelLabel(ev.channel) }}</span>
            <span class="btd-desc">{{ ev.description }}</span>
            <span class="btd-amt" v-if="ev.loss_eur_bn > 0">{{ ev.loss_eur_bn.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Metrics panel (bottom bar) -->
    <div class="bv-metrics" v-if="currentMetrics">
      <div class="bm-item">
        <span class="bm-label">Total Losses</span>
        <span class="bm-val loss">{{ (currentMetrics.cumulative_loss_eur_bn || 0).toFixed(1) }}bn</span>
      </div>
      <div class="bm-sep"></div>
      <div class="bm-item">
        <span class="bm-label">Avg CET1</span>
        <span class="bm-val" :class="cet1Class">{{ currentMetrics.avg_cet1_ratio_pct?.toFixed(1) }}%</span>
      </div>
      <div class="bm-sep"></div>
      <div class="bm-item">
        <span class="bm-label">Avg LCR</span>
        <span class="bm-val">{{ currentMetrics.avg_lcr_pct?.toFixed(0) }}%</span>
      </div>
      <div class="bm-sep"></div>
      <div class="bm-item">
        <span class="bm-label">Stressed</span>
        <span class="bm-val" :class="{ stress: currentMetrics.banks_stressed > 0 }">{{ currentMetrics.banks_stressed }}</span>
      </div>
      <div class="bm-sep"></div>
      <div class="bm-item">
        <span class="bm-label">Failed</span>
        <span class="bm-val" :class="{ fail: currentMetrics.banks_failed > 0 }">{{ currentMetrics.banks_failed }}</span>
      </div>
      <div class="bm-sep"></div>
      <div class="bm-item">
        <span class="bm-label">ECB Facility</span>
        <span class="bm-val ecb">{{ currentMetrics.ecb_facility_eur_bn?.toFixed(1) }}bn</span>
      </div>
    </div>

    <!-- Loading overlay -->
    <div class="bv-loading" v-if="loading">
      <div class="bv-spinner"></div>
      Running contagion simulation...
    </div>

    <!-- Error toast -->
    <div class="bv-error" v-if="error" @click="error = null">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as d3 from 'd3'
import axios from 'axios'

// -------------------------------------------------------------------
// State
// -------------------------------------------------------------------
const simData = ref(null)
const loading = ref(false)
const error = ref(null)
const selectedRound = ref(-1)
const animating = ref(false)

const graphEl = ref(null)
const svgEl = ref(null)

let sim = null
let resizeObserver = null
let animTimer = null
let nodeSelection = null
let nodeLabelSelection = null
let nodeMetricSelection = null
let edgeSelection = null
let ecbEdgeGroup = null

// -------------------------------------------------------------------
// Computed
// -------------------------------------------------------------------
const currentRoundLabel = computed(() => {
  if (!simData.value) return ''
  if (selectedRound.value === -1) return 'Pre-Shock'
  const r = simData.value.rounds.find(r => r.round_num === selectedRound.value)
  return r ? r.label : ''
})

const selectedRoundData = computed(() => {
  if (!simData.value || selectedRound.value < 0) return null
  return simData.value.rounds.find(r => r.round_num === selectedRound.value)
})

const currentMetrics = computed(() => {
  if (!simData.value) return null
  if (selectedRound.value === -1) return simData.value.pre_shock.metrics
  const r = selectedRoundData.value
  return r ? r.metrics : simData.value.pre_shock.metrics
})

const currentBankStates = computed(() => {
  if (!simData.value) return null
  if (selectedRound.value === -1) return simData.value.pre_shock.bank_states
  const r = selectedRoundData.value
  return r ? r.bank_states : simData.value.pre_shock.bank_states
})

const cet1Class = computed(() => {
  const v = currentMetrics.value?.avg_cet1_ratio_pct
  if (!v) return ''
  if (v < 5) return 'fail'
  if (v < 8) return 'stress'
  return ''
})

// -------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------
const STATUS_COLORS = {
  normal:     '#2dd4a0',
  stressed:   '#f0a832',
  critical:   '#f07020',
  failed:     '#f06060',
  resolution: '#f06060',
}

const CHANNEL_LABELS = {
  solvency:         'SOLV',
  liquidity:        'LIQ',
  counterparty:     'CPTY',
  fire_sale:        'FIRE',
  confidence:       'CONF',
  ecb_intervention: 'ECB',
  resolution:       'RES',
}

function statusColor(status) {
  return STATUS_COLORS[status] || '#666'
}

function channelLabel(ch) {
  return CHANNEL_LABELS[ch] || ch
}

function uniqueChannels(events) {
  return [...new Set(events.map(e => e.channel))]
}

// -------------------------------------------------------------------
// API
// -------------------------------------------------------------------
async function runSimulation() {
  loading.value = true
  error.value = null
  try {
    const res = await axios.get('/api/banking/simulate')
    simData.value = res.data
    selectedRound.value = -1
    await nextTick()
    renderGraph()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

// -------------------------------------------------------------------
// D3 Force Graph
// -------------------------------------------------------------------
function renderGraph() {
  if (!svgEl.value || !graphEl.value || !simData.value) return

  const svg = d3.select(svgEl.value)
  svg.selectAll('*').remove()
  if (sim) { sim.stop(); sim = null }

  const width = graphEl.value.clientWidth || 900
  const height = graphEl.value.clientHeight || 600

  svg.attr('viewBox', `0 0 ${width} ${height}`)
     .attr('width', width)
     .attr('height', height)

  const network = simData.value.network
  const bankStates = simData.value.pre_shock.bank_states

  // Filter to non-central-bank nodes
  const nodes = network.nodes
    .filter(n => n.type !== 'central_bank')
    .map(n => ({
      ...n,
      status: bankStates[n.id]?.status || 'normal',
      assets: bankStates[n.id]?.total_assets_eur_bn || 100,
    }))

  // Add ECB as a special fixed node
  nodes.push({
    id: 'ECB_BANK',
    name: 'ECB',
    type: 'central_bank',
    status: 'central_bank',
    assets: 500,
    fx: width / 2,
    fy: 70,
  })

  const edges = network.edges.map(e => ({ ...e }))

  // Scales
  const rScale = d3.scaleSqrt()
    .domain([200, 1800])
    .range([22, 52])
    .clamp(true)

  const edgeScale = d3.scaleLinear()
    .domain([2, 10])
    .range([1.5, 5])
    .clamp(true)

  const g = svg.append('g')

  // Zoom
  svg.call(
    d3.zoom()
      .scaleExtent([0.4, 4])
      .on('zoom', (event) => g.attr('transform', event.transform))
  )

  // Defs: arrow markers, glow filter
  const defs = svg.append('defs')

  defs.append('marker')
    .attr('id', 'bv-arrow')
    .attr('viewBox', '0 -4 8 8')
    .attr('refX', 12).attr('refY', 0)
    .attr('markerWidth', 5).attr('markerHeight', 5)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-3L8,0L0,3')
    .attr('fill', 'rgba(255,255,255,0.25)')

  defs.append('marker')
    .attr('id', 'bv-arrow-red')
    .attr('viewBox', '0 -4 8 8')
    .attr('refX', 12).attr('refY', 0)
    .attr('markerWidth', 5).attr('markerHeight', 5)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-3L8,0L0,3')
    .attr('fill', '#f06060')

  defs.append('marker')
    .attr('id', 'bv-arrow-ecb')
    .attr('viewBox', '0 -4 8 8')
    .attr('refX', 12).attr('refY', 0)
    .attr('markerWidth', 5).attr('markerHeight', 5)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-3L8,0L0,3')
    .attr('fill', '#4f8ef7')

  const glowFilter = defs.append('filter').attr('id', 'bv-glow')
  glowFilter.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'blur')
  glowFilter.append('feMerge').selectAll('feMergeNode')
    .data(['blur', 'SourceGraphic'])
    .join('feMergeNode')
    .attr('in', d => d)

  const redGlow = defs.append('filter').attr('id', 'bv-red-glow')
  redGlow.append('feDropShadow')
    .attr('dx', 0).attr('dy', 0)
    .attr('stdDeviation', 6)
    .attr('flood-color', '#f06060')
    .attr('flood-opacity', 0.7)

  // Edges
  edgeSelection = g.append('g').attr('class', 'edges')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', 'rgba(255,255,255,0.12)')
    .attr('stroke-width', d => edgeScale(d.amount_eur_bn))
    .attr('stroke-opacity', 0.5)
    .attr('marker-end', 'url(#bv-arrow)')

  // ECB intervention edges group (drawn dynamically)
  ecbEdgeGroup = g.append('g').attr('class', 'ecb-edges')

  // Node circles
  nodeSelection = g.append('g').attr('class', 'nodes')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', d => d.type === 'central_bank' ? 30 : rScale(d.assets))
    .attr('fill', d => d.type === 'central_bank' ? '#4f8ef7' : statusColor(d.status))
    .attr('stroke', d => d.type === 'central_bank' ? 'rgba(79,142,247,0.4)' : 'rgba(255,255,255,0.15)')
    .attr('stroke-width', d => d.type === 'central_bank' ? 3 : 1.5)
    .style('cursor', 'grab')

  // Bank name labels
  nodeLabelSelection = g.append('g').attr('class', 'labels')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text(d => d.name)
    .attr('font-size', d => d.type === 'central_bank' ? 12 : 11)
    .attr('font-weight', d => d.type === 'central_bank' ? 700 : 500)
    .attr('fill', '#e8eaf0')
    .attr('text-anchor', 'middle')
    .attr('dy', d => {
      const r = d.type === 'central_bank' ? 30 : rScale(d.assets)
      return r + 16
    })
    .style('pointer-events', 'none')

  // Metric labels below name (CET1 %)
  nodeMetricSelection = g.append('g').attr('class', 'metrics')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text(d => {
      if (d.type === 'central_bank') return 'Lender of Last Resort'
      const bs = bankStates[d.id]
      return bs ? `CET1 ${bs.cet1_ratio_pct.toFixed(1)}%  LCR ${bs.lcr_pct.toFixed(0)}%` : ''
    })
    .attr('font-size', 9)
    .attr('fill', '#8b90a0')
    .attr('text-anchor', 'middle')
    .attr('dy', d => {
      const r = d.type === 'central_bank' ? 30 : rScale(d.assets)
      return r + 28
    })
    .style('pointer-events', 'none')

  // Drag
  function dragStart(event, d) {
    if (!event.active) sim.alphaTarget(0.3).restart()
    d.fx = d.x; d.fy = d.y
  }
  function dragging(event, d) { d.fx = event.x; d.fy = event.y }
  function dragEnd(event, d) {
    if (!event.active) sim.alphaTarget(0)
    if (d.type !== 'central_bank') { d.fx = null; d.fy = null }
  }
  nodeSelection.call(d3.drag().on('start', dragStart).on('drag', dragging).on('end', dragEnd))

  // Tooltips
  nodeSelection.append('title').text(d => {
    if (d.type === 'central_bank') return 'European Central Bank\nLender of Last Resort'
    const bs = bankStates[d.id]
    if (!bs) return d.name
    return `${bs.name}\nAssets: €${bs.total_assets_eur_bn}bn\nCET1: ${bs.cet1_ratio_pct}%\nLCR: ${bs.lcr_pct}%\nStatus: ${bs.status}`
  })

  // Force simulation
  sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(180).strength(0.3))
    .force('charge', d3.forceManyBody().strength(-800))
    .force('center', d3.forceCenter(width / 2, height / 2 + 30))
    .force('collide', d3.forceCollide().radius(d => {
      const r = d.type === 'central_bank' ? 30 : rScale(d.assets)
      return r + 20
    }))
    .force('y', d3.forceY(height / 2 + 40).strength(0.05))
    .on('tick', () => {
      edgeSelection
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      nodeSelection
        .attr('cx', d => d.x).attr('cy', d => d.y)
      nodeLabelSelection
        .attr('x', d => d.x).attr('y', d => d.y)
      nodeMetricSelection
        .attr('x', d => d.x).attr('y', d => d.y)
      // Update ECB edges
      ecbEdgeGroup.selectAll('line')
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    })
}

// -------------------------------------------------------------------
// Update graph for selected round
// -------------------------------------------------------------------
function updateGraphForRound() {
  if (!simData.value || !nodeSelection) return

  const states = currentBankStates.value
  if (!states) return

  const roundData = selectedRoundData.value
  const affectedBanks = roundData?.affected_banks || []
  const activeEdges = roundData?.active_edges || []
  const isECB = roundData?.label === 'ECB Intervention'

  // Update node colors with transition
  nodeSelection
    .transition().duration(400)
    .attr('fill', d => {
      if (d.type === 'central_bank') {
        return isECB ? '#2dd4a0' : '#4f8ef7'
      }
      return statusColor(states[d.id]?.status || 'normal')
    })
    .attr('stroke', d => {
      if (d.type === 'central_bank') return isECB ? 'rgba(45,212,160,0.5)' : 'rgba(79,142,247,0.4)'
      if (affectedBanks.includes(d.id)) return '#fff'
      return 'rgba(255,255,255,0.15)'
    })
    .attr('stroke-width', d => {
      if (d.type === 'central_bank') return 3
      if (affectedBanks.includes(d.id)) return 3
      return 1.5
    })

  // Pulse affected nodes
  if (affectedBanks.length && selectedRound.value >= 0) {
    nodeSelection
      .filter(d => affectedBanks.includes(d.id))
      .attr('filter', 'url(#bv-glow)')
      .transition().delay(400).duration(600)
      .attr('filter', null)
  }

  // Update edge colors (red for contagion)
  edgeSelection
    .transition().duration(300)
    .attr('stroke', d => {
      const match = activeEdges.some(ae =>
        (ae.source === d.source.id && ae.target === d.target.id) ||
        (ae.source === d.target.id && ae.target === d.source.id)
      )
      return match ? '#f06060' : 'rgba(255,255,255,0.12)'
    })
    .attr('stroke-opacity', d => {
      const match = activeEdges.some(ae =>
        (ae.source === d.source.id && ae.target === d.target.id) ||
        (ae.source === d.target.id && ae.target === d.source.id)
      )
      return match ? 0.9 : 0.5
    })
    .attr('marker-end', d => {
      const match = activeEdges.some(ae =>
        (ae.source === d.source.id && ae.target === d.target.id) ||
        (ae.source === d.target.id && ae.target === d.source.id)
      )
      return match ? 'url(#bv-arrow-red)' : 'url(#bv-arrow)'
    })

  // ECB intervention: draw dashed lines from ECB to each bank receiving ELA
  ecbEdgeGroup.selectAll('line').remove()
  if (isECB && roundData?.events) {
    const ecbTargets = roundData.events
      .filter(e => e.channel === 'ecb_intervention')
      .map(e => e.target_bank_id)

    const ecbNode = nodeSelection.data().find(n => n.id === 'ECB_BANK')
    if (ecbNode) {
      const targetNodes = nodeSelection.data().filter(n => ecbTargets.includes(n.id))
      ecbEdgeGroup.selectAll('line')
        .data(targetNodes)
        .join('line')
        .attr('x1', ecbNode.x).attr('y1', ecbNode.y)
        .attr('x2', d => d.x).attr('y2', d => d.y)
        .attr('stroke', '#4f8ef7')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '6,4')
        .attr('stroke-opacity', 0)
        .attr('marker-end', 'url(#bv-arrow-ecb)')
        .each(function(d) { d.source = ecbNode; d.target = d })
        .transition().duration(500)
        .attr('stroke-opacity', 0.8)
    }
  }

  // Update metric labels
  nodeMetricSelection
    .text(d => {
      if (d.type === 'central_bank') return 'Lender of Last Resort'
      const bs = states[d.id]
      return bs ? `CET1 ${bs.cet1_ratio_pct.toFixed(1)}%  LCR ${bs.lcr_pct.toFixed(0)}%` : ''
    })
}

// -------------------------------------------------------------------
// Round selection
// -------------------------------------------------------------------
function selectRound(roundNum) {
  selectedRound.value = roundNum
}

watch(selectedRound, () => {
  nextTick(updateGraphForRound)
})

// -------------------------------------------------------------------
// Animation
// -------------------------------------------------------------------
function toggleAnimate() {
  if (animating.value) {
    stopAnimate()
  } else {
    startAnimate()
  }
}

function startAnimate() {
  if (!simData.value) return
  animating.value = true
  selectedRound.value = -1

  let stepIndex = 0
  const allSteps = [-1, ...simData.value.rounds.map(r => r.round_num)]

  animTimer = setInterval(() => {
    if (stepIndex >= allSteps.length) {
      stopAnimate()
      return
    }
    selectedRound.value = allSteps[stepIndex]
    stepIndex++
  }, 1000)
}

function stopAnimate() {
  animating.value = false
  if (animTimer) {
    clearInterval(animTimer)
    animTimer = null
  }
}

// -------------------------------------------------------------------
// Lifecycle
// -------------------------------------------------------------------
onMounted(async () => {
  await runSimulation()

  resizeObserver = new ResizeObserver(() => {
    if (simData.value) renderGraph()
  })
  if (graphEl.value) resizeObserver.observe(graphEl.value)
})

onBeforeUnmount(() => {
  stopAnimate()
  if (sim) sim.stop()
  if (resizeObserver) resizeObserver.disconnect()
})
</script>

<style scoped>
.banking-view {
  position: fixed;
  top: 56px;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  background: var(--bg);
  z-index: 5;
}

/* ── D3 graph ── */
.bv-graph {
  position: absolute;
  top: 0;
  left: 0;
  right: 340px;
  bottom: 56px;
}
.bv-graph svg { display: block; width: 100%; height: 100%; }

/* ── Controls (top-left) ── */
.bv-controls {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 10;
}

.bc-btn {
  font-family: inherit;
  font-size: 11px;
  padding: 7px 14px;
  border: 1px solid var(--border2);
  border-radius: 6px;
  background: rgba(8,12,20,0.85);
  backdrop-filter: blur(8px);
  color: var(--text2);
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: 0.02em;
}
.bc-btn:hover:not(:disabled) { color: var(--text); border-color: var(--accent); }
.bc-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.bc-btn.active {
  border-color: var(--amber);
  color: var(--amber);
  background: rgba(240,168,50,0.1);
}

.bc-round {
  font-size: 11px;
  color: var(--text);
  background: rgba(8,12,20,0.85);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 14px;
  font-weight: 600;
}

/* ── Shock info (top-center) ── */
.bv-shock {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(8,12,20,0.85);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  z-index: 10;
}
.bsh-label {
  font-size: 9px;
  color: var(--text3);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.bsh-val {
  font-size: 11px;
  color: var(--text);
  font-weight: 500;
}

/* ── Timeline (right sidebar) ── */
.bv-timeline {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 56px;
  width: 340px;
  background: rgba(8,12,20,0.92);
  backdrop-filter: blur(12px);
  border-left: 1px solid var(--border);
  z-index: 10;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.bt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  flex-shrink: 0;
}
.bt-title {
  font-size: 10px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.bt-count {
  font-size: 10px;
  color: var(--text3);
  background: rgba(255,255,255,0.05);
  padding: 1px 6px;
  border-radius: 3px;
}

.bt-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 8px;
  min-height: 0;
}

/* Timeline step button */
.bt-step {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text2);
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  text-align: left;
  transition: all 0.12s;
  flex-shrink: 0;
}
.bt-step:hover { background: rgba(255,255,255,0.03); }
.bt-step.active {
  background: rgba(79,142,247,0.08);
  border-color: var(--accent);
}
.bt-step.ecb.active {
  background: rgba(79,142,247,0.12);
  border-color: var(--accent);
}

.bt-step-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bt-num {
  font-size: 9px;
  font-weight: 700;
  color: var(--text3);
  background: rgba(255,255,255,0.05);
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  flex-shrink: 0;
}
.bt-step.active .bt-num {
  background: var(--accent);
  color: #080c14;
}
.bt-label { flex: 1; font-size: 11px; }
.bt-loss {
  font-size: 10px;
  color: #f06060;
  font-weight: 600;
}

.bt-channels {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  padding-left: 26px;
}
.bt-ch {
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.04em;
  font-weight: 600;
}
.bt-ch.ch-solvency         { background: rgba(240,96,96,0.15); color: #f06060; }
.bt-ch.ch-liquidity         { background: rgba(240,168,50,0.15); color: #f0a832; }
.bt-ch.ch-counterparty      { background: rgba(240,96,96,0.15); color: #f06060; }
.bt-ch.ch-fire_sale         { background: rgba(240,112,32,0.15); color: #f07020; }
.bt-ch.ch-confidence        { background: rgba(79,142,247,0.15); color: #4f8ef7; }
.bt-ch.ch-ecb_intervention  { background: rgba(45,212,160,0.15); color: #2dd4a0; }
.bt-ch.ch-resolution        { background: rgba(240,96,96,0.2); color: #f06060; }

.bt-dots {
  display: flex;
  gap: 4px;
  padding-left: 26px;
}
.bt-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* ── Event detail (bottom of timeline) ── */
.bt-detail {
  flex-shrink: 0;
  max-height: 40%;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.btd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px 6px;
  font-size: 10px;
  color: var(--text);
  font-weight: 600;
  flex-shrink: 0;
}
.btd-loss { color: #f06060; font-weight: 700; }

.btd-events {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.btd-ev {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 10px;
  line-height: 1.3;
}
.btd-ev.ch-solvency,
.btd-ev.ch-counterparty { background: rgba(240,96,96,0.06); }
.btd-ev.ch-liquidity     { background: rgba(240,168,50,0.06); }
.btd-ev.ch-fire_sale     { background: rgba(240,112,32,0.06); }
.btd-ev.ch-confidence    { background: rgba(79,142,247,0.06); }
.btd-ev.ch-ecb_intervention { background: rgba(45,212,160,0.06); }
.btd-ev.ch-resolution    { background: rgba(240,96,96,0.08); }

.btd-ch {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text3);
  flex-shrink: 0;
  width: 32px;
}
.btd-desc {
  flex: 1;
  color: var(--text2);
}
.btd-amt {
  font-size: 9px;
  color: #f06060;
  font-weight: 600;
  flex-shrink: 0;
}

/* ── Metrics bar (bottom) ── */
.bv-metrics {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: rgba(8,12,20,0.92);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 0 32px;
  z-index: 10;
}

.bm-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 0 24px;
}
.bm-label {
  font-size: 9px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.bm-val {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  transition: color 0.3s;
}
.bm-val.loss { color: #f06060; }
.bm-val.stress { color: #f0a832; }
.bm-val.fail { color: #f06060; }
.bm-val.ecb { color: #4f8ef7; }

.bm-sep {
  width: 1px;
  height: 28px;
  background: var(--border);
}

/* ── Loading ── */
.bv-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgba(8,12,20,0.8);
  font-size: 13px;
  color: var(--text2);
  z-index: 30;
}

.bv-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: bv-spin 0.8s linear infinite;
}
@keyframes bv-spin {
  to { transform: rotate(360deg); }
}

/* ── Error ── */
.bv-error {
  position: absolute;
  bottom: 72px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(240,96,96,0.15);
  border: 1px solid rgba(240,96,96,0.4);
  color: #f06060;
  font-size: 11px;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  z-index: 30;
}

@media (max-width: 1100px) {
  .bv-graph { right: 280px; }
  .bv-timeline { width: 280px; }
  .bm-item { padding: 0 14px; }
}
</style>
