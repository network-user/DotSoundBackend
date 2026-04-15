import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import type { LyricsResponse } from '@/types/api'
import { LyricsEditor } from './LyricsEditor'

interface Props {
  trackId: number
  isOwner: boolean
  hasLyrics: boolean
  hasAudio?: boolean
  forceEdit?: boolean
}

export function LyricsPanel({
  trackId,
  isOwner,
  hasLyrics,
  hasAudio = true,
  forceEdit,
}: Props) {
  const { t } = useTranslation()
  const { currentTime, duration, seek } =
    usePlayer()
  const [lyrics, setLyrics] =
    useState<LyricsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<
    string | null
  >(null)
  const [editing, setEditing] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [genStatus, setGenStatus] = useState<
    string | null
  >(null)
  const [showSync, setShowSync] = useState(true)
  const activeRef = useRef<HTMLDivElement>(null)
  const pollRef = useRef<ReturnType<
    typeof setInterval
  > | null>(null)

  useEffect(() => {
    if (forceEdit || (!hasLyrics && isOwner)) {
      setEditing(true)
    }
  }, [forceEdit, hasLyrics, isOwner])

  useEffect(() => {
    if (!hasLyrics) return
    setLoading(true)
    api
      .getLyrics(trackId)
      .then(setLyrics)
      .catch(() =>
        setError(
          t('lyrics.notFound', 'Не удалось загрузить'),
        ),
      )
      .finally(() => setLoading(false))
  }, [trackId, hasLyrics, t])

  const activeIdx = (() => {
    if (
      !showSync ||
      !lyrics?.synced_lines?.length
    )
      return -1
    const ms = currentTime * 1000
    let idx = 0
    for (
      let i = 0;
      i < lyrics.synced_lines.length;
      i++
    ) {
      if (lyrics.synced_lines[i].time_ms <= ms)
        idx = i
      else break
    }
    return idx
  })()

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    }
  }, [activeIdx])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  const handleGenerate = useCallback(
    async (withSync: boolean) => {
      setGenerating(true)
      setGenStatus(null)
      try {
        const { task_id } =
          await api.generateLyrics(
            trackId,
            withSync,
          )
        pollRef.current = setInterval(async () => {
          try {
            const { status } =
              await api.getLyricsAutoStatus(
                trackId,
                task_id,
              )
            if (status === 'found') {
              stopPolling()
              const updated =
                await api.getLyrics(trackId)
              setLyrics(updated)
              setGenerating(false)
              setGenStatus(null)
            } else if (
              status === 'not_found' ||
              status === 'error'
            ) {
              stopPolling()
              setGenerating(false)
              setGenStatus(status)
            }
          } catch {
            stopPolling()
            setGenerating(false)
            setGenStatus('error')
          }
        }, 2000)
      } catch {
        setGenerating(false)
        setGenStatus('error')
      }
    },
    [trackId, stopPolling],
  )

  const handleLineClick = (timeMs: number) => {
    if (!duration) return
    const pct = (timeMs / 1000 / duration) * 100
    seek(pct)
  }

  const handleSaved = (
    updated: LyricsResponse,
  ) => {
    setLyrics(updated)
    setEditing(false)
  }

  if (loading)
    return (
      <div className="lyrics-panel">
        <div className="loader" />
      </div>
    )
  if (error)
    return (
      <div className="lyrics-panel lyrics-error">
        {error}
      </div>
    )

  if (editing) {
    return (
      <LyricsEditor
        trackId={trackId}
        existingLyrics={lyrics}
        onSaved={handleSaved}
        onCancel={() =>
          (hasLyrics || lyrics) &&
          setEditing(false)
        }
      />
    )
  }

  if (generating)
    return (
      <div className="lyrics-panel">
        <div className="lyrics-generating">
          <div className="loader" />
          <span>
            {t(
              'lyrics.generating',
              'Определение...',
            )}
          </span>
        </div>
      </div>
    )

  if (
    genStatus === 'not_found' ||
    genStatus === 'error'
  ) {
    return (
      <div className="lyrics-panel">
        <div className="lyrics-not-found">
          <span>
            {t(
              'lyrics.notFound',
              'Текст не определён',
            )}
          </span>
          {isOwner && (
            <button
              className="btn-secondary"
              onClick={() => setEditing(true)}
            >
              {t('lyrics.edit', 'Редактировать')}
            </button>
          )}
        </div>
      </div>
    )
  }

  if (!lyrics && isOwner) {
    return (
      <div className="lyrics-panel">
        <div className="lyrics-auto-actions">
          <button
            className="btn-secondary"
            onClick={() => handleGenerate(false)}
          >
            {t(
              'lyrics.detectText',
              'Определить текст',
            )}
          </button>
          {hasAudio && (
            <button
              className="btn-secondary"
              onClick={() => handleGenerate(true)}
            >
              {t(
                'lyrics.detectTextWithSync',
                'Определить текст + таймкоды',
              )}
            </button>
          )}
          <button
            className="btn-text"
            onClick={() => setEditing(true)}
          >
            {t('lyrics.edit', 'Редактировать')}
          </button>
        </div>
      </div>
    )
  }

  if (!lyrics) return null

  const hasSyncData =
    lyrics.synced_lines &&
    lyrics.synced_lines.length > 0

  return (
    <div className="lyrics-panel">
      <div className="lyrics-panel-header">
        <span className="lyrics-panel-title">
          {t('lyrics.title', 'Текст')}
        </span>
        <div className="lyrics-panel-controls">
          {hasSyncData && (
            <label className="lyrics-sync-toggle">
              <input
                type="checkbox"
                checked={showSync}
                onChange={(e) =>
                  setShowSync(e.target.checked)
                }
              />
              <span>
                {t(
                  'lyrics.showSync',
                  'Подсветка по строкам',
                )}
              </span>
            </label>
          )}
          {isOwner && (
            <button
              className="btn-text btn-sm"
              onClick={() => setEditing(true)}
            >
              {t('lyrics.edit', 'Редактировать')}
            </button>
          )}
          {isOwner &&
            !hasSyncData &&
            hasAudio && (
              <button
                className="btn-text btn-sm"
                onClick={() =>
                  handleGenerate(true)
                }
              >
                {t(
                  'lyrics.addSync',
                  'Добавить таймкоды',
                )}
              </button>
            )}
        </div>
      </div>

      <div className="lyrics-content">
        {showSync && hasSyncData
          ? lyrics.synced_lines!.map(
              (line, i) => (
                <div
                  key={i}
                  ref={
                    i === activeIdx
                      ? activeRef
                      : null
                  }
                  className={`lyrics-line${i === activeIdx ? ' lyrics-line-active' : ''}`}
                  onClick={() =>
                    handleLineClick(line.time_ms)
                  }
                >
                  {line.text}
                </div>
              ),
            )
          : (
              <pre className="lyrics-plain">
                {lyrics.plain_text}
              </pre>
            )}
      </div>
    </div>
  )
}
