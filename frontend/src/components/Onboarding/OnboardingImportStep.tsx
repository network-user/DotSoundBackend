import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { YandexMusicUrlModal } from '@/components/Import/YandexMusicUrlModal'
import type { OnboardingStatus } from '@/types/api'

interface Props {
  onDone: () => void
}

const SOON = [
  { id: 'vk', label: 'VK Музыка', icon: 'source-vk' as const },
  { id: 'spotify', label: 'Spotify', icon: 'source-spotify' as const },
  { id: 'soundcloud', label: 'SoundCloud', icon: 'source-soundcloud' as const },
]

export function OnboardingImportStep({ onDone }: Props) {
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [yandexOpen, setYandexOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api
      .getOnboardingStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  const finish = async () => {
    setBusy(true)
    try {
      await api.acknowledgeOnboardingImport()
      onDone()
    } catch {
      setErr('Не удалось сохранить')
    }
    setBusy(false)
  }

  const onTelegram = async () => {
    setErr(null)
    setBusy(true)
    try {
      await api.startTelegramImport()
    } catch {
      setErr('Не удалось связаться с ботом')
    } finally {
      setBusy(false)
    }
    try {
      await api.acknowledgeOnboardingImport()
      onDone()
    } catch {
      setErr('Не удалось сохранить')
    }
  }

  const onYandexUrl = async (url: string) => {
    setErr(null)
    setBusy(true)
    try {
      const j = await api.startYandexMusicImport(url)
      if (j.status === 'failed') {
        throw new Error('scan_failed')
      }
      setYandexOpen(false)
      await api.acknowledgeOnboardingImport()
      onDone()
    } catch {
      setErr('Не удалось прочитать плейлист')
    }
    setBusy(false)
  }

  if (!status) {
    return (
      <div className="onboarding-step">
        <div className="onboarding-import-skeleton">
          <div className="loader" />
          <p className="onboarding-subtitle">Проверяем профиль…</p>
        </div>
      </div>
    )
  }

  const showTg = status.can_import_from_telegram

  return (
    <div className="onboarding-step">
      <h2 className="onboarding-title">Перенесите свою музыку</h2>
      <p className="onboarding-subtitle">
        Импортируйте треки в .sound — или пропустите и настройте вкус
        вручную
      </p>
      {err && (
        <p className="form-error" style={{ marginBottom: 12 }}>
          {err}
        </p>
      )}

      <div className="onboarding-import-cards">
        {showTg && (
          <button
            type="button"
            className="onboarding-import-card"
            onClick={onTelegram}
            disabled={busy}
          >
            <span className="onboarding-import-card-icon">
              <Icon name="source-telegram" size={24} />
            </span>
            <span className="onboarding-import-card-title">Telegram</span>
            <span className="hint">Аудио из вашего профиля</span>
          </button>
        )}

        <button
          type="button"
          className="onboarding-import-card"
          onClick={() => setYandexOpen(true)}
          disabled={busy}
        >
          <span className="onboarding-import-card-icon">
            <Icon name="source-yandex" size={24} />
          </span>
          <span className="onboarding-import-card-title">
            Яндекс.Музыка
          </span>
          <span className="hint">Ссылка на плейлист или альбом</span>
        </button>

        {SOON.map(s => (
          <div
            key={s.id}
            className="onboarding-import-card disabled"
          >
            <span className="onboarding-import-card-icon">
              <Icon name={s.icon} size={24} />
            </span>
            <span className="onboarding-import-card-title">{s.label}</span>
            <span className="onboarding-import-soon">скоро</span>
          </div>
        ))}
      </div>

      <div className="onboarding-import-footer-btns">
        <button
          type="button"
          className="onboarding-skip"
          onClick={finish}
          disabled={busy}
        >
          Позже
        </button>
        <button
          type="button"
          className="onboarding-next"
          onClick={finish}
          disabled={busy}
        >
          {busy ? '…' : 'Далее к жанрам'}
        </button>
      </div>

      <YandexMusicUrlModal
        open={yandexOpen}
        onClose={() => setYandexOpen(false)}
        onScan={onYandexUrl}
      />
    </div>
  )
}
