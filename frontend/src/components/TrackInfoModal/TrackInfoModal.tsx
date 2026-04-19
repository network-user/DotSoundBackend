import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import type { TrackInfoResponse } from '@/types/api'

interface Props {
  trackId: number
  title: string
  artist: string | null
  onClose: () => void
}

const POLL_INTERVAL_MS = 2000
const POLL_MAX_ATTEMPTS = 30

export function TrackInfoModal({ trackId, title, artist, onClose }: Props) {
  const { t } = useTranslation()
  const [info, setInfo] = useState<TrackInfoResponse | null>(null)
  const [error, setError] = useState(false)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptsRef = useRef(0)

  const stopPoll = () => {
    if (pollRef.current) {
      clearTimeout(pollRef.current)
      pollRef.current = null
    }
  }

  const scheduleNextPoll = (currentInfo: TrackInfoResponse) => {
    if (currentInfo.status !== 'fetching' && currentInfo.status !== 'pending') return
    if (attemptsRef.current >= POLL_MAX_ATTEMPTS) return
    attemptsRef.current += 1
    pollRef.current = setTimeout(async () => {
      try {
        const updated = await api.getTrackInfo(trackId)
        setInfo(updated)
        scheduleNextPoll(updated)
      } catch {
        setError(true)
      }
    }, POLL_INTERVAL_MS)
  }

  useEffect(() => {
    let cancelled = false
    attemptsRef.current = 0

    api.getTrackInfo(trackId).then((data) => {
      if (cancelled) return
      setInfo(data)
      scheduleNextPoll(data)
    }).catch(() => {
      if (!cancelled) setError(true)
    })

    return () => {
      cancelled = true
      stopPoll()
    }
  }, [trackId])

  const handleRefresh = async () => {
    stopPoll()
    setError(false)
    attemptsRef.current = 0
    try {
      const data = await api.refreshTrackInfo(trackId)
      setInfo(data)
      scheduleNextPoll(data)
    } catch {
      setError(true)
    }
  }

  const formatDate = (iso: string | null) => {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString()
    } catch {
      return ''
    }
  }

  const isFetching = !info || info.status === 'fetching' || info.status === 'pending'

  return (
    <div
      className="track-info-modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="track-info-modal">
        <div className="track-info-modal-header">
          <div className="track-info-modal-title">
            <span className="track-info-modal-track-name">{title}</span>
            {artist && (
              <span className="track-info-modal-artist">— {artist}</span>
            )}
          </div>
          <button
            className="track-info-modal-close icon-btn"
            onClick={onClose}
            aria-label={t('common.close', { defaultValue: 'Закрыть' })}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="track-info-modal-body">
          {error && (
            <div className="track-info-error">
              {t('trackInfo.error', { defaultValue: 'Ошибка загрузки информации' })}
            </div>
          )}

          {!error && isFetching && (
            <div className="track-info-loading">
              <div className="spinner" />
              <span>{t('trackInfo.loading', { defaultValue: 'Получение информации...' })}</span>
            </div>
          )}

          {!error && !isFetching && info?.status === 'not_found' && (
            <div className="track-info-not-found">
              {t('trackInfo.notFound', { defaultValue: 'Информация не найдена' })}
            </div>
          )}

          {!error && !isFetching && info?.status === 'failed' && (
            <div className="track-info-error">
              {t('trackInfo.failed', { defaultValue: 'Не удалось получить информацию' })}
            </div>
          )}

          {!error && info?.status === 'done' && info.content && (
            <div className="track-info-content">
              {info.content.split('\n').map((line, i) => (
                <p key={i} className={line === '' ? 'track-info-spacer' : undefined}>
                  {line}
                </p>
              ))}
            </div>
          )}
        </div>

        <div className="track-info-modal-footer">
          {info?.fetched_at && (
            <span className="track-info-cached-at">
              {t('trackInfo.cachedAt', {
                defaultValue: 'Обновлено {{date}}',
                date: formatDate(info.fetched_at),
              })}
            </span>
          )}
          {info?.status === 'done' || info?.status === 'not_found' || info?.status === 'failed' ? (
            <button
              className="btn-secondary track-info-refresh-btn"
              onClick={handleRefresh}
            >
              <Icon name="refresh" size={14} />
              {t('trackInfo.refresh', { defaultValue: 'Обновить' })}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
