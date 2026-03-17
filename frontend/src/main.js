import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import BankingView from './views/BankingView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: BankingView },
    { path: '/banking', component: BankingView },
  ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')
