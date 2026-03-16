<template>
  <div class="app-shell">
    <nav class="topnav">
      <router-link to="/" class="nav-logo">
        NEXUS <span class="eq">=</span> <span class="ht">HumanTwin</span>
      </router-link>
      <div class="nav-links">
        <router-link to="/">Home</router-link>
        <router-link to="/simulate">Simulate</router-link>
        <a href="https://github.com/Leotaby/nexus-sim" target="_blank">GitHub ↗</a>
      </div>
    </nav>
    <main>
      <router-view />
    </main>
  </div>
</template>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #080c14;
  --bg2: #0d1220;
  --bg3: #111827;
  --border: rgba(255,255,255,0.07);
  --border2: rgba(255,255,255,0.13);
  --text: #e8eaf0;
  --text2: #8b90a0;
  --text3: #50576a;
  --accent: #4f8ef7;
  --accent2: #2dd4a0;
  --amber: #f0a832;
  font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
}

body { background: var(--bg); color: var(--text); min-height: 100vh; }

.app-shell { display: flex; flex-direction: column; min-height: 100vh; }

.topnav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 32px; height: 56px;
  background: rgba(8,12,20,0.9); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 50;
}

.nav-logo {
  font-size: 16px; font-weight: 600; text-decoration: none; color: var(--text);
  letter-spacing: 0.06em;
}
.nav-logo .eq  { color: var(--text3); }
.nav-logo .ht  { color: var(--accent2); }

.nav-links { display: flex; gap: 28px; }
.nav-links a {
  font-size: 12px; color: var(--text2); text-decoration: none;
  letter-spacing: 0.04em; transition: color 0.15s;
}
.nav-links a:hover, .nav-links a.router-link-active { color: var(--text); }

main { flex: 1; padding: 0 32px 64px; max-width: 1440px; margin: 0 auto; width: 100%; }
</style>
