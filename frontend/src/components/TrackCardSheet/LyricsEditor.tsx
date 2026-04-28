import {
  useEffect,
  useRef,
  useState,
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
  const [error, setError] = useState<string | null>(
    null,
  )
  const [history, setHistory] = useState<
    { idx: number; prev: number | null }[]
  >([])
  const listRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)

  const enterSync = () => {
    const split = plainText
      .split('\n')
      .filter((l) => l.trim())
    setLines(split)
    const existing =
      existingLyrics?.synced_lines ?? []
    setTimecodes(
      split.map(
        (_, i) => existing[i]?.time_ms ?? null,
      ),
    )
    setCurrentLine(0)
    setHistory([])
    setStep('sync')
  }

  const markCurrent = () => {
    const ms = Math.round(currentTime * 1000)
    const idx = currentLine
    setHistory((h) => [
      ...h,
      { idx, prev: timecodes[idx] },
    ])
    setTimecodes((prev) => {
      const next = [...prev]
      next[idx] = ms
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
        ? (timecodes[idx]! / 1000 / duration) *
          100
        : 0
      seek(pct)
    }
  }

  const seekRelative = (sec: number) => {
    if (!duration) return
    const target = Math.max(
      0,
      Math.min(
        duration,
        currentTime + sec,
      ),
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
      const saved = await api.saveLyricsSync(
        trackId!,
        synced,
      )
      onSaved(saved)
    } catch {
      setError(t('lyrics.editor.saveError'))
    } finally {
      setSaving(false)
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
          <button
            className="icon-btn"
            onClick={onCancel}
          >
            <Icon name="x" size={16} />
          </button>
        </div>
        <textarea
          className="form-input le-textarea"
          rows={10}
          maxLength={10000}
          placeholder={t('lyrics.editor.placeholder')}
          value={plainText}
          onChange={(e) =>
            setPlainText(e.target.value)
          }
        />
        {error && (
          <div className="form-error">{error}</div>
        )}
        <div className="le-actions">
          <button
            className="btn-secondary"
            onClick={handleSaveText}
            disabled={saving || !plainText.trim()}
          >
            {t('lyrics.editor.saveText')}
          </button>
          {plainText.trim() && (
            <button
              className="btn-primary"
              onClick={enterSync}
              disabled={saving}
            >
              {t('lyrics.editor.addTimecodes')}
            </button>
          )}
        </div>
      </div>
    )
  }

  const pct = duration
    ? (currentTime / duration) * 100
    : 0

  const syncNode = (
    <div
      className="le-fullscreen le-fullscreen--portal"
      role="dialog"
      aria-modal="true"
      aria-label={t('lyrics.editor.timecodeModeAria')}
    >
      <div className="le-fs-header">
        <button
          className="icon-btn"
          onClick={() => setStep('text')}
        >
          <Icon name="undo" size={18} />
        </button>
        <span className="le-fs-time">
          {msToDisplay(
            Math.round(currentTime * 1000),
          )}
        </span>
        <button
          className="icon-btn"
          onClick={undoLast}
          disabled={!history.length}
        >
          <Icon name="undo" size={18} />
        </button>
      </div>

      <div className="le-fs-seek">
        <input
          type="range"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          onChange={(e) =>
            seek(Number(e.target.value))
          }
        />
      </div>

      <div className="le-fs-controls">
        <button
          className="ctrl-btn"
          onClick={() => seekRelative(-5)}
        >
          <Icon name="rewind-5" size={20} />
        </button>
        <button
          className={`play-btn${
            isPlaying ? ' play-btn--playing' : ''
          }`}
          onClick={togglePlay}
        >
          <Icon
            name={isPlaying ? 'pause' : 'play'}
            size={18}
          />
        </button>
        <button
          className="ctrl-btn"
          onClick={() => seekRelative(5)}
        >
          <Icon name="forward-5" size={20} />
        </button>
      </div>

      <div
        className="le-fs-current"
        onClick={markCurrent}
      >
        <p className="le-fs-current-text">
          {lines[currentLine] || '—'}
        </p>
        <p className="le-fs-hint">
          {t('lyrics.editor.tapToMark')}
        </p>
      </div>

      <div
        className="le-fs-list"
        ref={listRef}
      >
        {lines.map((line, i) => (
          <div
            key={i}
            ref={
              i === currentLine
                ? activeRef
                : null
            }
            className={`le-fs-line${i === currentLine ? ' active' : ''}`}
            onClick={() => jumpTo(i)}
          >
            <span className="le-fs-line-time">
              {timecodes[i] !== null
                ? msToDisplay(timecodes[i]!)
                : '—'}
            </span>
            <span className="le-fs-line-text">
              {line}
            </span>
          </div>
        ))}
      </div>

      {error && (
        <div className="form-error">{error}</div>
      )}

      <div className="le-fs-save">
        <button
          className="btn-secondary"
          onClick={handleSaveText}
          disabled={saving}
          style={{ flex: 1 }}
        >
          {t('lyrics.editor.noTimecodes')}
        </button>
        <button
          className="btn-primary"
          onClick={handleSaveSync}
          disabled={
            saving ||
            timecodes.every((tc) => tc === null)
          }
          style={{ flex: 1 }}
        >
          {t('lyrics.editor.save')}
        </button>
      </div>
    </div>
  )

  return createPortal(
    syncNode,
    document.body,
  )
}
