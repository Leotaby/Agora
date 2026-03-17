<template>
  <div class="world-view" ref="rootEl">
    <!-- Full-screen D3 force graph -->
    <div class="wv-graph" ref="graphEl">
      <svg ref="svgEl"></svg>
    </div>

    <!-- Status bar (top-left overlay) -->
    <div class="wv-status">
      <div class="ws-row">
        <span class="ws-label">TICK</span>
        <span class="ws-val">{{ store.tick }}</span>
      </div>
      <div class="ws-row">
        <span class="ws-label">DATE</span>
        <span class="ws-val">{{ store.simulationDate || '—' }}</span>
      </div>
      <div class="ws-row">
        <span class="ws-label">STATE</span>
        <span class="ws-badge" :class="stateBadge">{{ stateLabel }}</span>
      </div>
      <div class="ws-row" v-if="store.macro">
        <span class="ws-label">VIX</span>
        <span class="ws-val">{{ store.macro.vix?.toFixed(1) }}</span>
      </div>
      <div class="ws-row" v-if="store.macro">
        <span class="ws-label">OIL</span>
        <span class="ws-val">${{ store.macro.oil_price_brent?.toFixed(0) }}</span>
      </div>
    </div>

    <!-- Controls (bottom-left overlay) -->
    <div class="wv-controls">
      <button class="wc-btn" @click="handleInit" :disabled="store.loading">
        {{ store.initialized ? 'Re-init' : 'Init World' }}
      </button>
      <button class="wc-btn" @click="store.manualTick()" :disabled="!store.initialized || store.running">
        Tick
      </button>
      <button class="wc-btn" :class="{ active: store.autoTick }" @click="store.toggleAutoTick()" :disabled="!store.initialized || store.running">
        Auto {{ store.autoTick ? 'ON' : 'OFF' }}
      </button>
      <button class="wc-btn" @click="toggleEngine" :disabled="!store.initialized">
        {{ store.running ? 'Stop' : 'Start' }}
      </button>
    </div>

    <!-- Right sidebar: Event Feed + Intervention -->
    <div class="wv-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <button class="ws-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
        {{ sidebarCollapsed ? '◂' : '▸' }}
      </button>

      <template v-if="!sidebarCollapsed">
        <!-- Event Feed -->
        <div class="wv-feed">
          <div class="wf-header">
            <span class="wf-title">Event Feed</span>
            <span class="wf-count">{{ store.events.length }}</span>
          </div>
          <div class="wf-list" ref="feedEl">
            <TransitionGroup name="ev">
              <div
                class="wf-card"
                v-for="ev in displayEvents"
                :key="ev.event_id"
                :class="'sev-' + ev.severity"
              >
                <div class="wf-top">
                  <span class="wf-type">{{ formatType(ev.event_type) }}</span>
                  <span class="wf-tick">t{{ ev.tick }}</span>
                </div>
                <div class="wf-headline">{{ ev.headline }}</div>
                <div class="wf-desc" v-if="ev.description">{{ ev.description }}</div>
                <div class="wf-actor" v-if="ev.actor_id">
                  {{ ev.actor_type }}: {{ ev.actor_id }}
                </div>
              </div>
            </TransitionGroup>
            <div class="wf-empty" v-if="store.events.length === 0">
              No events yet. Initialize the world to begin.
            </div>
          </div>
        </div>

        <!-- Intervention Panel -->
        <div class="wv-intervene">
          <div class="wi-title">Agent Intervention</div>
          <div class="wi-form">
            <input v-model="intv.agentId" placeholder="Agent ID" class="wi-input" />
            <input v-model="intv.action" placeholder="Action description" class="wi-input" />
            <div class="wi-sliders">
              <label class="wi-slider">
                <span>USD</span>
                <input type="range" v-model.number="intv.usdDelta" min="-1" max="1" step="0.1" />
                <span class="wi-sv">{{ intv.usdDelta.toFixed(1) }}</span>
              </label>
              <label class="wi-slider">
                <span>EUR</span>
                <input type="range" v-model.number="intv.eurDelta" min="-1" max="1" step="0.1" />
                <span class="wi-sv">{{ intv.eurDelta.toFixed(1) }}</span>
              </label>
              <label class="wi-slider">
                <span>EQ</span>
                <input type="range" v-model.number="intv.eqDelta" min="-1" max="1" step="0.1" />
                <span class="wi-sv">{{ intv.eqDelta.toFixed(1) }}</span>
              </label>
              <label class="wi-slider">
                <span>BTC</span>
                <input type="range" v-model.number="intv.cryptoDelta" min="-1" max="1" step="0.1" />
                <span class="wi-sv">{{ intv.cryptoDelta.toFixed(1) }}</span>
              </label>
            </div>
            <button class="wc-btn accent" @click="submitIntervention" :disabled="!intv.agentId || !intv.action">
              Inject
            </button>
            <div class="wi-result" v-if="intvResult">{{ intvResult }}</div>
          </div>

          <!-- Quick shock buttons -->
          <div class="wi-title" style="margin-top: 12px;">Inject Shock</div>
          <div class="wi-shocks">
            <button class="wc-btn shock" v-for="s in shockPresets" :key="s.id" @click="fireShock(s.id)">
              {{ s.label }}
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- Loading overlay -->
    <div class="wv-loading" v-if="store.loading">Initializing world...</div>

    <!-- Error toast -->
    <div class="wv-error" v-if="store.error" @click="store.error = null">
      {{ store.error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as d3 from 'd3'
import { useWorldStore } from '@/stores/world'

const store = useWorldStore()

// ---------------------------------------------------------------
// Refs
// ---------------------------------------------------------------
const rootEl  = ref(null)
const graphEl = ref(null)
const svgEl   = ref(null)
const feedEl  = ref(null)

const sidebarCollapsed = ref(false)

let sim = null
let resizeObserver = null
let resizeTimeout = null

// Node/edge tracking for live pulse
let nodeSelection = null
let nodeDataMap   = {}

// ---------------------------------------------------------------
// Computed
// ---------------------------------------------------------------
const stateLabel = computed(() => {
  if (!store.initialized) return 'offline'
  if (store.running)      return 'running'
  if (store.autoTick)     return 'auto-tick'
  return 'idle'
})

const stateBadge = computed(() => {
  if (!store.initialized) return 'off'
  if (store.running)      return 'run'
  if (store.autoTick)     return 'auto'
  return 'idle'
})

const displayEvents = computed(() => {
  // Show last 50, newest on top
  return store.events.slice(-50).reverse()
})

// ---------------------------------------------------------------
// D3 Force Graph
// ---------------------------------------------------------------
const NODE_COLORS = {
  country:        '#4f8ef7',
  institution:    '#9b7ff4',
  nonstate_actor: '#f06060',
}

const EDGE_STYLES = {
  sanctions:          { stroke: '#f0a832', dash: '4,3', opacity: 0.7 },
  alliance:           { stroke: '#444',    dash: null,  opacity: 0.3 },
  institution_member: { stroke: '#555',    dash: null,  opacity: 0.15 },
  trade:              { stroke: '#333',    dash: null,  opacity: 0.1 },
  state_sponsor:      { stroke: '#f06060', dash: '3,3', opacity: 0.5 },
}

function renderGraph(graphData) {
  if (!svgEl.value || !graphEl.value) return

  const svg = d3.select(svgEl.value)
  svg.selectAll('*').remove()
  if (sim) { sim.stop(); sim = null }

  const width  = graphEl.value.clientWidth  || 800
  const height = graphEl.value.clientHeight || 600

  svg
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('width', width)
    .attr('height', height)

  const nodes = graphData.nodes.map(d => ({ ...d }))
  const edges = graphData.edges.map(d => ({ ...d }))

  const radiusScale = d3.scaleSqrt().domain([0, 50]).range([4, 24])

  const g = svg.append('g')

  // Zoom
  svg.call(
    d3.zoom()
      .scaleExtent([0.3, 6])
      .on('zoom', (event) => g.attr('transform', event.transform))
  )

  // Arrow markers
  const defs = svg.append('defs')
  ;['sanctions', 'state_sponsor'].forEach(type => {
    const style = EDGE_STYLES[type]
    defs.append('marker')
      .attr('id', `wv-arrow-${type}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-4L10,0L0,4')
      .attr('fill', style.stroke)
  })

  // Glow filter for pulsing nodes
  const filter = defs.append('filter').attr('id', 'wv-glow')
  filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur')
  filter.append('feMerge').selectAll('feMergeNode')
    .data(['blur', 'SourceGraphic'])
    .join('feMergeNode')
    .attr('in', d => d)

  // Links
  g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', d => EDGE_STYLES[d.type]?.stroke || '#333')
    .attr('stroke-opacity', d => EDGE_STYLES[d.type]?.opacity || 0.2)
    .attr('stroke-width', d => d.type === 'sanctions' ? 1.5 : 0.8)
    .attr('stroke-dasharray', d => EDGE_STYLES[d.type]?.dash || null)
    .attr('marker-end', d => d.directed ? `url(#wv-arrow-${d.type})` : null)

  // Nodes
  const node = g.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', d => radiusScale(d.size || 10))
    .attr('fill', d => NODE_COLORS[d.type] || '#666')
    .attr('stroke', 'rgba(255,255,255,0.15)')
    .attr('stroke-width', 1)
    .style('cursor', 'grab')

  nodeSelection = node
  nodeDataMap = {}
  nodes.forEach(n => { nodeDataMap[n.id] = n })

  // Labels
  const label = g.append('g')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text(d => d.type === 'country' ? (d.data?.flag || d.label) : d.label)
    .attr('font-size', d => d.type === 'country' ? 11 : 9)
    .attr('fill', '#8b90a0')
    .attr('text-anchor', 'middle')
    .attr('dy', d => radiusScale(d.size || 10) + 12)
    .style('pointer-events', 'none')

  // Drag
  function dragStart(event, d) {
    if (!event.active) sim.alphaTarget(0.3).restart()
    d.fx = d.x; d.fy = d.y
  }
  function dragging(event, d) { d.fx = event.x; d.fy = event.y }
  function dragEnd(event, d) {
    if (!event.active) sim.alphaTarget(0)
    d.fx = null; d.fy = null
  }
  node.call(d3.drag().on('start', dragStart).on('drag', dragging).on('end', dragEnd))

  // Tooltip
  node.append('title').text(d => {
    const data = d.data || {}
    if (d.type === 'country') return `${data.flag || ''} ${data.name || d.id}\nGDP: $${data.gdp_bn}B`
    return data.name || d.label
  })

  // Force simulation
  const linkSel = g.selectAll('line')
  sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      if (d.type === 'trade') return 120
      if (d.type === 'alliance') return 80
      if (d.type === 'institution_member') return 100
      return 90
    }))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => radiusScale(d.size || 10) + 6))
    .on('tick', () => {
      linkSel
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      node.attr('cx', d => d.x).attr('cy', d => d.y)
      label.attr('x', d => d.x).attr('y', d => d.y)
    })
}

// ---------------------------------------------------------------
// Pulse a node on event
// ---------------------------------------------------------------
function pulseNode(nodeId) {
  if (!nodeSelection) return
  nodeSelection
    .filter(d => d.id === nodeId)
    .transition().duration(200)
    .attr('stroke', '#fff')
    .attr('stroke-width', 3)
    .attr('filter', 'url(#wv-glow)')
    .transition().duration(800)
    .attr('stroke', 'rgba(255,255,255,0.15)')
    .attr('stroke-width', 1)
    .attr('filter', null)
}

// ---------------------------------------------------------------
// Event formatting
// ---------------------------------------------------------------
function formatType(t) {
  if (!t) return ''
  return t.replace(/_/g, ' ')
}

// ---------------------------------------------------------------
// Intervention
// ---------------------------------------------------------------
const intv = ref({
  agentId:     '',
  action:      '',
  usdDelta:    0,
  eurDelta:    0,
  eqDelta:     0,
  cryptoDelta: 0,
})
const intvResult = ref('')

async function submitIntervention() {
  const res = await store.intervene(intv.value.agentId, {
    action:       intv.value.action,
    usd_delta:    intv.value.usdDelta,
    eur_delta:    intv.value.eurDelta,
    equity_delta: intv.value.eqDelta,
    crypto_delta: intv.value.cryptoDelta,
  })
  if (res) {
    intvResult.value = `Queued: ${res.agent?.name} (${res.agent?.tier})`
    intv.value.action = ''
  } else {
    intvResult.value = store.error || 'Failed'
  }
  setTimeout(() => { intvResult.value = '' }, 4000)
}

// ---------------------------------------------------------------
// Shock presets
// ---------------------------------------------------------------
const shockPresets = [
  { id: 'fed_hike_75',    label: 'Fed +75bps' },
  { id: 'ecb_cut_50',     label: 'ECB -50bps' },
  { id: 'russia_sanction', label: 'RU Sanctions' },
  { id: 'nk_cyber',       label: 'NK Cyber' },
]

async function fireShock(id) {
  const res = await store.injectShock(id)
  if (res) {
    intvResult.value = `Shock: ${res.headline}`
    setTimeout(() => { intvResult.value = '' }, 4000)
  }
}

// ---------------------------------------------------------------
// Controls
// ---------------------------------------------------------------
async function handleInit() {
  await store.initWorld()
}

async function toggleEngine() {
  if (store.running) {
    await store.stopTicking()
  } else {
    await store.startTicking()
  }
}

// ---------------------------------------------------------------
// Watch events for node pulses
// ---------------------------------------------------------------
watch(() => store.events.length, async () => {
  await nextTick()
  // Auto-scroll feed
  if (feedEl.value) feedEl.value.scrollTop = 0

  // Pulse affected node
  const latest = store.events[store.events.length - 1]
  if (latest?.actor_id && latest.event_type !== 'tick_start' && latest.event_type !== 'tick_end') {
    pulseNode(latest.actor_id)
  }
})

// Watch graph data changes
watch(() => store.worldGraph, (graph) => {
  if (graph) nextTick(() => renderGraph(graph))
}, { deep: true })

// ---------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------
onMounted(async () => {
  // Try to load existing state
  await store.fetchState()
  if (store.initialized) {
    await store.fetchWorldGraph()
  }
  store.startSSE()

  // Resize handling
  resizeObserver = new ResizeObserver(() => {
    clearTimeout(resizeTimeout)
    resizeTimeout = setTimeout(() => {
      if (store.worldGraph) renderGraph(store.worldGraph)
    }, 200)
  })
  if (graphEl.value) resizeObserver.observe(graphEl.value)
})

onBeforeUnmount(() => {
  store.cleanup()
  if (sim) sim.stop()
  if (resizeObserver) resizeObserver.disconnect()
  clearTimeout(resizeTimeout)
})
</script>

<style scoped>
.world-view {
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
.wv-graph {
  position: absolute;
  inset: 0;
}
.wv-graph svg {
  display: block;
  width: 100%;
  height: 100%;
}

/* ── Status overlay (top-left) ── */
.wv-status {
  position: absolute;
  top: 16px;
  left: 16px;
  background: rgba(8,12,20,0.85);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
  min-width: 160px;
}
.ws-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.ws-label {
  font-size: 9px;
  color: var(--text3);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.ws-val {
  font-size: 12px;
  color: var(--text);
  font-weight: 600;
}
.ws-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.ws-badge.off  { background: #333; color: #666; }
.ws-badge.idle { background: rgba(79,142,247,0.2); color: var(--accent); }
.ws-badge.run  { background: rgba(45,212,160,0.2); color: var(--accent2); }
.ws-badge.auto { background: rgba(240,168,50,0.2); color: var(--amber); }

/* ── Controls (bottom-left) ── */
.wv-controls {
  position: absolute;
  bottom: 16px;
  left: 16px;
  display: flex;
  gap: 8px;
  z-index: 10;
}
.wc-btn {
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
.wc-btn:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--accent);
}
.wc-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.wc-btn.active {
  border-color: var(--amber);
  color: var(--amber);
  background: rgba(240,168,50,0.1);
}
.wc-btn.accent {
  border-color: var(--accent);
  color: var(--accent);
}
.wc-btn.accent:hover:not(:disabled) {
  background: rgba(79,142,247,0.15);
}
.wc-btn.shock {
  font-size: 10px;
  padding: 5px 10px;
  border-color: rgba(240,96,96,0.3);
  color: #f06060;
}
.wc-btn.shock:hover:not(:disabled) {
  background: rgba(240,96,96,0.1);
  border-color: #f06060;
}

/* ── Sidebar ── */
.wv-sidebar {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 340px;
  background: rgba(8,12,20,0.9);
  backdrop-filter: blur(12px);
  border-left: 1px solid var(--border);
  z-index: 10;
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 16px;
  overflow: hidden;
  transition: width 0.2s;
}
.wv-sidebar.collapsed {
  width: 32px;
  padding: 0;
}
.ws-toggle {
  position: absolute;
  top: 12px;
  left: -16px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--border2);
  background: rgba(8,12,20,0.9);
  color: var(--text3);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 11;
}

/* ── Event Feed ── */
.wv-feed {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.wf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  flex-shrink: 0;
}
.wf-title {
  font-size: 10px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.wf-count {
  font-size: 10px;
  color: var(--text3);
  background: rgba(255,255,255,0.05);
  padding: 1px 6px;
  border-radius: 3px;
}
.wf-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}
.wf-card {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--bg2);
  flex-shrink: 0;
}
.wf-card.sev-warning  { border-left: 3px solid var(--amber); }
.wf-card.sev-critical { border-left: 3px solid #f06060; }
.wf-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.wf-type {
  font-size: 9px;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.wf-tick {
  font-size: 9px;
  color: var(--text3);
}
.wf-headline {
  font-size: 11px;
  color: var(--text);
  line-height: 1.3;
}
.wf-desc {
  font-size: 10px;
  color: var(--text2);
  margin-top: 2px;
  line-height: 1.3;
}
.wf-actor {
  font-size: 9px;
  color: var(--text3);
  margin-top: 4px;
}
.wf-empty {
  font-size: 11px;
  color: var(--text3);
  text-align: center;
  padding: 32px 0;
}

/* ── Intervention Panel ── */
.wv-intervene {
  flex-shrink: 0;
  border-top: 1px solid var(--border);
  padding-top: 12px;
}
.wi-title {
  font-size: 10px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.wi-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.wi-input {
  font-family: inherit;
  font-size: 11px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 5px;
  background: var(--bg);
  color: var(--text);
  outline: none;
}
.wi-input:focus { border-color: var(--accent); }
.wi-input::placeholder { color: var(--text3); }
.wi-sliders {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 8px;
}
.wi-slider {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  color: var(--text3);
}
.wi-slider input[type="range"] {
  flex: 1;
  height: 3px;
  accent-color: var(--accent);
}
.wi-sv {
  font-size: 10px;
  color: var(--text2);
  width: 28px;
  text-align: right;
}
.wi-result {
  font-size: 10px;
  color: var(--accent2);
  padding: 4px 0;
}
.wi-shocks {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}

/* ── Loading / Error ── */
.wv-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(8,12,20,0.7);
  font-size: 14px;
  color: var(--text2);
  z-index: 20;
}
.wv-error {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(240,96,96,0.15);
  border: 1px solid rgba(240,96,96,0.4);
  color: #f06060;
  font-size: 11px;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  z-index: 20;
}

/* ── Transitions ── */
.ev-enter-active { transition: all 0.3s ease; }
.ev-enter-from  { opacity: 0; transform: translateY(-8px); }
.ev-leave-active { transition: all 0.2s ease; }
.ev-leave-to    { opacity: 0; transform: translateX(8px); }

/* ── Responsive ── */
@media (max-width: 900px) {
  .wv-sidebar { width: 280px; }
}
</style>
