<template>
  <div class="world-view">
    <!-- Full-screen D3 force graph (background) -->
    <div class="wv-graph" ref="graphEl">
      <svg ref="svgEl"></svg>
    </div>

    <!-- Left sidebar: Agent roles + agent list -->
    <div class="wv-left" :class="{ expanded: !!store.selectedRole }">
      <div class="wl-header">Agents</div>

      <!-- Role list -->
      <div class="wl-roles">
        <button
          class="wr-btn"
          v-for="r in store.roles"
          :key="r.role"
          :class="{ active: store.selectedRole === r.role }"
          @click="store.selectRole(r.role)"
        >
          <span class="wr-icon">{{ r.icon }}</span>
          <span class="wr-label">{{ r.label }}</span>
          <span class="wr-count">{{ r.count }}</span>
        </button>
        <div class="wl-empty" v-if="store.roles.length === 0">
          Initialize world first
        </div>
      </div>

      <!-- Agent list (when a role is selected) -->
      <div class="wl-agents" v-if="store.selectedRole && store.roleAgents.length">
        <div class="wl-sub">{{ store.roleAgents.length }} agents</div>
        <button
          class="wa-btn"
          v-for="a in store.roleAgents"
          :key="a.agent_id"
          :class="{ active: store.selectedAgentId === a.agent_id }"
          @click="store.fetchPerspective(a.agent_id)"
        >
          <span class="wa-name">{{ a.name }}</span>
          <span class="wa-country">{{ flag(a.country) }}</span>
        </button>
      </div>

      <button class="wl-back" v-if="store.selectedRole" @click="store.clearPerspective()">
        Clear
      </button>
    </div>

    <!-- Agent Perspective Panel (foreground overlay) -->
    <div class="wv-perspective" v-if="store.perspective && !store.perspectiveLoading">
      <div class="wp-header">
        <div class="wp-identity">
          <span class="wp-icon">{{ store.perspective.role_icon }}</span>
          <div>
            <div class="wp-name">{{ store.perspective.name }}</div>
            <div class="wp-role">{{ store.perspective.role_label }} · {{ flag(store.perspective.country) }} {{ store.perspective.country }} · Age {{ store.perspective.age }}</div>
          </div>
        </div>
        <button class="wp-close" @click="store.clearPerspective()">x</button>
      </div>

      <div class="wp-body">
        <!-- Beliefs -->
        <div class="wp-section">
          <div class="wp-stitle">Beliefs</div>
          <div class="wp-beliefs">
            <div class="wb-row" v-for="(val, key) in store.perspective.life.beliefs" :key="key">
              <span class="wb-key">{{ formatBelief(key) }}</span>
              <div class="wb-bar-bg">
                <div class="wb-bar" :style="{ width: (val * 100) + '%', background: beliefColor(val) }"></div>
              </div>
              <span class="wb-val">{{ (val * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>

        <!-- Portfolio -->
        <div class="wp-section">
          <div class="wp-stitle">Portfolio</div>
          <div class="wp-portfolio">
            <div class="wpo-item" v-for="(val, key) in store.perspective.portfolio" :key="key">
              <span class="wpo-key">{{ key.replace(/_/g, ' ') }}</span>
              <span class="wpo-val" v-if="key === 'net_wealth_eur'">{{ formatMoney(val) }}</span>
              <span class="wpo-val" v-else>{{ (val * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

        <!-- Recent Decisions -->
        <div class="wp-section">
          <div class="wp-stitle">Recent Decisions</div>
          <div class="wp-decisions">
            <div class="wd-card" v-for="(d, i) in store.perspective.life.recent_decisions" :key="i">
              <div class="wd-action">{{ d.action }}</div>
              <div class="wd-reason">{{ d.reasoning }}</div>
            </div>
            <div class="wp-empty" v-if="!store.perspective.life.recent_decisions.length">
              No decisions yet
            </div>
          </div>
        </div>

        <!-- Messages -->
        <div class="wp-section">
          <div class="wp-stitle">Messages ({{ store.perspective.recent_messages.length }})</div>
          <div class="wp-messages">
            <div class="wm-card" v-for="m in store.perspective.recent_messages.slice().reverse()" :key="m.message_id">
              <div class="wm-top">
                <span class="wm-type">{{ m.message_type }}</span>
                <span class="wm-tick">t{{ m.tick }}</span>
              </div>
              <div class="wm-content">{{ m.content }}</div>
              <div class="wm-from" v-if="m.sender_id">from: {{ m.sender_id.slice(0, 8) }}...</div>
            </div>
            <div class="wp-empty" v-if="!store.perspective.recent_messages.length">
              No messages received
            </div>
          </div>
        </div>

        <!-- Social Network -->
        <div class="wp-section">
          <div class="wp-stitle">Social Network</div>
          <div class="wp-network">
            <div class="wn-group" v-if="store.perspective.information_sources.length">
              <div class="wn-label">Info Sources</div>
              <div
                class="wn-agent"
                v-for="s in store.perspective.information_sources"
                :key="s.agent_id"
                @click="store.fetchPerspective(s.agent_id)"
              >
                {{ s.name }} <span class="wn-role">({{ s.role }})</span>
              </div>
            </div>
            <div class="wn-group" v-if="store.perspective.social_connections.length">
              <div class="wn-label">Connections</div>
              <div
                class="wn-agent"
                v-for="c in store.perspective.social_connections"
                :key="c.agent_id"
                @click="store.fetchPerspective(c.agent_id)"
              >
                {{ flag(c.country) }} {{ c.name }} <span class="wn-role">({{ c.role }})</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Country + Macro -->
        <div class="wp-section" v-if="store.perspective.country_data">
          <div class="wp-stitle">{{ store.perspective.country_data.name }}</div>
          <div class="wp-portfolio">
            <div class="wpo-item">
              <span class="wpo-key">GDP</span>
              <span class="wpo-val">${{ store.perspective.country_data.gdp_usd_bn.toFixed(0) }}B</span>
            </div>
            <div class="wpo-item">
              <span class="wpo-key">Inflation</span>
              <span class="wpo-val">{{ store.perspective.country_data.inflation_pct.toFixed(1) }}%</span>
            </div>
            <div class="wpo-item">
              <span class="wpo-key">Unemployment</span>
              <span class="wpo-val">{{ store.perspective.country_data.unemployment_pct.toFixed(1) }}%</span>
            </div>
            <div class="wpo-item" v-if="store.perspective.country_data.sanctioned">
              <span class="wpo-key">Sanctioned</span>
              <span class="wpo-val sanctioned">YES</span>
            </div>
          </div>
        </div>

        <!-- Employment -->
        <div class="wp-section">
          <div class="wp-stitle">Employment</div>
          <div class="wp-portfolio">
            <div class="wpo-item">
              <span class="wpo-key">Title</span>
              <span class="wpo-val">{{ store.perspective.life.employment.job_title }}</span>
            </div>
            <div class="wpo-item">
              <span class="wpo-key">Salary</span>
              <span class="wpo-val">{{ formatMoney(store.perspective.life.employment.salary_monthly_eur) }}/mo</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading perspective -->
    <div class="wv-perspective loading" v-if="store.perspectiveLoading">
      <div class="wp-loading">Loading perspective...</div>
    </div>

    <!-- Status bar (top-right overlay when no perspective) -->
    <div class="wv-status" v-if="!store.perspective">
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
      <button
        class="wc-btn god-toggle"
        :class="{ active: store.godMode }"
        @click="store.toggleGodMode()"
        :disabled="!store.initialized"
      >
        {{ store.godMode ? 'God Mode' : 'Observer' }}
      </button>
    </div>

    <!-- Right sidebar: Event Feed + God Mode / Shocks -->
    <div class="wv-sidebar" v-if="!store.perspective" :class="{ collapsed: sidebarCollapsed }">
      <button class="ws-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
        {{ sidebarCollapsed ? '◂' : '▸' }}
      </button>

      <template v-if="!sidebarCollapsed">
        <!-- Event feed (always visible, shrinks when god mode active) -->
        <div class="wv-feed" :class="{ compact: store.godMode }">
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
              </div>
            </TransitionGroup>
            <div class="wf-empty" v-if="store.events.length === 0">
              No events yet. Initialize the world to begin.
            </div>
          </div>
        </div>

        <!-- God Mode Panel -->
        <div class="wv-god" v-if="store.godMode">
          <div class="wg-header">
            <span class="wg-title">God Mode</span>
            <span class="wg-indicator"></span>
          </div>

          <!-- Intervention type selector -->
          <select class="wg-select" v-model="godType">
            <option value="">Select intervention...</option>
            <option v-for="(schema, key) in store.interventionTypes" :key="key" :value="key">
              {{ schema.icon }} {{ schema.label }}
            </option>
          </select>

          <!-- Dynamic parameter inputs -->
          <div class="wg-params" v-if="godType && store.interventionTypes[godType]">
            <div class="wg-desc">{{ store.interventionTypes[godType].desc }}</div>
            <div class="wg-field" v-for="(pdef, pkey) in store.interventionTypes[godType].params" :key="pkey">
              <label class="wg-label">{{ pdef.label }}</label>
              <select
                v-if="pdef.type === 'select'"
                class="wg-input"
                v-model="godParams[pkey]"
              >
                <option v-for="opt in pdef.options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <select
                v-else-if="pdef.type === 'boolean'"
                class="wg-input"
                v-model="godParams[pkey]"
              >
                <option :value="true">Yes</option>
                <option :value="false">No</option>
              </select>
              <input
                v-else-if="pdef.type === 'number'"
                type="number"
                class="wg-input"
                v-model.number="godParams[pkey]"
                :min="pdef.min"
                :max="pdef.max"
                :placeholder="pdef.label"
              />
              <input
                v-else
                type="text"
                class="wg-input"
                v-model="godParams[pkey]"
                :placeholder="pdef.label"
              />
            </div>
            <button class="wc-btn god-exec" @click="executeGod" :disabled="godExecuting">
              Execute
            </button>
            <div class="wg-result" v-if="godResult">{{ godResult }}</div>
          </div>

          <!-- Intervention History -->
          <div class="wg-history" v-if="store.interventionHistory.length">
            <div class="wg-htitle">History</div>
            <div class="wg-hlist">
              <div class="wg-hcard" v-for="h in store.interventionHistory.slice().reverse().slice(0, 10)" :key="h.intervention_id">
                <div class="wg-htop">
                  <span class="wg-htype">{{ h.intervention_type }}</span>
                  <span class="wg-htick">t{{ h.tick }}</span>
                </div>
                <div class="wg-heffects">
                  <span v-for="(val, key) in limitEffects(h.effects)" :key="key" class="wg-heff">
                    {{ key }}: {{ typeof val === 'number' ? val.toFixed?.(1) ?? val : val }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Observer mode: just show shock buttons -->
        <div class="wv-shocks" v-if="!store.godMode">
          <div class="wi-title">Inject Shock</div>
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
const graphEl = ref(null)
const svgEl   = ref(null)
const feedEl  = ref(null)

const sidebarCollapsed = ref(false)

let sim = null
let resizeObserver = null
let resizeTimeout = null
let nodeSelection = null

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

const displayEvents = computed(() => store.events.slice(-50).reverse())

// ---------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------
function flag(iso2) {
  if (!iso2 || iso2.length !== 2) return ''
  return String.fromCodePoint(
    ...iso2.toUpperCase().split('').map(c => 0x1F1E6 + c.charCodeAt(0) - 65)
  )
}

function formatType(t) {
  return t ? t.replace(/_/g, ' ') : ''
}

function formatBelief(key) {
  return key.replace(/_/g, ' ')
}

function beliefColor(val) {
  if (val > 0.7) return '#f06060'
  if (val > 0.4) return '#f0a832'
  return '#2dd4a0'
}

function formatMoney(val) {
  if (val >= 1_000_000) return `€${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `€${(val / 1_000).toFixed(1)}K`
  return `€${val.toFixed(0)}`
}

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

  svg.call(
    d3.zoom()
      .scaleExtent([0.3, 6])
      .on('zoom', (event) => g.attr('transform', event.transform))
  )

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

  const filter = defs.append('filter').attr('id', 'wv-glow')
  filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur')
  filter.append('feMerge').selectAll('feMergeNode')
    .data(['blur', 'SourceGraphic'])
    .join('feMergeNode')
    .attr('in', d => d)

  g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', d => EDGE_STYLES[d.type]?.stroke || '#333')
    .attr('stroke-opacity', d => EDGE_STYLES[d.type]?.opacity || 0.2)
    .attr('stroke-width', d => d.type === 'sanctions' ? 1.5 : 0.8)
    .attr('stroke-dasharray', d => EDGE_STYLES[d.type]?.dash || null)
    .attr('marker-end', d => d.directed ? `url(#wv-arrow-${d.type})` : null)

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

  node.append('title').text(d => {
    const data = d.data || {}
    if (d.type === 'country') return `${data.flag || ''} ${data.name || d.id}\nGDP: $${data.gdp_bn}B`
    return data.name || d.label
  })

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

// Highlight the agent's country node when perspective is open
watch(() => store.perspective?.country, (country) => {
  if (!nodeSelection) return
  nodeSelection
    .attr('stroke', d => d.id === country ? '#fff' : 'rgba(255,255,255,0.15)')
    .attr('stroke-width', d => d.id === country ? 3 : 1)
})

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
// God Mode
// ---------------------------------------------------------------
const godType = ref('')
const godParams = ref({})
const godResult = ref('')
const godExecuting = ref(false)

// Reset params when type changes
watch(godType, () => {
  godParams.value = {}
  godResult.value = ''
})

async function executeGod() {
  if (!godType.value) return
  godExecuting.value = true
  godResult.value = ''
  const res = await store.executeIntervention(godType.value, godParams.value)
  godExecuting.value = false
  if (res) {
    godResult.value = res.headline || 'Executed'
    setTimeout(() => { godResult.value = '' }, 5000)
  } else {
    godResult.value = store.error || 'Failed'
  }
}

function limitEffects(effects) {
  // Show at most 4 key effects, skip arrays/objects
  const out = {}
  let count = 0
  for (const [k, v] of Object.entries(effects)) {
    if (count >= 4) break
    if (typeof v === 'object' && v !== null) continue
    out[k] = v
    count++
  }
  return out
}

// ---------------------------------------------------------------
// Shocks
// ---------------------------------------------------------------
const shockPresets = [
  { id: 'fed_hike_75',    label: 'Fed +75bps' },
  { id: 'ecb_cut_50',     label: 'ECB -50bps' },
  { id: 'russia_sanction', label: 'RU Sanctions' },
  { id: 'nk_cyber',       label: 'NK Cyber' },
]

async function fireShock(id) {
  await store.injectShock(id)
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
// Watchers
// ---------------------------------------------------------------
watch(() => store.events.length, async () => {
  await nextTick()
  if (feedEl.value) feedEl.value.scrollTop = 0
  const latest = store.events[store.events.length - 1]
  if (latest?.actor_id && latest.event_type !== 'tick_start' && latest.event_type !== 'tick_end') {
    pulseNode(latest.actor_id)
  }
})

watch(() => store.worldGraph, (graph) => {
  if (graph) nextTick(() => renderGraph(graph))
}, { deep: true })

// ---------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------
onMounted(async () => {
  await store.fetchState()
  if (store.initialized) {
    await store.fetchWorldGraph()
    await store.fetchRoles()
  }
  store.startSSE()

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
.wv-graph { position: absolute; inset: 0; }
.wv-graph svg { display: block; width: 100%; height: 100%; }

/* ── Left sidebar: roles + agents ── */
.wv-left {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 200px;
  background: rgba(8,12,20,0.92);
  backdrop-filter: blur(12px);
  border-right: 1px solid var(--border);
  z-index: 12;
  display: flex;
  flex-direction: column;
  padding: 12px 0;
  overflow-y: auto;
  transition: width 0.2s;
}
.wv-left.expanded { width: 220px; }
.wl-header {
  font-size: 10px;
  color: var(--text3);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0 14px 8px;
  flex-shrink: 0;
}
.wl-roles { display: flex; flex-direction: column; gap: 2px; flex-shrink: 0; }
.wr-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border: none;
  background: transparent;
  color: var(--text2);
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  text-align: left;
  transition: all 0.12s;
}
.wr-btn:hover { background: rgba(255,255,255,0.04); color: var(--text); }
.wr-btn.active { background: rgba(79,142,247,0.12); color: var(--accent); }
.wr-icon { font-size: 14px; width: 20px; text-align: center; }
.wr-label { flex: 1; }
.wr-count {
  font-size: 9px;
  color: var(--text3);
  background: rgba(255,255,255,0.05);
  padding: 1px 5px;
  border-radius: 3px;
}
.wl-empty {
  font-size: 10px;
  color: var(--text3);
  padding: 16px 14px;
  text-align: center;
}

/* Agent list within left sidebar */
.wl-agents {
  border-top: 1px solid var(--border);
  margin-top: 8px;
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.wl-sub {
  font-size: 9px;
  color: var(--text3);
  padding: 0 14px 4px;
  letter-spacing: 0.06em;
}
.wa-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 14px;
  border: none;
  background: transparent;
  color: var(--text2);
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.12s;
}
.wa-btn:hover { background: rgba(255,255,255,0.04); color: var(--text); }
.wa-btn.active { background: rgba(45,212,160,0.12); color: var(--accent2); }
.wa-name { flex: 1; text-align: left; }
.wa-country { font-size: 13px; }
.wl-back {
  margin: 8px 14px 0;
  font-family: inherit;
  font-size: 10px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text3);
  cursor: pointer;
  flex-shrink: 0;
}
.wl-back:hover { color: var(--text); border-color: var(--border2); }

/* ── Perspective panel (foreground) ── */
.wv-perspective {
  position: absolute;
  top: 0;
  left: 220px;
  bottom: 0;
  width: 380px;
  background: rgba(8,12,20,0.94);
  backdrop-filter: blur(14px);
  border-right: 1px solid var(--border);
  z-index: 11;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.wv-perspective.loading {
  display: flex;
  align-items: center;
  justify-content: center;
}
.wp-loading { font-size: 12px; color: var(--text3); }
.wp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.wp-identity { display: flex; align-items: center; gap: 10px; }
.wp-icon { font-size: 24px; }
.wp-name { font-size: 14px; font-weight: 600; color: var(--text); }
.wp-role { font-size: 10px; color: var(--text2); margin-top: 2px; }
.wp-close {
  width: 24px;
  height: 24px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text3);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.wp-close:hover { color: var(--text); border-color: var(--border2); }

.wp-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wp-section { display: flex; flex-direction: column; gap: 6px; }
.wp-stitle {
  font-size: 9px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* Beliefs bars */
.wp-beliefs { display: flex; flex-direction: column; gap: 4px; }
.wb-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wb-key {
  font-size: 10px;
  color: var(--text2);
  width: 110px;
  flex-shrink: 0;
  text-transform: capitalize;
}
.wb-bar-bg {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  overflow: hidden;
}
.wb-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}
.wb-val {
  font-size: 10px;
  color: var(--text2);
  width: 32px;
  text-align: right;
  flex-shrink: 0;
}

/* Portfolio / stats */
.wp-portfolio { display: flex; flex-direction: column; gap: 4px; }
.wpo-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.wpo-key { font-size: 10px; color: var(--text2); text-transform: capitalize; }
.wpo-val { font-size: 11px; color: var(--text); font-weight: 500; }
.wpo-val.sanctioned { color: #f06060; }

/* Decisions */
.wp-decisions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
}
.wd-card {
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--bg2);
}
.wd-action { font-size: 11px; color: var(--text); }
.wd-reason { font-size: 9px; color: var(--text3); margin-top: 2px; }

/* Messages */
.wp-messages {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
}
.wm-card {
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--bg2);
}
.wm-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 3px;
}
.wm-type {
  font-size: 8px;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.wm-tick { font-size: 8px; color: var(--text3); }
.wm-content { font-size: 10px; color: var(--text); line-height: 1.3; }
.wm-from { font-size: 8px; color: var(--text3); margin-top: 2px; }
.wp-empty { font-size: 10px; color: var(--text3); padding: 8px 0; text-align: center; }

/* Social network */
.wp-network { display: flex; flex-direction: column; gap: 8px; }
.wn-group { display: flex; flex-direction: column; gap: 2px; }
.wn-label { font-size: 9px; color: var(--text3); margin-bottom: 2px; }
.wn-agent {
  font-size: 10px;
  color: var(--text2);
  padding: 3px 0;
  cursor: pointer;
  transition: color 0.12s;
}
.wn-agent:hover { color: var(--accent); }
.wn-role { color: var(--text3); font-size: 9px; }

/* ── Status overlay ── */
.wv-status {
  position: absolute;
  top: 16px;
  right: 360px;
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
.ws-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.ws-label { font-size: 9px; color: var(--text3); letter-spacing: 0.1em; text-transform: uppercase; }
.ws-val { font-size: 12px; color: var(--text); font-weight: 600; }
.ws-badge {
  font-size: 9px; font-weight: 700; padding: 2px 8px; border-radius: 3px;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.ws-badge.off  { background: #333; color: #666; }
.ws-badge.idle { background: rgba(79,142,247,0.2); color: var(--accent); }
.ws-badge.run  { background: rgba(45,212,160,0.2); color: var(--accent2); }
.ws-badge.auto { background: rgba(240,168,50,0.2); color: var(--amber); }

/* ── Controls ── */
.wv-controls {
  position: absolute;
  bottom: 16px;
  left: 220px;
  display: flex;
  gap: 8px;
  z-index: 10;
}
.wc-btn {
  font-family: inherit; font-size: 11px; padding: 7px 14px;
  border: 1px solid var(--border2); border-radius: 6px;
  background: rgba(8,12,20,0.85); backdrop-filter: blur(8px);
  color: var(--text2); cursor: pointer; transition: all 0.15s;
  letter-spacing: 0.02em;
}
.wc-btn:hover:not(:disabled) { color: var(--text); border-color: var(--accent); }
.wc-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.wc-btn.active { border-color: var(--amber); color: var(--amber); background: rgba(240,168,50,0.1); }
.wc-btn.shock {
  font-size: 10px; padding: 5px 10px;
  border-color: rgba(240,96,96,0.3); color: #f06060;
}
.wc-btn.shock:hover:not(:disabled) { background: rgba(240,96,96,0.1); border-color: #f06060; }

/* ── Right sidebar ── */
.wv-sidebar {
  position: absolute;
  top: 0; right: 0; bottom: 0;
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
.wv-sidebar.collapsed { width: 32px; padding: 0; }
.ws-toggle {
  position: absolute; top: 12px; left: -16px;
  width: 32px; height: 32px; border-radius: 50%;
  border: 1px solid var(--border2);
  background: rgba(8,12,20,0.9); color: var(--text3);
  cursor: pointer; font-size: 12px;
  display: flex; align-items: center; justify-content: center;
  z-index: 11;
}

/* ── Event Feed ── */
.wv-feed { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.wf-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; flex-shrink: 0;
}
.wf-title { font-size: 10px; color: var(--text3); letter-spacing: 0.08em; text-transform: uppercase; }
.wf-count {
  font-size: 10px; color: var(--text3);
  background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 3px;
}
.wf-list {
  flex: 1; overflow-y: auto;
  display: flex; flex-direction: column; gap: 6px; min-height: 0;
}
.wf-card {
  border: 1px solid var(--border); border-radius: 6px;
  padding: 8px 10px; background: var(--bg2); flex-shrink: 0;
}
.wf-card.sev-warning  { border-left: 3px solid var(--amber); }
.wf-card.sev-critical { border-left: 3px solid #f06060; }
.wf-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.wf-type { font-size: 9px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.06em; }
.wf-tick { font-size: 9px; color: var(--text3); }
.wf-headline { font-size: 11px; color: var(--text); line-height: 1.3; }
.wf-desc { font-size: 10px; color: var(--text2); margin-top: 2px; line-height: 1.3; }
.wf-empty { font-size: 11px; color: var(--text3); text-align: center; padding: 32px 0; }

/* Shocks */
.wv-shocks {
  flex-shrink: 0;
  border-top: 1px solid var(--border);
  padding-top: 12px;
}
.wi-title {
  font-size: 10px; color: var(--text3);
  letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px;
}
.wi-shocks { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }

/* ── Loading / Error ── */
.wv-loading {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(8,12,20,0.7); font-size: 14px; color: var(--text2); z-index: 20;
}
.wv-error {
  position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%);
  background: rgba(240,96,96,0.15); border: 1px solid rgba(240,96,96,0.4);
  color: #f06060; font-size: 11px; padding: 8px 16px;
  border-radius: 6px; cursor: pointer; z-index: 20;
}

/* ── Transitions ── */
.ev-enter-active { transition: all 0.3s ease; }
.ev-enter-from  { opacity: 0; transform: translateY(-8px); }
.ev-leave-active { transition: all 0.2s ease; }
.ev-leave-to    { opacity: 0; transform: translateX(8px); }

/* ── God Mode toggle button ── */
.wc-btn.god-toggle {
  border-color: rgba(240,96,96,0.3);
  color: var(--text2);
}
.wc-btn.god-toggle.active {
  border-color: #f06060;
  color: #f06060;
  background: rgba(240,96,96,0.12);
  text-shadow: 0 0 8px rgba(240,96,96,0.4);
}

/* ── Feed compact mode ── */
.wv-feed.compact { max-height: 35%; flex: none; }

/* ── God Mode Panel ── */
.wv-god {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid rgba(240,96,96,0.2);
  padding-top: 10px;
  min-height: 0;
  overflow-y: auto;
}
.wg-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wg-title {
  font-size: 10px;
  color: #f06060;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
}
.wg-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f06060;
  animation: god-pulse 1.5s ease-in-out infinite;
}
@keyframes god-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.wg-select {
  font-family: inherit;
  font-size: 11px;
  padding: 6px 8px;
  border: 1px solid rgba(240,96,96,0.3);
  border-radius: 5px;
  background: var(--bg);
  color: var(--text);
  outline: none;
  cursor: pointer;
}
.wg-select:focus { border-color: #f06060; }
.wg-desc {
  font-size: 10px;
  color: var(--text3);
  line-height: 1.3;
  padding: 2px 0;
}
.wg-params {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.wg-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wg-label {
  font-size: 9px;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.wg-input {
  font-family: inherit;
  font-size: 11px;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  outline: none;
}
.wg-input:focus { border-color: #f06060; }
.wg-input::placeholder { color: var(--text3); }
.wc-btn.god-exec {
  border-color: #f06060;
  color: #f06060;
  font-weight: 600;
  margin-top: 4px;
}
.wc-btn.god-exec:hover:not(:disabled) {
  background: rgba(240,96,96,0.12);
}
.wg-result {
  font-size: 10px;
  color: var(--accent2);
  padding: 2px 0;
}

/* ── Intervention History ── */
.wg-history {
  border-top: 1px solid var(--border);
  padding-top: 8px;
  margin-top: 4px;
}
.wg-htitle {
  font-size: 9px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.wg-hlist {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 180px;
  overflow-y: auto;
}
.wg-hcard {
  border: 1px solid rgba(240,96,96,0.15);
  border-left: 3px solid #f06060;
  border-radius: 4px;
  padding: 5px 8px;
  background: var(--bg2);
}
.wg-htop {
  display: flex;
  justify-content: space-between;
  margin-bottom: 3px;
}
.wg-htype {
  font-size: 9px;
  color: #f06060;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.wg-htick { font-size: 9px; color: var(--text3); }
.wg-heffects {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
}
.wg-heff {
  font-size: 9px;
  color: var(--text2);
}

@media (max-width: 1100px) {
  .wv-perspective { width: 320px; }
  .wv-sidebar { width: 280px; }
}
</style>
