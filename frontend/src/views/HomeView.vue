<template>
  <div class="home">
    <div class="hero">
      <div class="eyebrow">PhD Research Project · Economics &amp; Finance</div>
      <h1>NEXUS <span class="eq">=</span> <span class="ht">HumanTwin</span></h1>
      <p class="tagline">A living synthetic economy of human agents.<br>Predicting markets from households to central banks.</p>
      <div class="hero-actions">
        <router-link to="/simulate" class="btn-primary">Run a simulation →</router-link>
        <a href="https://github.com/Leotaby/nexus-sim" target="_blank" class="btn-secondary">View on GitHub ↗</a>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat" v-for="s in stats" :key="s.label">
        <div class="stat-num">{{ s.num }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <div class="tier-grid">
      <div class="tier-card" v-for="tier in tiers" :key="tier.id">
        <div class="tier-badge" :class="tier.cls">{{ tier.id }}</div>
        <div class="tier-name">{{ tier.name }}</div>
        <div class="tier-desc">{{ tier.desc }}</div>
        <div class="tier-meta">
          <span class="meta-item">Speed: {{ tier.speed }}</span>
          <span class="meta-item">Source: {{ tier.data }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const stats = [
  { num: "7",    label: "Agent tiers" },
  { num: "1M+",  label: "Max agents" },
  { num: "6",    label: "CB institutions" },
  { num: "5",    label: "Target papers" },
]

const tiers = [
  { id: "T1", cls: "t-cb",   name: "Central banks",            desc: "Fed, ECB, BoJ, BoE, SNB, PBoC. Set policy rates. The macro shock generators.",               speed: "Instant",      data: "Taylor rule" },
  { id: "T2", cls: "t-hf",   name: "Macro hedge funds",        desc: "Carry, momentum, fundamental. Primary channel of price discovery after a shock.",           speed: "2 min",        data: "CFTC CoT" },
  { id: "T3", cls: "t-bk",   name: "Commercial banks",         desc: "FX market makers. See client order flow before it hits the market.",                         speed: "Seconds",      data: "BIS survey" },
  { id: "T4", cls: "t-am",   name: "Institutional AMs",        desc: "Pension funds, SWFs. Mechanical FX rebalancing — slow but enormous flows.",                  speed: "1–3 days",     data: "Pension surveys" },
  { id: "T5", cls: "t-pr",   name: "Professional retail",      desc: "Technical analysis, economic calendars. Moderate literacy, leveraged accounts.",             speed: "Hours",        data: "OANDA positioning" },
  { id: "T6", cls: "t-or",   name: "Ordinary retail",          desc: "Social media-driven, FOMO, loss-averse. The irrational component that sustains disconnect.", speed: "Days",         data: "ESMA loss data" },
  { id: "T7", cls: "t-hh",   name: "Households",               desc: "Never trade FX directly. Their savings and consumption ARE the macro fundamentals.",        speed: "Weeks",        data: "ECB HFCS" },
]
</script>

<style scoped>
.home { padding-top: 60px; }

.hero { text-align: center; padding-bottom: 64px; }
.eyebrow { font-size: 11px; letter-spacing: 0.1em; color: var(--accent2); margin-bottom: 20px; }
h1 { font-size: clamp(36px, 7vw, 72px); font-weight: 700; letter-spacing: -0.01em; margin-bottom: 20px; }
.eq { color: var(--text3); }
.ht { color: var(--accent2); }
.tagline { font-size: 16px; color: var(--text2); line-height: 1.7; margin-bottom: 36px; }
.hero-actions { display: flex; gap: 12px; justify-content: center; }

.btn-primary {
  font-size: 13px; padding: 12px 24px; border-radius: 8px;
  background: var(--accent); color: #080c14;
  text-decoration: none; font-weight: 600;
  transition: background 0.2s;
}
.btn-primary:hover { background: #6ba3fa; }
.btn-secondary {
  font-size: 13px; padding: 11px 24px; border-radius: 8px;
  border: 1px solid var(--border2); color: var(--text2);
  text-decoration: none; transition: all 0.2s;
}
.btn-secondary:hover { border-color: var(--text2); color: var(--text); }

.stats-row {
  display: flex; gap: 0; margin-bottom: 56px;
  border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
}
.stat {
  flex: 1; padding: 20px; text-align: center;
  border-right: 1px solid var(--border);
}
.stat:last-child { border-right: none; }
.stat-num { font-size: 28px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.stat-label { font-size: 11px; color: var(--text3); letter-spacing: 0.06em; }

.tier-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.tier-card {
  border: 1px solid var(--border); border-radius: 10px; padding: 18px;
  background: var(--bg2); transition: border-color 0.15s;
}
.tier-card:hover { border-color: var(--border2); }
.tier-badge {
  display: inline-block; font-size: 10px; font-weight: 600;
  padding: 3px 10px; border-radius: 4px; margin-bottom: 10px;
  letter-spacing: 0.06em;
}
.t-cb  { background: rgba(240,96,96,0.15);  color: #f06060; }
.t-hf  { background: rgba(155,127,244,0.15);color: #9b7ff4; }
.t-bk  { background: rgba(45,212,160,0.15); color: #2dd4a0; }
.t-am  { background: rgba(79,142,247,0.15); color: #4f8ef7; }
.t-pr  { background: rgba(240,168,50,0.15); color: #f0a832; }
.t-or  { background: rgba(255,255,255,0.07);color: var(--text3); }
.t-hh  { background: rgba(240,96,96,0.08);  color: #e88080; }

.tier-name { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.tier-desc { font-size: 12px; color: var(--text2); line-height: 1.6; margin-bottom: 12px; }
.tier-meta { display: flex; flex-direction: column; gap: 3px; }
.meta-item { font-size: 11px; color: var(--text3); }
</style>
