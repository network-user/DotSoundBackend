import '@/lib/i18n'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AdminProvider } from '@/components/Admin/AdminContext'
import { LikesProvider } from '@/store/LikesContext'
import { PlayerProvider } from '@/store/PlayerContext'
import { App } from './App'
import './styles/global.css'
import './styles/animations.css'

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(regs => {
    regs.forEach(r => r.unregister())
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
