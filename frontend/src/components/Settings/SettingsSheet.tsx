import { useState } from 'react'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'

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

  if (!open) return null

  const handleEq = () => {
    onClose()
    openEq()
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

          <button
            className="settings-item disabled"
            disabled
          >
            <Icon name="text" size={20} />
            <span>Язык</span>
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
