import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { LikesProvider } from '@/store/LikesContext'
import { PlayerProvider } from '@/store/PlayerContext'
import { App } from './App'
import './styles/global.css'
import './styles/animations.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PlayerProvider>
      <LikesProvider>
        <App />
      </LikesProvider>
    </PlayerProvider>
  </StrictMode>,
)
