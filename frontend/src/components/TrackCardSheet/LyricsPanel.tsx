import {
  useEffect,
  useRef,
  useState,
} from 'react'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import type { LyricsResponse } from '@/types/api'
import { LyricsEditor } from './LyricsEditor'

interface Props {
  trackId: number
  isOwner: boolean
  hasLyrics: boolean
}

export function LyricsPanel({
  trackId,
  isOwner,
  hasLyrics,
}: Props) {
  const { currentTime, duration, seek } =
    usePlayer()
  const [lyrics, setLyrics] =
    useState<LyricsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<
    string | null
  >(null)
  const [editing, setEditing] = useState(
    !hasLyrics && isOwner,
  )
  const activeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!hasLyrics) return
    setLoading(true)
    api
      .getLyrics(trackId)
      .then(setLyrics)
      .catch(() =>
        setError('Не удалось загрузить текст'),
      )
      .finally(() => setLoading(false))
  }, [trackId, hasLyrics])

  const activeIdx = (() => {
    if (!lyrics?.synced_lines?.length) return -1
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

  if (editing || (!hasLyrics && isOwner)) {
    return (
      <LyricsEditor
        trackId={trackId}
        existingLyrics={lyrics}
        onSaved={handleSaved}
        onCancel={() =>
          hasLyrics && setEditing(false)
        }
      />
    )
  }

  if (!lyrics) return null

  return (
    <div className="lyrics-panel">
      <div className="lyrics-panel-header">
        <span className="lyrics-panel-title">
          Текст
        </span>
        {isOwner && (
          <button
            className="lyrics-edit-btn"
            onClick={() => setEditing(true)}
          >
            <Icon name="edit" size={14} />
            Редактировать
          </button>
        )}
      </div>

      <div className="lyrics-content">
        {lyrics.synced_lines?.length
          ? lyrics.synced_lines.map((line, i) => (
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
            ))
          : (
            <pre className="lyrics-plain">
              {lyrics.plain_text}
            </pre>
          )}
      </div>
    </div>
  )
}
