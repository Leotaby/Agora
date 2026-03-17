import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import HomeView from './views/HomeView.vue'
import SimulationView from './views/SimulationView.vue'
import WorldView from './views/WorldView.vue'
import BankingView from './views/BankingView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',             component: HomeView       },
    { path: '/simulate',     component: SimulationView },
    { path: '/simulate/:id', component: SimulationView },
    { path: '/world',        component: WorldView      },
    { path: '/banking',      component: BankingView    },
  ]
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
