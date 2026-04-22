import {
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
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
  // При forceEdit (редактирование из карточки) нужно открыть редактор сразу,
  // а не после первого рендера useEffect.
  const [editing, setEditing] = useState(() =>
    Boolean(forceEdit),
  )
  const [lyricsChoiceStep, setLyricsChoiceStep] = useState<
    'root' | 'auto' | 'debug' | 'redefine'
  >('root')
  const [showSync, setShowSync] = useState(true)
  const [karaoke, setKaraoke] = useState<boolean>(
    () => localStorage.getItem('setting-lyrics-karaoke') === '1',
  )
  const [offsetMs] = useState<number>(() => {
    const raw = localStorage.getItem(
      'setting-lyrics-sync-offset-ms',
    )
    const n = raw ? Number(raw) : 0
    return Number.isFinite(n) ? n : 0
  })
  const activeRef = useRef<HTMLDivElement>(null)
  const [devOpen, setDevOpen] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const [
    lastRequestMeta,
    setLastRequestMeta,
  ] = useState<{
    mode: 'auto' | 'debug' | 'redefine'
    withSync: boolean
    debugTier: number | null
    bypassCache: boolean
  } | null>(null)
  const isAdmin = getIsAdmin()

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
    cancelGeneration,
    resumeTask,
    appendDebugLog,
  } = useLyricsTask(trackId)

  useEffect(() => {
    if (forceEdit) {
      setEditing(true)
    }
  }, [forceEdit])

  useEffect(() => {
    // После выхода из редактора возвращаемся к первому выбору
    if (!editing) setLyricsChoiceStep('root')
  }, [editing])

  useEffect(() => {
    setLyricsChoiceStep('root')
  }, [trackId, genStatus])

  useEffect(() => {
    if (genStatus === 'found' && !lyrics) {
      if (editing) return
      console.debug('[LyricsPanel] fetching lyrics after detection', { trackId })
      api
        .getLyrics(trackId)
        .then((updated) => {
          console.debug('[LyricsPanel] lyrics loaded', { chars: updated.plain_text?.length })
          appendDebugLog(
            `[client] lyrics loaded chars=${updated.plain_text?.length ?? 0} synced=${updated.synced_lines?.length ?? 0}`,
          )
          setLyrics(updated)
        })
        .catch((err) => {
          console.error(
            '[LyricsPanel] Failed to load lyrics after detection:',
            err,
          )
          const msg =
            err instanceof Error
              ? err.message
              : 'load failed'
          appendDebugLog(
            `[client] ERROR loading lyrics after detection: ${msg}`,
          )
          clearTask()
        })
    }
  }, [
    appendDebugLog,
    clearTask,
    editing,
    genStatus,
    trackId,
    lyrics,
  ])

  useEffect(() => {
    if (!hasLyrics) return
    if (editing) return
    setLoading(true)
    api
      .getLyrics(trackId)
      .then(setLyrics)
      .catch(() => {
        // 404/ошибка загрузки не должна ломать UI —
        // считаем, что текста нет и показываем выбор/редактор.
        setLyrics(null)
        setError(null)
      })
      .finally(() => setLoading(false))
  }, [trackId, hasLyrics, t, editing])

  const adjustedMs = currentTime * 1000 + offsetMs

  const activeIdx = (() => {
    if (
      !showSync ||
      !lyrics?.synced_lines?.length
    )
      return -1
    let idx = 0
    for (
      let i = 0;
      i < lyrics.synced_lines.length;
      i++
    ) {
      if (lyrics.synced_lines[i].time_ms <= adjustedMs)
        idx = i
      else break
    }
    return idx
  })()

  const hasWordTimes = !!lyrics?.synced_lines?.some(
    (l) => l.word_times && l.word_times.length > 0,
  )
  const karaokeActive =
    karaoke && hasWordTimes && lyrics?.sync_quality === 'word'

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
    withSync?: boolean,
    debugTier?: number,
  ) => {
    const requestMeta = {
      mode: debugTier ? 'debug' : 'auto',
      withSync: Boolean(withSync),
      debugTier: debugTier ?? null,
      bypassCache: false,
    } as const
    setLastRequestMeta(requestMeta)
    try {
      await startGeneration(withSync, debugTier)
      appendDebugLog(
        `[client] request accepted mode=${requestMeta.mode} with_sync=${requestMeta.withSync} debug_stage=${requestMeta.debugTier ?? '-'}`,
      )
    } catch {
      // Важно: не блокируем UI. Если авто-определение не стартовало
      // (например, 422/валидация), пользователь должен иметь возможность
      // выбрать "ввести вручную" или попробовать снова.
      setError(null)
      setLyrics(null)
      clearTask()
      setLyricsChoiceStep('root')
    }
  }

  const handleLineClick = (timeMs: number) => {
    if (!duration) return
    const pct = (timeMs / 1000 / duration) * 100
    seek(pct)
  }

  const handleDelete = async () => {
    try {
      await api.deleteLyrics(trackId)
      setLyrics(null)
      clearTask()
      setLyricsChoiceStep('root')
    } catch {
      // ignore
    }
  }

  const handleRedefine = async (
    withSync: boolean = false,
    bypassCache: boolean = false,
  ) => {
    const requestMeta = {
      mode: 'redefine',
      withSync,
      debugTier: null,
      bypassCache,
    } as const
    setLastRequestMeta(requestMeta)
    try {
      setLyricsChoiceStep('root')
      const { task_id } = await api.redefineLyrics(
        trackId,
        withSync,
        bypassCache,
      )
      setLyrics(null)
      resumeTask(task_id, { withSync, bypassCache })
      appendDebugLog(
        `[client] redefine queued with_sync=${withSync} bypass_cache=${bypassCache} admin=${isAdmin}`,
      )
    } catch {
      setLyricsChoiceStep('root')
    }
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
  const lastRequestLabel = lastRequestMeta
    ? `mode=${lastRequestMeta.mode} | with_sync=${lastRequestMeta.withSync} | debug_stage=${lastRequestMeta.debugTier ?? '-'} | bypass_cache=${lastRequestMeta.bypassCache}`
    : '-'

  if (editing) {
    return (
      <LyricsEditor
        trackId={trackId}
        existingLyrics={lyrics}
        onSaved={handleSaved}
        onCancel={() => setEditing(false)}
      />
    )
  }

  if (loading)
    return (
      <div className="lyrics-panel">
        <div className="loader" />
      </div>
    )
  if (error && !(isOwner && !lyrics))
    return (
      <div className="lyrics-panel lyrics-error">
        {error}
      </div>
    )

  const lyricsLoading =
    genStatus === 'found' && !lyrics

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

            {(generating || lyricsLoading) && (
              <button
                onClick={() => {
                  if (generating) {
                    cancelGeneration()
                  } else {
                    clearTask()
                  }
                }}
                style={{
                  background: 'rgba(239,68,68,0.2)',
                  border: '1px solid rgba(239,68,68,0.5)',
                  color: '#ef4444',
                  borderRadius: 4,
                  padding: '2px 8px',
                  fontSize: 11,
                  cursor: 'pointer',
                  fontWeight: 500,
                }}
              >
                Отмена
              </button>
            )}

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
              {' | '}
              status: {genStatus ?? '-'}
              {' | '}
              role: {isAdmin ? 'admin' : 'owner'}
              {' | '}
              {lastRequestLabel}
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

  if (!lyrics && isOwner) {
    const wasNotFound =
      genStatus === 'not_found' ||
      genStatus === 'error'

    return (
      <div className="lyrics-panel">
        <div className="lyrics-empty-state">
          {(wasNotFound || error) && (
            <p className="lyrics-empty-msg">
              {error ||
                t(
                  'lyrics.notFound',
                  'Текст не определён',
                )}
            </p>
          )}

          <div className="lyrics-choice-grid">
            {lyricsChoiceStep === 'root' ? (
              <>
                <button
                  className="lyrics-choice-btn"
                  onClick={() => {
                    setLyricsChoiceStep('auto')
                  }}
                >
                  <Icon name="sparkle" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Определить автоматически
                    </span>
                    <span className="lyrics-choice-hint">
                      Авто + Дебаг режимы
                    </span>
                  </div>
                </button>

                <button
                  className="lyrics-choice-btn"
                  onClick={() => setEditing(true)}
                >
                  <Icon name="text" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Ввести вручную
                    </span>
                    <span className="lyrics-choice-hint">
                      Текст с таймкодами или без
                    </span>
                  </div>
                </button>
              </>
            ) : (
              <>
                {/* Автоматические режимы */}
                <div style={{ gridColumn: '1 / -1', fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 4 }}>
                  Автоматические режимы:
                </div>

                <button
                  className="lyrics-choice-btn"
                  onClick={() => {
                    if (wasNotFound) clearTask()
                    handleGenerate(false)
                  }}
                >
                  <Icon name="sparkle" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Авто: только текст
                    </span>
                    <span className="lyrics-choice-hint">
                      Без таймкодов
                    </span>
                  </div>
                </button>

                <button
                  className="lyrics-choice-btn"
                  onClick={() => {
                    if (wasNotFound) clearTask()
                    handleGenerate(true)
                  }}
                  disabled={!hasAudio}
                  style={
                    !hasAudio
                      ? { opacity: 0.5, cursor: 'not-allowed' }
                      : undefined
                  }
                >
                  <Icon name="sparkle" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Авто: текст + таймкоды
                    </span>
                    <span className="lyrics-choice-hint">
                      {!hasAudio
                        ? 'Требуется аудиофайл'
                        : 'С синхронизацией'}
                    </span>
                  </div>
                </button>

                {/* Дебаг режимы */}
                <div style={{ gridColumn: '1 / -1', fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 12, marginBottom: 4 }}>
                  Дебаг режимы (тестирование отдельных этапов):
                </div>

                <button
                  className="lyrics-choice-btn"
                  onClick={() => {
                    if (wasNotFound) clearTask()
                    handleGenerate(undefined, 1)
                  }}
                >
                  <Icon name="settings" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Дебаг: Сценарий 1
                    </span>
                    <span className="lyrics-choice-hint">
                      Тестирование вариант A
                    </span>
                  </div>
                </button>

                <button
                  className="lyrics-choice-btn"
                  onClick={() => {
                    if (wasNotFound) clearTask()
                    handleGenerate(undefined, 2)
                  }}
                >
                  <Icon name="settings" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Дебаг: Сценарий 2
                    </span>
                    <span className="lyrics-choice-hint">
                      Тестирование вариант B
                    </span>
                  </div>
                </button>

                <button
                  className="lyrics-choice-btn"
                  onClick={() => {
                    if (!hasAudio) return
                    if (wasNotFound) clearTask()
                    handleGenerate(undefined, 3)
                  }}
                  disabled={!hasAudio}
                  style={
                    !hasAudio
                      ? { opacity: 0.5, cursor: 'not-allowed' }
                      : undefined
                  }
                >
                  <Icon name="settings" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Дебаг: Сценарий 3
                    </span>
                    <span className="lyrics-choice-hint">
                      {!hasAudio
                        ? 'Требуется аудиофайл'
                        : 'Тестирование вариант C'}
                    </span>
                  </div>
                </button>

                <button
                  className="btn-secondary"
                  onClick={() =>
                    setLyricsChoiceStep('root')
                  }
                >
                  Назад
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    )
  }

  // Redefine chooser — shown over existing lyrics
  if (isOwner && lyricsChoiceStep === 'redefine') {
    return (
      <div className="lyrics-panel">
        <div className="lyrics-empty-state">
          <p className="lyrics-empty-msg">
            Выберите сценарий переопределения
          </p>
          <div className="lyrics-choice-grid">
            <button
              className="lyrics-choice-btn"
              onClick={() => handleRedefine(false)}
            >
              <Icon name="sparkle" size={22} />
              <div>
                <span className="lyrics-choice-label">
                  Только текст
                </span>
                <span className="lyrics-choice-hint">
                  Без таймкодов
                </span>
              </div>
            </button>

            <button
              className="lyrics-choice-btn"
              onClick={() => handleRedefine(true)}
              disabled={!hasAudio}
              style={!hasAudio ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
            >
              <Icon name="sparkle" size={22} />
              <div>
                <span className="lyrics-choice-label">
                  Текст + таймкоды
                </span>
                <span className="lyrics-choice-hint">
                  {!hasAudio ? 'Требуется аудиофайл' : 'С синхронизацией'}
                </span>
              </div>
            </button>

            {isAdmin && (
              <>
                <div
                  style={{
                    gridColumn: '1 / -1',
                    fontSize: 12,
                    color: 'rgba(255,255,255,0.5)',
                    marginTop: 12,
                    marginBottom: 4,
                  }}
                >
                  Админ-режим (обход кеша):
                </div>

                <button
                  className="lyrics-choice-btn"
                  onClick={() =>
                    handleRedefine(false, true)
                  }
                >
                  <Icon name="settings" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Админ: без кеша (текст)
                    </span>
                    <span className="lyrics-choice-hint">
                      Прямой запрос bypass_cache=true
                    </span>
                  </div>
                </button>

                <button
                  className="lyrics-choice-btn"
                  onClick={() =>
                    handleRedefine(true, true)
                  }
                  disabled={!hasAudio}
                  style={
                    !hasAudio
                      ? { opacity: 0.5, cursor: 'not-allowed' }
                      : undefined
                  }
                >
                  <Icon name="settings" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      Админ: без кеша + таймкоды
                    </span>
                    <span className="lyrics-choice-hint">
                      {!hasAudio
                        ? 'Требуется аудиофайл'
                        : 'С принудительным bypass_cache'}
                    </span>
                  </div>
                </button>
              </>
            )}

            <button
              className="btn-secondary"
              style={{ gridColumn: '1 / -1' }}
              onClick={() => setLyricsChoiceStep('root')}
            >
              Назад
            </button>
          </div>
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
        {hasWordTimes && (
          <label className="lyrics-sync-toggle">
            <input
              type="checkbox"
              checked={karaokeActive}
              onChange={(e) => {
                const next = e.target.checked
                setKaraoke(next)
                try {
                  localStorage.setItem(
                    'setting-lyrics-karaoke',
                    next ? '1' : '0',
                  )
                } catch {}
              }}
            />
            <span>
              {t('lyrics.karaokeMode', 'Караоке')}
            </span>
          </label>
        )}
      </div>

      <div className="lyrics-content">
        {showSync && hasSyncData
          ? lyrics.synced_lines!.map((line, i) => {
              const isActive = i === activeIdx
              let wordIdx = -1
              if (
                karaokeActive &&
                isActive &&
                line.word_times &&
                line.word_times.length > 0
              ) {
                for (let j = 0; j < line.word_times.length; j++) {
                  const w = line.word_times[j]
                  if (
                    adjustedMs >= w.start_ms &&
                    adjustedMs < w.start_ms + w.dur_ms
                  ) {
                    wordIdx = j
                    break
                  }
                }
              }
              return (
                <div
                  key={i}
                  ref={
                    isActive ? activeRef : null
                  }
                  className={`lyrics-line${isActive ? ' lyrics-line-active' : ''}${(line.confidence ?? 0) < 0.5 ? ' lyrics-line-uncertain' : ''}`}
                  onClick={() =>
                    handleLineClick(line.time_ms)
                  }
                  title={
                    (line.confidence ?? 0) < 0.5
                      ? 'Таймкод неточный'
                      : undefined
                  }
                >
                  {karaokeActive &&
                  line.word_times &&
                  line.word_times.length > 0 ? (
                    line.word_times.map((w, j) => (
                      <span
                        key={j}
                        className={`lyrics-word${j === wordIdx ? ' lyrics-word-active' : ''}${isActive && wordIdx >= 0 && j < wordIdx ? ' lyrics-word-past' : ''}`}
                      >
                        {w.text}{' '}
                      </span>
                    ))
                  ) : (
                    line.text
                  )}
                </div>
              )
            })
          : (
              <pre className="lyrics-plain">
                {lyrics.plain_text}
              </pre>
            )}
      </div>

      {isAdmin && (
        <div className="lyrics-debug-attribution">
          <div className="lyrics-debug-row">
            <span className="lyrics-debug-label">
              Источник текста:
            </span>
            <span className="lyrics-debug-value">
              {lyrics.source_name || '—'}
            </span>
          </div>
          <div className="lyrics-debug-row">
            <span className="lyrics-debug-label">
              Синхронизовал:
            </span>
            <span className="lyrics-debug-value">
              {lyrics.sync_source_name || '—'}
            </span>
          </div>
        </div>
      )}

      {isOwner && (
        <div className="lyrics-actions">
          <button
            className="lyrics-action-btn"
            onClick={() => setEditing(true)}
          >
            <Icon name="text" size={15} />
            {t('lyrics.edit', 'Редактировать')}
          </button>
          <button
            className="lyrics-action-btn"
            onClick={() => setLyricsChoiceStep('redefine')}
          >
            <Icon name="sparkle" size={15} />
            {t('lyrics.redefine', 'Переопределить')}
          </button>
          {!hasSyncData && hasAudio && (
            <button
              className="lyrics-action-btn"
              onClick={() => handleGenerate(true)}
            >
              <Icon name="eq" size={15} />
              {t('lyrics.addSync', 'Таймкоды')}
            </button>
          )}
          <button
            className="lyrics-action-btn lyrics-action-btn--danger"
            onClick={handleDelete}
          >
            <Icon name="trash" size={15} />
            {t('lyrics.delete', 'Удалить')}
          </button>
        </div>
      )}
    </div>
  )
}
