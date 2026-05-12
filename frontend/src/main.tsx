import { i18nReady } from '@/lib/i18n'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AdminProvider } from '@/components/Admin/AdminContext'
import { LikesProvider } from '@/store/LikesContext'
import { PlayerProvider } from '@/store/PlayerContext'
import { PrefetchProvider } from '@/store/PrefetchContext'
import { SoundProvider } from '@/store/SoundContext'
import { api } from '@/lib/api'
import { installGlassPerformanceClass } from '@/lib/glassPerformance'
import { installViewportListener } from '@/lib/telegram'
import { installOnlineFlush } from '@/lib/pendingEvents'
import { captureBeforeInstallPrompt } from '@/lib/pwaInstall'
import { LazyMotion, domAnimation } from '@/lib/motion'
import { OfflineErrorBoundary } from '@/components/OfflineErrorBoundary/OfflineErrorBoundary'
import { App } from './App'
import './styles/tokens.css'
import './styles/global.css'
import './styles/animations.css'
import './styles/components.css'
import './styles/redesign-shared.css'
import './styles/redesign-player.css'
import './styles/redesign-nav.css'
import './styles/redesign-home.css'
import './styles/redesign-library.css'
import './styles/redesign-tracks.css'
import './styles/redesign-artist.css'
import './styles/redesign-recap.css'
import './styles/redesign-upload.css'
import './styles/redesign-track-edit.css'
import './styles/redesign-profile.css'
import './styles/onboarding.css'
import './styles/legal.css'

installGlassPerformanceClass()
installViewportListener()
installOnlineFlush()
captureBeforeInstallPrompt()

window.addEventListener('unhandledrejection', (event) => {
  console.error('[unhandledRejection]', event.reason)
})
window.addEventListener('error', (event) => {
  if (event.error) console.error('[globalError]', event.error)
})
// When Vite's module preloads 404 (stale chunks after a new deployment),
// a hard reload is the only reliable recovery.
window.addEventListener('vite:preloadError', () => {
  window.location.reload()
})

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

void i18nReady.then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <OfflineErrorBoundary>
        <LazyMotion features={domAnimation}>
          <BrowserRouter basename="/mini_app">
            <SoundProvider>
              <AdminProvider>
                <PrefetchProvider>
                  <PlayerProvider>
                    <LikesProvider>
                      <App />
                    </LikesProvider>
                  </PlayerProvider>
                </PrefetchProvider>
              </AdminProvider>
            </SoundProvider>
          </BrowserRouter>
        </LazyMotion>
      </OfflineErrorBoundary>
    </StrictMode>,
  )
})
