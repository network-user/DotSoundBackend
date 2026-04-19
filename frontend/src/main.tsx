import '@/lib/i18n'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AdminProvider } from '@/components/Admin/AdminContext'
import { LikesProvider } from '@/store/LikesContext'
import { PlayerProvider } from '@/store/PlayerContext'
import { api } from '@/lib/api'
import { installViewportListener } from '@/lib/telegram'
import { App } from './App'
import './styles/tokens.css'
import './styles/global.css'
import './styles/animations.css'
import './styles/components.css'

installViewportListener()

api.restoreSession()

const params = new URLSearchParams(window.location.search)
const forceUnregisterSw = params.get('nosw') === '1'

if (
  (import.meta.env.DEV || forceUnregisterSw) &&
  'serviceWorker' in navigator
) {
  navigator.serviceWorker
    .getRegistrations()
    .then((regs) => {
      regs.forEach((r) => r.unregister())
    })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename="/mini_app">
      <AdminProvider>
        <PlayerProvider>
          <LikesProvider>
            <App />
          </LikesProvider>
        </PlayerProvider>
      </AdminProvider>
    </BrowserRouter>
  </StrictMode>,
)

requestAnimationFrame(() => {
  window.dispatchEvent(new Event('app-ready'))
})
