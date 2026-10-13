import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Initialise auth session before mounting so the nav guard has a session
const authStore = useAuthStore()
authStore.init().then(() => {
  app.mount('#app')
})
