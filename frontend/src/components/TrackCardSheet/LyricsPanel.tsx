import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import {
  usePlayerActions,
  usePlayerState,
} from '@/store/PlayerContext'
import { useLyricsTask } from '@/store/lyricsTaskStore'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import type { LyricsResponse } from '@/types/api'
import { LyricsEditor } from './LyricsEditor'

function clampPct(value: number): number {
  return Math.min(100, Math.max(0, value))
}

interface Props {
  trackId: number
  isOwner: boolean
  hasLyrics: boolean
  hasAudio?: boolean
  forceEdit?: boolean
  catalogType?: string | null
}

export function LyricsPanel({
  trackId,
  isOwner,
  hasLyrics,
  hasAudio = true,
  forceEdit,
  catalogType,
}: Props) {
  const { t } = useTranslation()
  const { currentTime, duration } = usePlayerState()
  const { seek } = usePlayerActions()
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
  const [selectedLang, setSelectedLang] =
    useState<string>('original')
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
  const isExternalRef = catalogType === 'external_reference'
  const canEdit = isExternalRef ? isAdmin : isOwner

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
    setSelectedLang('original')
  }, [trackId])

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
    let idx = -1
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
  const translationItems = lyrics?.translations ?? []
  const selectedTranslation =
    selectedLang === 'original'
      ? null
      : translationItems.find(
          (x) => x.language_code === selectedLang,
        ) ?? null
  const plainTextToRender =
    selectedTranslation?.translated_text ??
    lyrics?.plain_text ??
    ''
  const firstLineLeadInMs =
    showSync &&
    lyrics?.synced_lines?.length &&
    activeIdx < 0
      ? Math.max(0, lyrics.synced_lines[0].time_ms - adjustedMs)
      : null

  const lineProgressPct = (lineIndex: number): number => {
    const lines = lyrics?.synced_lines
    if (!lines || lineIndex < 0) return 0
    const current = lines[lineIndex]
    const next = lines[lineIndex + 1]
    const endMs =
      next?.time_ms ??
      (duration ? duration * 1000 : current.time_ms + 3500)
    const spanMs = Math.max(1, endMs - current.time_ms)
    return clampPct(
      ((adjustedMs - current.time_ms) / spanMs) * 100,
    )
  }

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
  const providerDiagnostic =
    [...debugLog]
      .reverse()
      .find((line) =>
        /(failed:|ERROR|HTTP \d{3}|Outbound[A-Za-z]+Error|invalid JSON|no lyrics container|empty text|rejected by artist validation)/i.test(
          line,
        ),
      ) ?? null

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
  if (error && !(canEdit && !lyrics))
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

  if (!lyrics && canEdit) {
    const wasNotFound =
      genStatus === 'not_found' ||
      genStatus === 'error'

    return (
      <div className="lyrics-panel">
        <div className="lyrics-empty-state">
          {(wasNotFound || error) && (
            <p className="lyrics-empty-msg">
              {error ||
                providerDiagnostic ||
                t(
                  'lyrics.notFound',
                  'Текст не определён',
                )}
            </p>
          )}

          <div className="lyrics-choice-grid">
            {lyricsChoiceStep === 'root' ? (
              <>
                <MotionPress
                  type="button"
                  variant="subtle"
                  haptic="light"
                  className="lyrics-choice-btn"
                  onClick={() => {
                    setLyricsChoiceStep('auto')
                  }}
                >
                  <Icon name="sparkle" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      {t(
                        'lyrics.detectAuto',
                        'Определить автоматически',
                      )}
                    </span>
                    <span className="lyrics-choice-hint">
                      {t(
                        'lyrics.detectAutoHint',
                        'Авто + Дебаг режимы',
                      )}
                    </span>
                  </div>
                </MotionPress>

                <MotionPress
                  type="button"
                  variant="subtle"
                  haptic="light"
                  className="lyrics-choice-btn"
                  onClick={() => setEditing(true)}
                >
                  <Icon name="text" size={22} />
                  <div>
                    <span className="lyrics-choice-label">
                      {t(
                        'lyrics.enterManually',
                        'Ввести вручную',
                      )}
                    </span>
                    <span className="lyrics-choice-hint">
                      {t(
                        'lyrics.enterManuallyHint',
                        'Текст с таймкодами или без',
                      )}
                    </span>
                  </div>
                </MotionPress>
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
  if (canEdit && lyricsChoiceStep === 'redefine') {
    return (
      <div className="lyrics-panel">
        <div className="lyrics-empty-state">
          <p className="lyrics-empty-msg">
            {t(
              'lyrics.redefineHeader',
              'Выберите сценарий переопределения',
            )}
          </p>
          <div className="lyrics-choice-grid">
            <MotionPress
              type="button"
              variant="subtle"
              haptic="light"
              className="lyrics-choice-btn"
              onClick={() => handleRedefine(false)}
            >
              <Icon name="sparkle" size={22} />
              <div>
                <span className="lyrics-choice-label">
                  {t(
                    'lyrics.redefineTextOnly',
                    'Только текст',
                  )}
                </span>
                <span className="lyrics-choice-hint">
                  {t(
                    'lyrics.redefineTextOnlyHint',
                    'Без таймкодов',
                  )}
                </span>
              </div>
            </MotionPress>

            <MotionPress
              type="button"
              variant="subtle"
              haptic="light"
              className={
                hasAudio
                  ? 'lyrics-choice-btn'
                  : 'lyrics-choice-btn lyrics-choice-btn--disabled'
              }
              onClick={() => handleRedefine(true)}
              disabled={!hasAudio}
            >
              <Icon name="sparkle" size={22} />
              <div>
                <span className="lyrics-choice-label">
                  {t(
                    'lyrics.redefineWithTiming',
                    'Текст + таймкоды',
                  )}
                </span>
                <span className="lyrics-choice-hint">
                  {!hasAudio
                    ? t(
                        'lyrics.redefineNeedsAudio',
                        'Требуется аудиофайл',
                      )
                    : t(
                        'lyrics.redefineWithTimingHint',
                        'С синхронизацией',
                      )}
                </span>
              </div>
            </MotionPress>

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

                <MotionPress
                  type="button"
                  variant="subtle"
                  haptic="light"
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
                </MotionPress>

                <MotionPress
                  type="button"
                  variant="subtle"
                  haptic="light"
                  className={
                    hasAudio
                      ? 'lyrics-choice-btn'
                      : 'lyrics-choice-btn lyrics-choice-btn--disabled'
                  }
                  onClick={() =>
                    handleRedefine(true, true)
                  }
                  disabled={!hasAudio}
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
                </MotionPress>
              </>
            )}

            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary lyrics-choice-back"
              onClick={() => setLyricsChoiceStep('root')}
            >
              {t('common.back', 'Назад')}
            </MotionPress>
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
        <div className="lyrics-panel-heading">
          <span className="lyrics-panel-title">
            {t('lyrics.title', 'Lyrics')}
          </span>
          {hasSyncData && (
            <span className="lyrics-sync-badge">
              {lyrics.sync_quality === 'word'
                ? t('lyrics.syncQualityWord', 'Word sync')
                : t('lyrics.syncQualityLine', 'Line sync')}
            </span>
          )}
        </div>
        <div className="lyrics-panel-controls">
          {hasSyncData && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              className={`lyrics-mode-btn${
                showSync ? ' is-active' : ''
              }`}
              onClick={() => setShowSync((v) => !v)}
              aria-pressed={showSync}
            >
              <Icon name="eq" size={14} />
              <span>
                {t('lyrics.showSync', 'Line highlighting')}
              </span>
            </MotionPress>
          )}
          {hasWordTimes && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="selection"
              className={`lyrics-mode-btn${
                karaokeActive ? ' is-active' : ''
              }`}
              onClick={() => {
                const next = !karaoke
                setKaraoke(next)
                try {
                  localStorage.setItem(
                    'setting-lyrics-karaoke',
                    next ? '1' : '0',
                  )
                } catch {}
              }}
              aria-pressed={karaokeActive}
            >
              <Icon name="text" size={14} />
              <span>
                {t('lyrics.karaokeMode', 'Karaoke')}
              </span>
            </MotionPress>
          )}
          {translationItems.length > 0 && (
            <select
              className="lyrics-lang-select"
              value={selectedLang}
              onChange={(e) =>
                setSelectedLang(e.target.value)
              }
              aria-label={t(
                'redesign.player.lyricsLanguage',
                'Language',
              )}
            >
              <option value="original">
                {t(
                  'redesign.player.lyricsOriginal',
                  'Original',
                )}
              </option>
              {translationItems.map((tr) => (
                <option
                  key={tr.language_code}
                  value={tr.language_code}
                >
                  {tr.language_code.toUpperCase()}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="lyrics-content">
        {firstLineLeadInMs !== null && firstLineLeadInMs > 250 && (
          <button
            type="button"
            className="lyrics-lead-in"
            onClick={() =>
              handleLineClick(lyrics.synced_lines![0].time_ms)
            }
          >
            <span className="lyrics-lead-in__label">
              {t('lyrics.startsIn', 'Starts in')}
            </span>
            <span className="lyrics-lead-in__time">
              {(firstLineLeadInMs / 1000).toFixed(1)}
            </span>
          </button>
        )}
        {showSync && hasSyncData
          ? lyrics.synced_lines!.map((line, i) => {
              const isActive = i === activeIdx
              const isPast = activeIdx > i
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
                  className={`lyrics-line${
                    isActive ? ' lyrics-line-active' : ''
                  }${isPast ? ' lyrics-line-past' : ''}${
                    (line.confidence ?? 0) < 0.5
                      ? ' lyrics-line-uncertain'
                      : ''
                  }`}
                  style={
                    {
                      ['--lyrics-line-progress']: `${
                        isActive ? lineProgressPct(i) : 0
                      }%`,
                    } as CSSProperties
                  }
                  aria-current={isActive ? 'true' : undefined}
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
                {plainTextToRender}
              </pre>
            )}
      </div>

      {(isAdmin || isOwner) && (
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

      {canEdit && (
        <div className="lyrics-actions">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="lyrics-action-btn"
            onClick={() => setEditing(true)}
          >
            <Icon name="text" size={15} />
            {t('lyrics.edit', 'Редактировать')}
          </MotionPress>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="lyrics-action-btn"
            onClick={() => setLyricsChoiceStep('redefine')}
          >
            <Icon name="sparkle" size={15} />
            {t('lyrics.redefine', 'Переопределить')}
          </MotionPress>
          {!hasSyncData && hasAudio && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="lyrics-action-btn"
              onClick={() => handleGenerate(true)}
            >
              <Icon name="eq" size={15} />
              {t('lyrics.addSync', 'Таймкоды')}
            </MotionPress>
          )}
          <MotionPress
            type="button"
            variant="ghost"
            haptic="medium"
            className="lyrics-action-btn lyrics-action-btn--danger"
            onClick={handleDelete}
          >
            <Icon name="trash" size={15} />
            {t('lyrics.delete', 'Удалить')}
          </MotionPress>
        </div>
      )}
    </div>
  )
}
