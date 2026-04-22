import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import type { LyricsResponse, SyncedLine } from '@/types/api'

const SYNC_OFFSET_KEY = 'setting-lyrics-sync-offset-ms'
const KARAOKE_KEY = 'setting-lyrics-karaoke'

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

function readOffset(): number {
  const raw = localStorage.getItem(SYNC_OFFSET_KEY)
  const n = raw ? Number(raw) : 0
  return Number.isFinite(n) ? n : 0
}

function readKaraoke(): boolean {
  return localStorage.getItem(KARAOKE_KEY) === '1'
}

function activeLineIndex(
  lines: SyncedLine[],
  ms: number,
): number {
  let idx = -1
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].time_ms <= ms) idx = i
    else break
  }
  return idx
}

function activeWordIndex(line: SyncedLine, ms: number): number {
  const wts = line.word_times
  if (!wts || wts.length === 0) return -1
  for (let i = 0; i < wts.length; i++) {
    const w = wts[i]
    if (ms >= w.start_ms && ms < w.start_ms + w.dur_ms) return i
  }
  return -1
}

export function FullscreenLyrics() {
  const { t } = useTranslation()
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

  const [lyrics, setLyrics] = useState<LyricsResponse | null>(
    null,
  )
  const [loading, setLoading] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  const [offsetMs, setOffsetMs] = useState<number>(readOffset)
  const [karaoke, setKaraoke] = useState<boolean>(readKaraoke)
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

  const adjustedMs = currentTime * 1000 + offsetMs

  const activeIdx = lyrics?.synced_lines?.length
    ? activeLineIndex(lyrics.synced_lines, adjustedMs)
    : -1

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    }
  }, [activeIdx])

  if (!isLyricsOpen || !track) return null

  const pct = duration ? (currentTime / duration) * 100 : 0

  const videoEnabled =
    localStorage.getItem('setting-video-enabled') !== 'false'
  const videoSrc =
    track.video_key && videoEnabled
      ? `/api/v1/tracks/${track.id}/video`
      : null

  const handleLineClick = (timeMs: number) => {
    if (!duration) return
    seek((timeMs / 1000 / duration) * 100)
  }

  const handleOffsetChange = (val: number) => {
    setOffsetMs(val)
    try {
      localStorage.setItem(SYNC_OFFSET_KEY, String(val))
    } catch {}
  }

  const toggleKaraoke = () => {
    const next = !karaoke
    setKaraoke(next)
    try {
      localStorage.setItem(KARAOKE_KEY, next ? '1' : '0')
    } catch {}
  }

  const hasWordTimes = !!lyrics?.synced_lines?.some(
    (l) => l.word_times && l.word_times.length > 0,
  )
  const karaokeActive =
    karaoke && hasWordTimes && lyrics?.sync_quality === 'word'
  const isAdmin = getIsAdmin()

  return (
    <div className="fl-overlay">
      {videoSrc && !videoFailed && (
        <video
          className="fl-video-bg"
          src={videoSrc}
          autoPlay
          loop
          muted
          playsInline
          onError={() => setVideoFailed(true)}
        />
      )}
      <div className="fl-gradient" />

      <button
        className="fl-close icon-btn"
        onClick={closeLyrics}
      >
        <Icon name="x" size={18} />
      </button>

      <div className="fl-toolbar">
        {hasWordTimes && (
          <button
            className={`fl-toolbar-btn${karaokeActive ? ' fl-toolbar-btn-active' : ''}`}
            onClick={toggleKaraoke}
            aria-pressed={karaokeActive}
          >
            {t('lyrics.karaokeMode', 'Karaoke')}
          </button>
        )}
        <label className="fl-offset">
          <span>{t('lyrics.syncOffset', 'Offset')}</span>
          <input
            type="range"
            min={-2000}
            max={2000}
            step={50}
            value={offsetMs}
            onChange={(e) =>
              handleOffsetChange(Number(e.target.value))
            }
          />
          <span className="fl-offset-value">
            {offsetMs >= 0 ? '+' : ''}
            {offsetMs} ms
          </span>
        </label>
      </div>

      <div className="fl-content">
        {loading && <div className="loader" />}

        {!loading && lyrics?.synced_lines?.length
          ? lyrics.synced_lines.map((line, i) => {
              const isActive = i === activeIdx
              const wordIdx =
                karaokeActive && isActive
                  ? activeWordIndex(line, adjustedMs)
                  : -1
              return (
                <div
                  key={i}
                  ref={isActive ? activeRef : null}
                  className={`fl-line${isActive ? ' fl-line-active' : ''}`}
                  onClick={() =>
                    handleLineClick(line.time_ms)
                  }
                >
                  {karaokeActive &&
                  line.word_times &&
                  line.word_times.length > 0 ? (
                    line.word_times.map((w, j) => (
                      <span
                        key={j}
                        className={`fl-word${j === wordIdx ? ' fl-word-active' : ''}${isActive && j < wordIdx ? ' fl-word-past' : ''}`}
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
          : !loading &&
            lyrics?.plain_text && (
              <pre className="fl-plain">
                {lyrics.plain_text}
              </pre>
            )}

        {!loading && !lyrics && (
          <p className="fl-no-lyrics">
            {t('lyrics.notFound', 'Текст не найден')}
          </p>
        )}

        {!loading && lyrics && isAdmin && (
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
            style={{ ['--progress' as any]: `${pct}%` }}
            aria-label="Перемотка трека"
            onChange={(e) =>
              seek(Number(e.target.value))
            }
          />
        </div>
        <div className="fl-controls-row">
          <span className="fl-time">{fmt(currentTime)}</span>
          <div className="fl-btns">
            <button
              className="ctrl-btn"
              onClick={playPrev}
              aria-label="Предыдущий трек"
            >
              <Icon name="skip-back" size={18} />
            </button>
            <button
              className="play-btn"
              onClick={togglePlay}
              aria-label={isPlaying ? 'Пауза' : 'Воспроизвести'}
            >
              <Icon
                name={isPlaying ? 'pause' : 'play'}
                size={16}
              />
            </button>
            <button
              className="ctrl-btn"
              onClick={playNext}
              aria-label="Следующий трек"
            >
              <Icon name="skip-forward" size={18} />
            </button>
          </div>
          <span className="fl-time">{fmt(duration)}</span>
        </div>
      </div>
    </div>
  )
}
