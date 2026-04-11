import {
  useEffect,
  useRef,
  useState,
} from 'react'
import { api } from '@/lib/api'
import { usePlayer } from '@/store/PlayerContext'
import type { LyricsResponse } from '@/types/api'

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

export function FullscreenLyrics() {
  const {
    track,
    isPlaying,
    isLyricsOpen,
    closeLyrics,
    currentTime,
    duration,
    togglePlay,
    playNext,
    playPrev,
    seek,
  } = usePlayer()

  const [lyrics, setLyrics] =
    useState<LyricsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const activeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isLyricsOpen || !track) {
      setLyrics(null)
      return
    }
    setLoading(true)
    api
      .getLyrics(track.id)
      .then(setLyrics)
      .catch(() => setLyrics(null))
      .finally(() => setLoading(false))
  }, [isLyricsOpen, track?.id])

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

  if (!isLyricsOpen || !track) return null

  const pct = duration
    ? (currentTime / duration) * 100
    : 0

  const videoSrc = track.video_key
    ? `/api/v1/tracks/${track.id}/video`
    : null

  return (
    <div className="fl-overlay">
      {videoSrc && (
        <video
          className="fl-video-bg"
          src={videoSrc}
          autoPlay
          loop
          muted
          playsInline
        />
      )}
      <div className="fl-gradient" />

      <button
        className="fl-close icon-btn"
        onClick={closeLyrics}
      >
        ✕
      </button>

      <div className="fl-content">
        {loading && (
          <div className="loader" />
        )}

        {!loading && lyrics?.synced_lines?.length
          ? lyrics.synced_lines.map((line, i) => (
              <div
                key={i}
                ref={
                  i === activeIdx
                    ? activeRef
                    : null
                }
                className={`fl-line${i === activeIdx ? ' fl-line-active' : ''}`}
              >
                {line.text}
              </div>
            ))
          : !loading &&
            lyrics?.plain_text && (
              <pre className="fl-plain">
                {lyrics.plain_text}
              </pre>
            )}

        {!loading && !lyrics && (
          <p className="fl-no-lyrics">
            Текст не найден
          </p>
        )}
      </div>

      <div className="fl-controls">
        <div className="fl-seek-wrap">
          <input
            type="range"
            className="fl-seek"
            min={0}
            max={100}
            step={0.1}
            value={pct}
            onChange={(e) =>
              seek(Number(e.target.value))
            }
          />
        </div>
        <div className="fl-controls-row">
          <span className="fl-time">
            {fmt(currentTime)}
          </span>
          <div className="fl-btns">
            <button
              className="ctrl-btn"
              onClick={playPrev}
            >
              ⏮
            </button>
            <button
              className="play-btn"
              onClick={togglePlay}
            >
              {isPlaying ? '⏸' : '▶'}
            </button>
            <button
              className="ctrl-btn"
              onClick={playNext}
            >
              ⏭
            </button>
          </div>
          <span className="fl-time">
            {fmt(duration)}
          </span>
        </div>
      </div>
    </div>
  )
}
