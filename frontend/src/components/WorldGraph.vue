<template>
  <div class="world-graph" ref="containerEl">
    <div class="wg-loading" v-if="store.worldGraphLoading">Loading world graph...</div>
    <svg ref="svgEl"></svg>
    <div class="wg-tooltip" ref="tooltipEl" v-show="tooltip.show">
      <div class="tt-title">{{ tooltip.title }}</div>
      <div class="tt-body" v-html="tooltip.body"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as d3 from 'd3'
import { useSimulationStore } from '@/stores/simulation'

const store = useSimulationStore()

const containerEl = ref(null)
const svgEl = ref(null)
const tooltipEl = ref(null)
const tooltip = ref({ show: false, title: '', body: '' })

let simulation = null
let resizeObserver = null

const NODE_COLORS = {
  country:        '#4f8ef7',
  institution:    '#9b7ff4',
  nonstate_actor: '#f06060',
}

const EDGE_STYLES = {
  sanctions:          { stroke: '#f0a832', dash: '4,3', opacity: 0.7 },
  alliance:           { stroke: '#444',    dash: null,   opacity: 0.3 },
  institution_member: { stroke: '#555',    dash: null,   opacity: 0.15 },
  trade:              { stroke: '#333',    dash: null,   opacity: 0.1 },
  state_sponsor:      { stroke: '#f06060', dash: '3,3',  opacity: 0.5 },
}

function buildTooltip(d) {
  const data = d.data || {}
  if (d.type === 'country') {
    return {
      title: `${data.flag || ''} ${data.name || d.id}`,
      body: [
        data.gdp_bn ? `GDP: $${data.gdp_bn}B` : '',
        data.currency ? `Currency: ${data.currency}` : '',
        data.regime ? `Regime: ${data.regime}` : '',
        data.blocs?.length ? `Blocs: ${data.blocs.join(', ')}` : '',
        data.sanctioned ? '<span style="color:#f0a832">Sanctioned</span>' : '',
      ].filter(Boolean).join('<br>'),
    }
  }
  if (d.type === 'institution') {
    return {
      title: data.name || d.id,
      body: [
        data.inst_type ? `Type: ${data.inst_type}` : '',
        data.hq ? `HQ: ${data.hq}` : '',
        `Enforcement: ${data.enforcement}`,
        `Narrative: ${data.narrative}`,
      ].filter(Boolean).join('<br>'),
    }
  }
  return {
    title: data.name || d.id,
    body: [
      data.actor_type ? `Type: ${data.actor_type}` : '',
      data.hq ? `HQ: ${data.hq}` : '',
      data.threat ? `Threat: ${data.threat}` : '',
      data.cyber != null ? `Cyber: ${data.cyber}` : '',
      data.sponsors?.length ? `Sponsors: ${data.sponsors.join(', ')}` : '',
    ].filter(Boolean).join('<br>'),
  }
}

function render(graphData) {
  if (!svgEl.value || !containerEl.value) return

  const svg = d3.select(svgEl.value)
  svg.selectAll('*').remove()

  const rect = containerEl.value.getBoundingClientRect()
  const width = rect.width || 800
  const height = rect.height || 600

  svg.attr('width', width).attr('height', height)

  const nodes = graphData.nodes.map(d => ({ ...d }))
  const edges = graphData.edges.map(d => ({ ...d }))

  const radiusScale = d3.scaleSqrt().domain([0, 50]).range([4, 24])

  const g = svg.append('g')

  // Zoom
  const zoom = d3.zoom()
    .scaleExtent([0.3, 4])
    .on('zoom', (event) => g.attr('transform', event.transform))
  svg.call(zoom)

  // Arrow markers for directed edges
  const defs = svg.append('defs')
  ;['sanctions', 'state_sponsor'].forEach(type => {
    const style = EDGE_STYLES[type]
    defs.append('marker')
      .attr('id', `arrow-${type}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-4L10,0L0,4')
      .attr('fill', style.stroke)
  })

  // Links
  const link = g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', d => (EDGE_STYLES[d.type]?.stroke || '#333'))
    .attr('stroke-opacity', d => (EDGE_STYLES[d.type]?.opacity || 0.2))
    .attr('stroke-width', d => d.type === 'sanctions' ? 1.5 : 0.8)
    .attr('stroke-dasharray', d => EDGE_STYLES[d.type]?.dash || null)
    .attr('marker-end', d => d.directed ? `url(#arrow-${d.type})` : null)

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
    .call(d3.drag()
      .on('start', dragStart)
      .on('drag', dragging)
      .on('end', dragEnd))

  // Labels
  const label = g.append('g')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text(d => d.type === 'country' ? (d.data?.flag || d.label) : d.label)
    .attr('font-size', d => d.type === 'country' ? 11 : 9)
    .attr('fill', 'var(--text2)')
    .attr('text-anchor', 'middle')
    .attr('dy', d => radiusScale(d.size || 10) + 12)
    .style('pointer-events', 'none')

  // Tooltip
  node.on('mouseenter', (event, d) => {
    const tt = buildTooltip(d)
    tooltip.value = { show: true, title: tt.title, body: tt.body }
    const [x, y] = d3.pointer(event, containerEl.value)
    if (tooltipEl.value) {
      tooltipEl.value.style.left = (x + 14) + 'px'
      tooltipEl.value.style.top  = (y - 10) + 'px'
    }
    d3.select(event.currentTarget).attr('stroke', '#fff').attr('stroke-width', 2)
  })
  .on('mouseleave', (event) => {
    tooltip.value.show = false
    d3.select(event.currentTarget).attr('stroke', 'rgba(255,255,255,0.15)').attr('stroke-width', 1)
  })

  // Force simulation
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges)
      .id(d => d.id)
      .distance(d => {
        if (d.type === 'trade') return 120
        if (d.type === 'alliance') return 80
        if (d.type === 'institution_member') return 100
        return 90
      }))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => radiusScale(d.size || 10) + 6))
    .on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
      label
        .attr('x', d => d.x)
        .attr('y', d => d.y)
    })

  function dragStart(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    d.fx = d.x; d.fy = d.y
  }
  function dragging(event, d) {
    d.fx = event.x; d.fy = event.y
  }
  function dragEnd(event, d) {
    if (!event.active) simulation.alphaTarget(0)
    d.fx = null; d.fy = null
  }
}

watch(() => store.worldGraph, (graph) => {
  if (graph) render(graph)
}, { deep: true })

onMounted(() => {
  store.fetchWorldGraph()

  resizeObserver = new ResizeObserver(() => {
    if (store.worldGraph) render(store.worldGraph)
  })
  if (containerEl.value) resizeObserver.observe(containerEl.value)
})

onBeforeUnmount(() => {
  if (simulation) simulation.stop()
  if (resizeObserver) resizeObserver.disconnect()
})
</script>

<style scoped>
.world-graph {
  position: relative; width: 100%; height: 100%; min-height: 400px;
  background: var(--bg2); border: 1px solid var(--border); border-radius: 10px;
  overflow: hidden;
}
.world-graph svg { display: block; width: 100%; height: 100%; }
.wg-loading {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: var(--text3);
}
.wg-tooltip {
  position: absolute; pointer-events: none; z-index: 10;
  background: rgba(13,18,32,0.95); border: 1px solid var(--border2); border-radius: 6px;
  padding: 10px 12px; max-width: 220px;
}
.tt-title { font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.tt-body { font-size: 10px; color: var(--text2); line-height: 1.5; }
</style>
