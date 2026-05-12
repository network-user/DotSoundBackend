import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import { createPortal } from 'react-dom'
import { api } from '@/lib/api'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { looksLikeLrc, parseLrc } from '@/lib/lrc'
import {
  saveLyricsDraft,
  loadLyricsDraft,
  clearLyricsDraft,
  type LyricsDraft,
} from '@/lib/lyricsDraft'
import type {
  LyricsResponse,
  SyncedLine,
} from '@/types/api'

interface Props {
  trackId?: number
  localAudioUrl?: string
  existingLyrics: LyricsResponse | null
  onSaved: (lyrics: LyricsResponse) => void
  onCancel: () => void
}

type Step = 'text' | 'sync'

function msToDisplay(ms: number): string {
  const sec = ms / 1000
  const m = Math.floor(sec / 60)
  const s = (sec % 60).toFixed(1).padStart(4, '0')
  return `${m}:${s}`
}

function formatDraftAge(
  savedAt: number,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const diffMs = Date.now() - savedAt
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return t('lyrics.editor.draftJustNow')
  if (mins < 60)
    return t('lyrics.editor.draftMinAgo', { count: mins })
  return t('lyrics.editor.draftHourAgo', {
    count: Math.floor(mins / 60),
  })
}

export function LyricsEditor({
  trackId,
  localAudioUrl,
  existingLyrics,
  onSaved,
  onCancel,
}: Props) {
  const { t } = useTranslation()
  const { currentTime, duration, isPlaying } =
    usePlayerState()
  const { track } = usePlayerMeta()
  const {
    playTrack,
    togglePlay,
    seek,
  } = usePlayerActions()

  const [step, setStep] = useState<Step>('text')
  const [plainText, setPlainText] = useState(
    existingLyrics?.plain_text ?? '',
  )
  const [lines, setLines] = useState<string[]>([])
  const [timecodes, setTimecodes] = useState<
    (number | null)[]
  >([])
  const [currentLine, setCurrentLine] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<
    { idx: number; prev: number | null }[]
  >([])
  const [autoDetectStarting, setAutoDetectStarting] =
    useState(false)
  const [autoDetectInfo, setAutoDetectInfo] = useState<
    string | null
  >(null)
  const [draftBanner, setDraftBanner] =
    useState<LyricsDraft | null>(null)

  const listRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)
  const lrcInputRef = useRef<HTMLInputElement>(null)
  const autosaveTimerRef = useRef<ReturnType<
    typeof setTimeout
  > | null>(null)
  const hasUserEdited = useRef(false)

  useEffect(() => {
    if (!trackId) return
    const draft = loadLyricsDraft(trackId)
    if (!draft || !draft.plainText.trim()) return
    const existingText = existingLyrics?.plain_text ?? ''
    if (draft.plainText !== existingText) {
      setDraftBanner(draft)
    }
  }, [])

  const scheduleAutosave = (
    text: string,
    synced: SyncedLine[] | null,
  ) => {
    if (!trackId || !hasUserEdited.current) return
    if (autosaveTimerRef.current)
      clearTimeout(autosaveTimerRef.current)
    autosaveTimerRef.current = setTimeout(() => {
      saveLyricsDraft(trackId, text, synced)
    }, 800)
  }

  useEffect(
    () => () => {
      if (autosaveTimerRef.current)
        clearTimeout(autosaveTimerRef.current)
    },
    [],
  )

  const handleTextChange = (
    e: ChangeEvent<HTMLTextAreaElement>,
  ) => {
    hasUserEdited.current = true
    const next = e.target.value
    setPlainText(next)
    scheduleAutosave(next, null)
  }

  const restoreDraft = (draft: LyricsDraft) => {
    hasUserEdited.current = true
    setPlainText(draft.plainText)
    setDraftBanner(null)
    if (trackId) saveLyricsDraft(trackId, draft.plainText, draft.syncedLines)
  }

  const discardDraft = () => {
    if (trackId) clearLyricsDraft(trackId)
    setDraftBanner(null)
  }

  const enterSync = () => {
    const split = plainText
      .split('\n')
      .filter((l) => l.trim())
    setLines(split)
    const existing = existingLyrics?.synced_lines ?? []
    setTimecodes(
      split.map((_, i) => existing[i]?.time_ms ?? null),
    )
    setCurrentLine(0)
    setHistory([])
    setStep('sync')
  }

  const markCurrent = () => {
    const ms = Math.round(currentTime * 1000)
    const idx = currentLine
    hasUserEdited.current = true
    setHistory((h) => [...h, { idx, prev: timecodes[idx] }])
    setTimecodes((prev) => {
      const next = [...prev]
      next[idx] = ms
      scheduleAutosave(
        plainText,
        lines.map((text, i) => ({
          time_ms: (i === idx ? ms : prev[i]) ?? 0,
          text,
        })),
      )
      return next
    })
    if (currentLine < lines.length - 1) {
      setCurrentLine((c) => c + 1)
    }
  }

  const undoLast = () => {
    if (!history.length) return
    const last = history[history.length - 1]
    setTimecodes((prev) => {
      const next = [...prev]
      next[last.idx] = last.prev
      return next
    })
    setCurrentLine(last.idx)
    setHistory((h) => h.slice(0, -1))
  }

  const jumpTo = (idx: number) => {
    setCurrentLine(idx)
    if (timecodes[idx] !== null) {
      const pct = duration
        ? (timecodes[idx]! / 1000 / duration) * 100
        : 0
      seek(pct)
    }
  }

  const seekRelative = (sec: number) => {
    if (!duration) return
    const target = Math.max(
      0,
      Math.min(duration, currentTime + sec),
    )
    seek((target / duration) * 100)
  }

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      })
    }
  }, [currentLine])

  const stampedIndex = useMemo(() => {
    if (!isPlaying) return -1
    const ms = Math.round(currentTime * 1000)
    let idx = -1
    for (let i = 0; i < timecodes.length; i++) {
      const tc = timecodes[i]
      if (tc !== null && tc <= ms) idx = i
      else if (tc !== null && tc > ms) break
    }
    return idx
  }, [currentTime, timecodes, isPlaying])

  useEffect(() => {
    if (step !== 'sync' || !isPlaying) return
    if (stampedIndex < 0) return
    setCurrentLine(stampedIndex)
  }, [step, isPlaying, stampedIndex])

  useEffect(() => {
    if (step !== 'sync') return
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      if (e.target instanceof HTMLTextAreaElement) return
      if (e.code === 'Space' && !e.shiftKey) {
        e.preventDefault()
        markCurrent()
      } else if (e.code === 'Space' && e.shiftKey) {
        e.preventDefault()
        undoLast()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step, currentLine, lines.length, history.length])

  const nudgeCurrent = (deltaMs: number) => {
    hasUserEdited.current = true
    setTimecodes((prev) => {
      const next = [...prev]
      const cur = next[currentLine]
      if (cur === null) return prev
      next[currentLine] = Math.max(0, cur + deltaMs)
      scheduleAutosave(
        plainText,
        lines.map((text, i) => ({
          time_ms: next[i] ?? 0,
          text,
        })),
      )
      return next
    })
  }

  useEffect(() => {
    if (step !== 'sync') return
    const root = document.documentElement
    root.classList.add('le-lyrics-sync-open')
    return () => {
      root.classList.remove('le-lyrics-sync-open')
    }
  }, [step])

  useEffect(() => {
    if (step === 'sync') {
      if (localAudioUrl) {
        playTrack(
          {
            id: -1,
            title: 'Preview',
            artist: '',
            genre: null,
            description: null,
            duration_seconds: 0,
            cover_key: null,
            play_count: 0,
            is_active: true,
            is_public: true,
            source: 'internal',
            catalog_type: 'ugc',
            access_mode: 'internal_stream',
            source_platform: null,
            sc_url: null,
            sc_uri: null,
            source_url: null,
            canonical_source_url: null,
            source_name: null,
            uploaded_by_id: null,
            video_key: null,
            waveform_data: null,
            created_at: '',
          },
          localAudioUrl,
        ).catch(() => {})
      } else if (track) {
        playTrack(track).catch(() => {})
      }
    }
  }, [step])

  const handleSaveText = async () => {
    if (!plainText.trim()) {
      setError(t('lyrics.editor.enterText'))
      return
    }
    if (localAudioUrl) {
      onSaved({
        track_id: 0,
        plain_text: plainText.trim(),
        synced_lines: null,
        source: 'manual',
        created_at: '',
        updated_at: '',
      })
      return
    }
    setSaving(true)
    setError(null)
    try {
      const saved = await api.saveLyrics(
        trackId!,
        plainText.trim(),
      )
      if (trackId) clearLyricsDraft(trackId)
      onSaved(saved)
    } catch {
      setError(t('lyrics.editor.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const handleSaveSync = async () => {
    const synced: SyncedLine[] = lines
      .map((text, i) => ({
        time_ms: timecodes[i] ?? 0,
        text,
      }))
      .sort((a, b) => a.time_ms - b.time_ms)

    if (localAudioUrl) {
      onSaved({
        track_id: 0,
        plain_text: plainText.trim(),
        synced_lines: synced,
        source: 'manual',
        created_at: '',
        updated_at: '',
      })
      return
    }
    setSaving(true)
    setError(null)
    try {
      const saved = await api.saveLyricsSync(trackId!, synced)
      if (trackId) clearLyricsDraft(trackId)
      onSaved(saved)
    } catch {
      setError(t('lyrics.editor.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const importLrcText = (text: string) => {
    const result = parseLrc(text)
    if (!result.lines.length) {
      setError(t('lyrics.editor.lrcEmpty'))
      return
    }
    const linesText = result.lines.map((l) => l.text)
    hasUserEdited.current = true
    setPlainText(linesText.join('\n'))
    setLines(linesText)
    setTimecodes(result.lines.map((l) => l.time_ms))
    setHistory([])
    setCurrentLine(0)
    setError(null)
    setStep('sync')
  }

  const handleLrcFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const raw = String(ev.target?.result ?? '')
      if (!looksLikeLrc(raw)) {
        setError(t('lyrics.editor.lrcInvalid'))
        return
      }
      importLrcText(raw)
    }
    reader.onerror = () =>
      setError(t('lyrics.editor.lrcInvalid'))
    reader.readAsText(file)
    e.target.value = ''
  }

  const handlePasteIntoTextarea = (
    e: React.ClipboardEvent<HTMLTextAreaElement>,
  ) => {
    const pasted = e.clipboardData.getData('text/plain')
    if (pasted && looksLikeLrc(pasted)) {
      e.preventDefault()
      importLrcText(pasted)
    }
  }

  const triggerAutoDetect = async () => {
    if (!trackId || autoDetectStarting) return
    setAutoDetectStarting(true)
    setAutoDetectInfo(null)
    setError(null)
    try {
      await api.generateLyrics(trackId, true)
      setAutoDetectInfo(t('lyrics.editor.autoDetectQueued'))
    } catch {
      setError(t('lyrics.editor.autoDetectError'))
    } finally {
      setAutoDetectStarting(false)
    }
  }

  if (step === 'text') {
    return (
      <div className="le-panel">
        <div className="le-header">
          <span className="le-title">
            {existingLyrics
              ? t('lyrics.editor.titleEdit')
              : t('lyrics.editor.titleAdd')}
          </span>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="icon-btn"
            ariaLabel={t('common.close', 'Закрыть')}
            onClick={onCancel}
          >
            <Icon name="x" size={16} />
          </MotionPress>
        </div>

        {draftBanner && (
          <div className="le-draft-banner">
            <span className="le-draft-banner__text">
              {t('lyrics.editor.draftBanner', {
                age: formatDraftAge(draftBanner.savedAt, t),
              })}
            </span>
            <div className="le-draft-banner__actions">
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="le-draft-banner__btn le-draft-banner__btn--primary"
                onClick={() => restoreDraft(draftBanner)}
              >
                {t('lyrics.editor.draftRestore')}
              </MotionPress>
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="le-draft-banner__btn"
                onClick={discardDraft}
              >
                {t('lyrics.editor.draftDiscard')}
              </MotionPress>
            </div>
          </div>
        )}

        <textarea
          className="form-input le-textarea"
          rows={10}
          maxLength={10000}
          placeholder={t('lyrics.editor.placeholder')}
          value={plainText}
          onChange={handleTextChange}
          onPaste={handlePasteIntoTextarea}
        />
        {autoDetectInfo && (
          <div className="le-info">{autoDetectInfo}</div>
        )}
        {error && (
          <div className="form-error">{error}</div>
        )}
        <div className="le-secondary-actions">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="btn-secondary le-secondary-btn"
            onClick={() => lrcInputRef.current?.click()}
            disabled={saving}
          >
            {t('lyrics.editor.importLrc')}
          </MotionPress>
          {trackId && (
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary le-secondary-btn"
              onClick={() => {
                void triggerAutoDetect()
              }}
              disabled={saving || autoDetectStarting}
            >
              {autoDetectStarting
                ? t('lyrics.editor.autoDetectRunning')
                : t('lyrics.editor.autoDetect')}
            </MotionPress>
          )}
          <input
            ref={lrcInputRef}
            type="file"
            accept=".lrc,text/plain"
            hidden
            onChange={handleLrcFile}
          />
        </div>
        <div className="le-actions">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="medium"
            className="btn-secondary"
            onClick={handleSaveText}
            disabled={saving || !plainText.trim()}
          >
            {t('lyrics.editor.saveText')}
          </MotionPress>
          {plainText.trim() && (
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              onClick={enterSync}
              disabled={saving}
            >
              {t('lyrics.editor.addTimecodes')}
            </MotionPress>
          )}
        </div>
      </div>
    )
  }

  const pct = duration ? (currentTime / duration) * 100 : 0

  const syncNode = (
    <div
      className="le-fullscreen le-fullscreen--portal"
      role="dialog"
      aria-modal="true"
      aria-label={t('lyrics.editor.timecodeModeAria')}
    >
      <div className="le-fs-header">
        <MotionPress
          type="button"
          variant="icon"
          haptic="light"
          className="icon-btn"
          ariaLabel={t('common.back', 'Назад')}
          onClick={() => setStep('text')}
        >
          <Icon name="undo" size={18} />
        </MotionPress>
        <span className="le-fs-time">
          {msToDisplay(Math.round(currentTime * 1000))}
        </span>
        <MotionPress
          type="button"
          variant="icon"
          haptic="light"
          className="icon-btn"
          ariaLabel={t('common.undo', 'Отменить')}
          onClick={undoLast}
          disabled={!history.length}
        >
          <Icon name="undo" size={18} />
        </MotionPress>
      </div>

      <div className="le-fs-seek">
        <input
          type="range"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          onChange={(e) => seek(Number(e.target.value))}
        />
      </div>

      <div className="le-fs-controls">
        <MotionPress
          type="button"
          variant="icon"
          haptic="light"
          className="ctrl-btn"
          ariaLabel={t('player.seekBack', '-5 секунд')}
          onClick={() => seekRelative(-5)}
        >
          <Icon name="rewind-5" size={20} />
        </MotionPress>
        <MotionPress
          type="button"
          variant="icon"
          haptic="medium"
          className={`play-btn${
            isPlaying ? ' play-btn--playing' : ''
          }`}
          ariaLabel={
            isPlaying
              ? t('player.pause', 'Пауза')
              : t('player.play', 'Воспроизвести')
          }
          onClick={togglePlay}
        >
          <MorphIcon
            name={isPlaying ? 'pause' : 'play'}
            size={18}
            filled
          />
        </MotionPress>
        <MotionPress
          type="button"
          variant="icon"
          haptic="light"
          className="ctrl-btn"
          ariaLabel={t('player.seekFwd', '+5 секунд')}
          onClick={() => seekRelative(5)}
        >
          <Icon name="forward-5" size={20} />
        </MotionPress>
      </div>

      <div className="le-fs-current" onClick={markCurrent}>
        <p className="le-fs-current-text">
          {lines[currentLine] || '—'}
        </p>
        <p className="le-fs-hint">
          {t('lyrics.editor.tapToMark')}
        </p>
      </div>

      {timecodes[currentLine] !== null && (
        <div className="le-fs-nudge">
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="le-fs-nudge-btn"
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation()
              nudgeCurrent(-50)
            }}
          >
            {t('lyrics.editor.nudgeMinus')}
          </MotionPress>
          <span className="le-fs-nudge-time">
            {msToDisplay(timecodes[currentLine]!)}
          </span>
          <MotionPress
            type="button"
            variant="ghost"
            haptic="light"
            className="le-fs-nudge-btn"
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation()
              nudgeCurrent(50)
            }}
          >
            {t('lyrics.editor.nudgePlus')}
          </MotionPress>
        </div>
      )}

      <div className="le-fs-list" ref={listRef}>
        {lines.map((line, i) => (
          <div
            key={i}
            ref={i === currentLine ? activeRef : null}
            className={`le-fs-line${
              i === currentLine ? ' active' : ''
            }`}
            onClick={() => jumpTo(i)}
          >
            <span className="le-fs-line-time">
              {timecodes[i] !== null
                ? msToDisplay(timecodes[i]!)
                : '—'}
            </span>
            <span className="le-fs-line-text">{line}</span>
          </div>
        ))}
      </div>

      {error && (
        <div className="form-error">{error}</div>
      )}

      <div className="le-fs-save">
        <MotionPress
          type="button"
          variant="ghost"
          haptic="medium"
          className="btn-secondary le-fs-save-btn"
          onClick={handleSaveText}
          disabled={saving}
        >
          {t('lyrics.editor.noTimecodes')}
        </MotionPress>
        <MotionPress
          type="button"
          variant="primary"
          haptic="medium"
          className="btn-primary le-fs-save-btn"
          onClick={handleSaveSync}
          disabled={
            saving || timecodes.every((tc) => tc === null)
          }
        >
          {t('lyrics.editor.save')}
        </MotionPress>
      </div>
    </div>
  )

  return createPortal(syncNode, document.body)
}
