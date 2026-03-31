import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import type { LyricsResponse, SyncedLine } from '@/types/api'

interface Props {
  trackId: number
  existingLyrics: LyricsResponse | null
  onSaved: (lyrics: LyricsResponse) => void
  onCancel: () => void
}

type EditorStep = 'text' | 'timecodes'

function msToDisplay(ms: number): string {
  const totalSec = ms / 1000
  const m = Math.floor(totalSec / 60)
  const s = (totalSec % 60).toFixed(1).padStart(4, '0')
  return `${m}:${s}`
}

function parseMsFromInput(val: string): number | null {
  const parts = val.trim().split(':')
  if (parts.length !== 2) return null
  const m = parseFloat(parts[0])
  const s = parseFloat(parts[1])
  if (isNaN(m) || isNaN(s)) return null
  return Math.round((m * 60 + s) * 1000)
}

export function LyricsEditor({ trackId, existingLyrics, onSaved, onCancel }: Props) {
  const { currentTime, track, playTrack } = usePlayer()

  const [step, setStep] = useState<EditorStep>('text')
  const [plainText, setPlainText] = useState(existingLyrics?.plain_text ?? '')
  const [lines, setLines] = useState<string[]>([])
  const [timecodes, setTimecodes] = useState<(number | null)[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // When entering timecode step, split text into lines
  const enterTimecodeStep = () => {
    const splitLines = plainText.split('\n').filter((l) => l.trim() !== '')
    setLines(splitLines)
    // Preserve existing timecodes if available
    const existing = existingLyrics?.synced_lines ?? []
    setTimecodes(splitLines.map((_, i) => existing[i]?.time_ms ?? null))
    setStep('timecodes')
  }

  // Tap to mark: set current playback time for line
  const markLine = (idx: number) => {
    const ms = Math.round(currentTime * 1000)
    setTimecodes((prev) => {
      const next = [...prev]
      next[idx] = ms
      return next
    })
  }

  // Manual input for timecode
  const handleTimeInput = (idx: number, val: string) => {
    const ms = parseMsFromInput(val)
    setTimecodes((prev) => {
      const next = [...prev]
      next[idx] = ms
      return next
    })
  }

  const handleSaveText = async () => {
    if (!plainText.trim()) {
      setError('Введите текст')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const saved = await api.saveLyrics(trackId, plainText.trim())
      onSaved(saved)
    } catch {
      setError('Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveSync = async () => {
    setSaving(true)
    setError(null)
    try {
      const syncedLines: SyncedLine[] = lines
        .map((text, i) => ({ time_ms: timecodes[i] ?? 0, text }))
        .sort((a, b) => a.time_ms - b.time_ms)
      const saved = await api.saveLyricsSync(trackId, syncedLines)
      onSaved(saved)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      setError(msg === '422' ? 'Таймкоды должны быть в порядке возрастания' : 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  // Auto-start playing when entering timecode step
  useEffect(() => {
    if (step === 'timecodes' && track) {
      playTrack(track).catch(() => {})
    }
  }, [step]) // eslint-disable-line react-hooks/exhaustive-deps

  if (step === 'text') {
    return (
      <div className="lyrics-editor">
        <div className="lyrics-panel-header">
          <span className="lyrics-panel-title">
            {existingLyrics ? 'Редактировать текст' : 'Добавить текст'}
          </span>
          <button className="lyrics-edit-btn" onClick={onCancel}>Отмена</button>
        </div>

        <div className="form-group">
          <textarea
            className="form-input lyrics-textarea"
            rows={10}
            maxLength={10000}
            placeholder="Вставьте текст песни&#10;Каждая строка — отдельная строфа"
            value={plainText}
            onChange={(e) => setPlainText(e.target.value)}
          />
        </div>

        {error && <div className="form-error">{error}</div>}

        <div className="lyrics-editor-actions">
          <button
            className="btn-secondary"
            onClick={handleSaveText}
            disabled={saving || !plainText.trim()}
          >
            💾 Сохранить текст
          </button>
          {plainText.trim() && (
            <button
              className="btn-primary"
              onClick={enterTimecodeStep}
              disabled={saving}
            >
              🕐 Добавить таймкоды →
            </button>
          )}
        </div>
      </div>
    )
  }

  // Timecode step
  return (
    <div className="lyrics-editor">
      <div className="lyrics-panel-header">
        <button className="lyrics-edit-btn" onClick={() => setStep('text')}>← Текст</button>
        <span className="lyrics-panel-title">Таймкоды</span>
        <span className="lyrics-editor-time">{msToDisplay(Math.round(currentTime * 1000))}</span>
      </div>

      <p className="lyrics-editor-hint">
        Нажми ▶ на строке во время воспроизведения, чтобы отметить момент. Или введи время вручную (м:сс.д).
      </p>

      <div className="lyrics-timecode-list">
        {lines.map((line, i) => (
          <div key={i} className="lyrics-timecode-row">
            <button
              className="lyrics-timecode-mark"
              title="Отметить текущий момент"
              onClick={() => markLine(i)}
            >
              ▶
            </button>
            <div className="lyrics-timecode-text">{line}</div>
            <input
              className="lyrics-timecode-input"
              type="text"
              placeholder="0:00.0"
              value={timecodes[i] !== null ? msToDisplay(timecodes[i]!) : ''}
              onChange={(e) => handleTimeInput(i, e.target.value)}
            />
          </div>
        ))}
      </div>

      {error && <div className="form-error">{error}</div>}

      <div className="lyrics-editor-actions">
        <button
          className="btn-secondary"
          onClick={handleSaveText}
          disabled={saving}
        >
          💾 Сохранить без таймкодов
        </button>
        <button
          className="btn-primary"
          onClick={handleSaveSync}
          disabled={saving || timecodes.every((t) => t === null)}
        >
          💾 Сохранить с таймкодами
        </button>
      </div>
    </div>
  )
}
