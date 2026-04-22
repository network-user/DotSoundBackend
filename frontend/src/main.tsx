import '@/lib/i18n'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AdminProvider } from '@/components/Admin/AdminContext'
import { LikesProvider } from '@/store/LikesContext'
import { PlayerProvider } from '@/store/PlayerContext'
import { ToastProvider } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { installViewportListener } from '@/lib/telegram'
import { installOnlineFlush } from '@/lib/pendingEvents'
import { App } from './App'
import './styles/tokens.css'
import './styles/global.css'
import './styles/animations.css'
import './styles/components.css'

installViewportListener()
installOnlineFlush()

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
      <ToastProvider>
        <AdminProvider>
          <PlayerProvider>
            <LikesProvider>
              <App />
            </LikesProvider>
          </PlayerProvider>
        </AdminProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
)

requestAnimationFrame(() => {
  window.dispatchEvent(new Event('app-ready'))
})
