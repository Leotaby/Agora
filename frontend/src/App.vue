<template>
  <nav>
    <div class="nav-inner">
      <router-link to="/" class="nav-brand">AGORA</router-link>
      <div class="nav-links">
        <router-link to="/banking">Simulation</router-link>
        <a href="https://github.com/Leotaby/Agora" target="_blank">GitHub ↗</a>
      </div>
    </div>
  </nav>
  <router-view />
</template>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0a0e1a; color: #e0e0e0; font-family: 'JetBrains Mono', monospace; }
nav { height: 48px; border-bottom: 1px solid #1e2435; display: flex; align-items: center; padding: 0 24px; }
.nav-inner { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.nav-brand { font-size: 16px; font-weight: 600; color: #e0e0e0; text-decoration: none; letter-spacing: 0.1em; }
.nav-links { display: flex; gap: 24px; }
.nav-links a { font-size: 13px; color: #888; text-decoration: none; }
.nav-links a:hover { color: #e0e0e0; }
</style>
