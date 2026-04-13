import { useState } from 'react'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import { TwoFASettings } from './TwoFASettings'

interface Props {
  open: boolean
  onClose: () => void
  onLogout: () => void
}

export function SettingsSheet({
  open,
  onClose,
  onLogout,
}: Props) {
  const { openEq } = usePlayer()
  const [videoEnabled, setVideoEnabled] =
    useState(
      () =>
        localStorage.getItem(
          'setting-video-enabled',
        ) !== 'false',
    )
  const [monoEnabled, setMonoEnabled] =
    useState(
      () =>
        localStorage.getItem(
          'setting-monochrome',
        ) === 'true',
    )
  const [twoFAEnabled, setTwoFAEnabled] =
    useState(false)

  if (!open) return null

  const handleEq = () => {
    onClose()
    openEq()
  }

  const handleVideoToggle = () => {
    const next = !videoEnabled
    setVideoEnabled(next)
    localStorage.setItem(
      'setting-video-enabled',
      String(next),
    )
  }

  const handleMonoToggle = () => {
    const next = !monoEnabled
    setMonoEnabled(next)
    localStorage.setItem(
      'setting-monochrome',
      String(next),
    )
    document.body.classList.toggle(
      'monochrome',
      next,
    )
  }

  const handleOpenBrowser = () => {
    window.open(
      window.location.href,
      '_blank',
    )
  }

  return (
    <div
      className="settings-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget)
          onClose()
      }}
    >
      <div className="settings-sheet">
        <div className="settings-handle" />
        <div className="settings-header">
          <span className="settings-title">
            Настройки
          </span>
          <button
            className="icon-btn"
            onClick={onClose}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="settings-list">
          <button
            className="settings-item"
            onClick={handleEq}
          >
            <Icon name="eq" size={20} />
            <span>Эквалайзер</span>
            <Icon
              name="chevron"
              size={16}
              className="settings-chevron"
            />
          </button>

          <div
            className="settings-item"
            onClick={handleVideoToggle}
          >
            <Icon name="video" size={20} />
            <span>Видеоклипы</span>
            <div
              className={`settings-toggle${videoEnabled ? ' on' : ''}`}
            >
              <div className="settings-toggle-dot" />
            </div>
          </div>

          <div
            className="settings-item"
            onClick={handleMonoToggle}
          >
            <Icon name="moon" size={20} />
            <span>Монохром</span>
            <div
              className={`settings-toggle${monoEnabled ? ' on' : ''}`}
            >
              <div className="settings-toggle-dot" />
            </div>
          </div>

          <button
            className="settings-item"
            onClick={handleOpenBrowser}
          >
            <Icon name="maximize" size={20} />
            <span>Открыть в браузере</span>
            <Icon
              name="chevron"
              size={16}
              className="settings-chevron"
            />
          </button>

          <div className="settings-hint">
            Для управления музыкой с экрана
            блокировки откройте .sound в
            браузере
          </div>

          <TwoFASettings
            enabled={twoFAEnabled}
            onToggle={setTwoFAEnabled}
          />

          <button
            className="settings-item disabled"
            disabled
          >
            <Icon
              name="volume-high"
              size={20}
            />
            <span>Качество звука</span>
            <span className="settings-badge">
              скоро
            </span>
          </button>

          <button className="settings-item">
            <Icon name="info" size={20} />
            <span>О приложении</span>
            <span className="settings-version">
              v0.1.0
            </span>
          </button>
        </div>

        <div className="settings-footer">
          <button
            className="settings-logout"
            onClick={onLogout}
          >
            <Icon name="log-out" size={18} />
            Выйти
          </button>
        </div>
      </div>
    </div>
  )
}
