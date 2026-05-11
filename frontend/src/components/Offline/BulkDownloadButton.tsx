import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import {
  downloadTracksBulk,
  isOfflineCacheSupported,
  type BulkDownloadProgress,
  type CacheSource,
} from '@/lib/offlineCache'
import type { Track } from '@/types/api'

interface Props {
  tracks: Track[] | null
  source?: CacheSource
  pinned?: boolean
  variant?: 'ghost' | 'primary'
  className?: string
}

export function BulkDownloadButton({
  tracks,
  source = 'manual',
  pinned = true,
  variant = 'ghost',
  className,
}: Props) {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] =
    useState<BulkDownloadProgress | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(
    () => () => {
      abortRef.current?.abort()
      abortRef.current = null
    },
    [],
  )

  if (!isOfflineCacheSupported()) return null
  const eligible = (tracks ?? []).filter(
    (it) => it.access_mode !== 'third_party_stream',
  )
  if (!tracks || eligible.length === 0) return null

  const handleClick = async () => {
    if (busy && abortRef.current) {
      abortRef.current.abort()
      return
    }
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setBusy(true)
    setProgress(null)
    try {
      const result = await downloadTracksBulk(eligible, {
        source,
        pinned,
        signal: ctrl.signal,
        onProgress: setProgress,
      })
      if (result.aborted) {
        showIsland({
          kind: 'toast',
          title: t(
            'offline.bulk.cancelled',
            'Скачивание отменено ({{ok}}/{{total}})',
            { ok: result.ok, total: eligible.length },
          ),
          durationMs: 2800,
        })
      } else if (result.failed > 0) {
        showIsland({
          kind: 'toast',
          title: t(
            'offline.bulk.partial',
            'Скачано {{ok}} из {{total}} ({{failed}} не удалось)',
            {
              ok: result.ok,
              total: eligible.length,
              failed: result.failed,
            },
          ),
          durationMs: 3500,
        })
      } else {
        showIsland({
          kind: 'toast',
          title: t(
            'offline.bulk.done',
            'Скачано: {{ok}} • Пропущено: {{skipped}}',
            {
              ok: result.ok,
              skipped: result.skipped,
            },
          ),
          durationMs: 2800,
        })
      }
    } catch {
      showIsland({
        kind: 'error',
        title: t(
          'offline.bulk.failed',
          'Не удалось скачать пакет',
        ),
      })
    } finally {
      abortRef.current = null
      setBusy(false)
      setProgress(null)
    }
  }

  const label = busy
    ? progress
      ? `${progress.done} / ${progress.total}`
      : '…'
    : t('offline.bulk.downloadAll', 'Скачать все')

  return (
    <MotionPress
      variant={variant}
      haptic={busy ? 'selection' : 'light'}
      className={className}
      onClick={() => {
        void handleClick()
      }}
      title={
        busy
          ? t(
              'offline.bulk.cancelHint',
              'Нажмите, чтобы отменить',
            )
          : undefined
      }
    >
      <Icon name={busy ? 'x' : 'download'} size={16} />
      <span>{label}</span>
    </MotionPress>
  )
}
