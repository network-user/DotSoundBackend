import {
  useEffect,
  useState,
  type MouseEvent,
} from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { isTelegram, tg } from '@/lib/telegram'
import { useToast } from '@/components/ui/Toast'
import type {
  ImportJobResponse,
  OAuthLinkedProvider,
} from '@/types/api'

export type ImportPlatform = 'spotify' | 'vk'

interface Props {
  open: boolean
  platform: ImportPlatform
  onClose: () => void
  /** After user chooses “by link” — open the URL modal from the parent */
  onPickByLink: () => void
  /**
   * Account import (OAuth already done or not needed) produced a scannable
   * job; parent should apply it like a URL import result.
   */
  onAccountScanReady: (job: ImportJobResponse) => void
}

const TITLES: Record<ImportPlatform, string> = {
  spotify: 'Spotify',
  vk: 'VK Музыка',
}

const LINK_BLURBS: Record<ImportPlatform, string> = {
  spotify:
    'Подойдёт публичный плейлист или альбом (open.spotify.com). ' +
    'Ссылка не даёт доступа к вашим «Сохранённым» — для этого подключите аккаунт.',
  vk:
    'Подойдут ссылки на альбом, плейлист или публичную коллекцию на VK. ' +
    'Свой каталог в приложении — через вход в аккаунт.',
}

const ACCOUNT_BLURBS: Record<ImportPlatform, string> = {
  spotify:
    'Импортируем треки из библиотеки Spotify: сохранённые треки (после ' +
    'согласия в окне входа).',
  vk:
    'Импортируем аудио, доступные вашему профилю VK (после согласия ' +
    'и входа).',
}

function openOAuthUrlInApp(url: string) {
  try {
    if (
      isTelegram() &&
      typeof (tg as { openLink?: (u: string) => void })
        .openLink === 'function'
    ) {
      ;(tg as { openLink: (u: string) => void }).openLink(url)
      return
    }
  } catch {
    /* fall through */
  }
  window.location.assign(url)
}

function oauthProvider(
  p: ImportPlatform,
): OAuthLinkedProvider {
  return p === 'spotify' ? 'spotify' : 'vk'
}

function accountErrorMessage(
  e: unknown,
  platform: ImportPlatform,
): string {
  const r =
    e instanceof Error ? e.message : String(e)
  const lower = r.toLowerCase()
  if (lower.includes('503') || r.includes('not configured')) {
    return (
      'Вход через ' +
      TITLES[platform] +
      ' сейчас недоступен. Используйте вариант с ссылкой ' +
      'или попробуйте позже.'
    )
  }
  if (
    lower.includes('not connected') ||
    r.includes('не подключ') ||
    r.toLowerCase().includes('account is not connected')
  ) {
    return 'Сначала войдите через сервис — откроется окно входа.'
  }
  if (r.length && r.length < 200) return r
  return 'Не удалось запустить импорт. Попробуйте ссылку или позже.'
}

export function PlatformImportMethodModal({
  open,
  platform,
  onClose,
  onPickByLink,
  onAccountScanReady,
}: Props) {
  const toast = useToast()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, submitting, onClose])

  useEffect(() => {
    if (!open) {
      setError('')
      setSubmitting(false)
    }
  }, [open])

  if (!open) return null

  const handleBackdrop = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !submitting) onClose()
  }

  const handleByLink = () => {
    if (submitting) return
    onClose()
    onPickByLink()
  }

  const handleByAccount = async () => {
    if (submitting) return
    setError('')
    setSubmitting(true)
    const provider = oauthProvider(platform)
    try {
      const list = await api.getLinkedAccounts()
      const acc = list.find(
        a => a.provider === provider,
      )
      if (acc?.connected) {
        const j =
          platform === 'spotify'
            ? await api.startSpotifyAccountImport({
                source: 'liked',
              })
            : await api.startVkAccountImport({ source: 'liked' })
        if (j.status === 'failed') {
          setError(
            j.tracks_data?.error_message
              || 'Сервис не вернул треки. Попробуйте по ссылке.',
          )
          setSubmitting(false)
          return
        }
        onClose()
        onAccountScanReady(j)
        setSubmitting(false)
        return
      }
      const { auth_url: authUrl } =
        await api.startLinkedAccountConnect(provider)
      onClose()
      setSubmitting(false)
      toast.info('Откроется страница входа. После возврата снова ' +
        'запустите импорт и выберите «вход в аккаунт».')
      openOAuthUrlInApp(authUrl)
    } catch (e) {
      setError(accountErrorMessage(e, platform))
      setSubmitting(false)
    }
  }

  const name = TITLES[platform]

  return (
    <div className="modal" onClick={handleBackdrop}>
      <div className="modal-content">
        <div className="modal-header">
          <h3>Как импортировать из {name}</h3>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn"
            ariaLabel="Закрыть"
            onClick={onClose}
            disabled={submitting}
          >
            <Icon name="x" size={18} />
          </MotionPress>
        </div>
        <p className="modal-hint">{LINK_BLURBS[platform]}</p>
        <p
          className="modal-hint"
          style={{ marginTop: 8 }}
        >
          {ACCOUNT_BLURBS[platform]}
        </p>
        {error && <div className="form-error">{error}</div>}
        <div className="rf-import-modal-actions">
          <MotionPress
            type="button"
            variant="primary"
            haptic="medium"
            className="btn-primary"
            disabled={submitting}
            onClick={handleByLink}
          >
            Вставить ссылку
          </MotionPress>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="medium"
            className="btn-secondary"
            disabled={submitting}
            onClick={() => {
              void handleByAccount()
            }}
          >
            {submitting
              ? '…'
              : 'Войти в аккаунт ' + name}
          </MotionPress>
        </div>
      </div>
    </div>
  )
}
