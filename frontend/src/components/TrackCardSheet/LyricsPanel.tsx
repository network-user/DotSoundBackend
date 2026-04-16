import {
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import { useLyricsTask } from '@/store/lyricsTaskStore'
import { Icon } from '@/components/Icon/Icon'
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
  const [showSync, setShowSync] = useState(true)
  const activeRef = useRef<HTMLDivElement>(null)
  const [devOpen, setDevOpen] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)

  const {
    generating,
    stage,
    genStatus,
    taskId: activeTaskId,
    startedAt,
    debugLog,
    startGeneration,
    clearTask,
    clearDebugLog,
  } = useLyricsTask(trackId)

  useEffect(() => {
    if (forceEdit) {
      setEditing(true)
    }
  }, [forceEdit])

  useEffect(() => {
    if (genStatus === 'found' && !lyrics) {
      api
        .getLyrics(trackId)
        .then((updated) => {
          setLyrics(updated)
        })
        .catch((err) => {
          console.error(
            'Failed to load lyrics after detection:',
            err,
          )
        })
    }
  }, [genStatus, trackId, lyrics])

  useEffect(() => {
    if (!hasLyrics) return
    setLoading(true)
    api
      .getLyrics(trackId)
      .then(setLyrics)
      .catch(() =>
        setError(
          t(
            'lyrics.notFound',
            'Не удалось загрузить',
          ),
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

  useEffect(() => {
    if (devOpen && logEndRef.current) {
      logEndRef.current.scrollIntoView({
        behavior: 'smooth',
      })
    }
  }, [devOpen, debugLog.length])

  const handleGenerate = async (
    withSync: boolean,
  ) => {
    try {
      await startGeneration(withSync)
    } catch {
      setError(
        t(
          'lyrics.notFound',
          'Не удалось запустить определение',
        ),
      )
    }
  }

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

  const elapsed = startedAt
    ? ((Date.now() - startedAt) / 1000).toFixed(1)
    : '0'

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

  const stageProgress: Record<string, number> = {
    searching: 25,
    downloading_audio: 50,
    processing: 75,
    saving: 95,
  }
  const progressPct = generating
    ? stageProgress[stage ?? ''] ?? 10
    : lyricsLoading
      ? 100
      : 0

  const lyricsLoading =
    genStatus === 'found' && !lyrics

  if (
    generating ||
    lyricsLoading ||
    (devOpen && debugLog.length > 0)
  )
    return (
      <div
        className="lyrics-panel"
        style={{ position: 'relative' }}
      >
        <div className="lyrics-generating">
          <div
            style={{
              width: '100%',
              height: 3,
              borderRadius: 2,
              background:
                'rgba(255,255,255,0.08)',
              overflow: 'hidden',
              marginBottom: 12,
            }}
          >
            <div
              style={{
                width: `${progressPct}%`,
                height: '100%',
                borderRadius: 2,
                background:
                  'rgba(255,255,255,0.5)',
                transition:
                  'width 0.6s ease-in-out',
              }}
            />
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span
              style={{
                fontSize: 12,
                color: 'rgba(255,255,255,0.4)',
              }}
            >
              {generating
                ? t(
                    'lyrics.generating',
                    'Определение...',
                  )
                : lyricsLoading
                  ? t(
                      'lyrics.generating',
                      'Загрузка...',
                    )
                  : ''}
            </span>
            <button
              onClick={() =>
                setDevOpen((v) => !v)
              }
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 2,
                display: 'flex',
                alignItems: 'center',
                color: 'rgba(255,255,255,0.7)',
              }}
            >
              <Icon
                name="settings"
                size={16}
              />
            </button>
          </div>
        </div>
        {devOpen && (
          <div
            style={{
              background: 'rgba(10,10,10,0.95)',
              border:
                '1px solid rgba(255,255,255,0.12)',
              borderRadius: 10,
              padding: '8px 10px',
              fontSize: 10,
              fontFamily: 'monospace',
              color: 'rgba(255,255,255,0.7)',
              maxHeight: '40vh',
              overflow: 'auto',
              marginTop: 8,
              backdropFilter: 'blur(8px)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginBottom: 6,
                flexWrap: 'wrap',
              }}
            >
              <span
                style={{
                  fontWeight: 700,
                  color: '#fff',
                  fontSize: 11,
                }}
              >
                DevTools — Lyrics
              </span>
              <span
                style={{
                  padding: '1px 5px',
                  borderRadius: 4,
                  fontSize: 9,
                  background: generating
                    ? 'rgba(250,204,21,0.2)'
                    : 'rgba(74,222,128,0.2)',
                  color: generating
                    ? '#facc15'
                    : '#4ade80',
                }}
              >
                {generating ? 'RUNNING' : 'DONE'}
              </span>
              <button
                onClick={() => clearDebugLog()}
                style={{
                  marginLeft: 'auto',
                  background:
                    'rgba(255,255,255,0.08)',
                  border: 'none',
                  color: 'rgba(255,255,255,0.5)',
                  borderRadius: 4,
                  padding: '2px 6px',
                  fontSize: 9,
                  cursor: 'pointer',
                }}
              >
                Clear
              </button>
              <button
                onClick={() => setDevOpen(false)}
                style={{
                  background:
                    'rgba(255,255,255,0.08)',
                  border: 'none',
                  color: 'rgba(255,255,255,0.5)',
                  borderRadius: 4,
                  padding: '2px 6px',
                  fontSize: 9,
                  cursor: 'pointer',
                }}
              >
                Close
              </button>
            </div>
            <div
              style={{
                color: 'rgba(255,255,255,0.4)',
                fontSize: 9,
                marginBottom: 4,
              }}
            >
              task: {activeTaskId ?? '-'}
              {' | '}
              elapsed: {elapsed}s
              {' | '}
              stage: {stage ?? '-'}
            </div>
            <div
              style={{
                borderTop:
                  '1px solid rgba(255,255,255,0.08)',
                paddingTop: 4,
              }}
            >
              {debugLog.map((line, i) => (
                <div
                  key={i}
                  style={{
                    padding: '1px 0',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                  }}
                >
                  {line}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        )}
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
            <div
              style={{
                display: 'flex',
                gap: 8,
                flexWrap: 'wrap',
                marginTop: 8,
              }}
            >
              <button
                className="btn-secondary"
                onClick={() => {
                  clearTask()
                  handleGenerate(false)
                }}
              >
                {t(
                  'lyrics.detectText',
                  'Определить текст',
                )}
              </button>
              {hasAudio && (
                <button
                  className="btn-secondary"
                  onClick={() => {
                    clearTask()
                    handleGenerate(true)
                  }}
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
                {t(
                  'lyrics.edit',
                  'Редактировать',
                )}
              </button>
            </div>
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
