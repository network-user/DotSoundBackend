import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type {
  LinkedAccountInfo,
  OAuthLinkedProvider,
} from '@/types/api'

const LABELS: Record<OAuthLinkedProvider, string> = {
  spotify: 'Spotify',
  vk: 'VK',
  soundcloud: 'SoundCloud',
}

export function OAuthImportAccounts() {
  const [items, setItems] = useState<
    LinkedAccountInfo[] | null
  >(null)
  const [busy, setBusy] =
    useState<OAuthLinkedProvider | null>(null)

  const load = () => {
    api
      .getLinkedAccounts()
      .then(setItems)
      .catch(() => setItems([]))
  }

  useEffect(() => {
    load()
  }, [])

  const disconnect = async (p: OAuthLinkedProvider) => {
    setBusy(p)
    try {
      await api.disconnectLinkedAccount(p)
      load()
    } catch {
      /* ignore */
    } finally {
      setBusy(null)
    }
  }

  if (items === null) return null

  const connected = items.filter((x) => x.connected)

  if (connected.length === 0) return null

  return (
    <>
      <div
        className="settings-hint"
        style={{ marginTop: 12 }}
      >
        Сервисы импорта
      </div>
      {connected.map((a) => (
        <div
          key={a.provider}
          className="settings-item"
        >
          <span>
            {LABELS[a.provider as OAuthLinkedProvider] ??
              a.provider}
            {a.provider_username
              ? ` (${a.provider_username})`
              : ''}
          </span>
          <button
            type="button"
            className="settings-badge"
            disabled={busy === a.provider}
            onClick={() =>
              disconnect(
                a.provider as OAuthLinkedProvider,
              )
            }
            style={{
              cursor: 'pointer',
              background: 'var(--surface-2)',
            }}
          >
            {busy === a.provider ? '…' : 'Отвязать'}
          </button>
        </div>
      ))}
    </>
  )
}
