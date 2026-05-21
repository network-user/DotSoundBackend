import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { getIsAdmin, getUserId } from '@/lib/telegram'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { useExitTransition } from '@/hooks/useExitTransition'
import type { LyricsResponse, SyncedLine } from '@/types/api'
import {
  m,
  SPRING_GENTLE,
  useReducedMotion,
} from '@/lib/motion'

const KARAOKE_KEY = 'setting-lyrics-karaoke'

function clampPct(value: number): number {
  return Math.min(100, Math.max(0, value))
}

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const mins = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${mins}:${s}`
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

export type FullscreenLyricsProps = {
  embed?: boolean
}

export function FullscreenLyrics({
  embed = false,
}: FullscreenLyricsProps) {
  const { t } = useTranslation()
  const lyricsReduce = useReducedMotion()
  const { currentTime, duration, isPlaying } =
    usePlayerState()
  const { track, isLyricsOpen } = usePlayerMeta()
  const {
    closeLyrics,
    togglePlay,
    playNext,
    playPrev,
    seek,
    getPreciseTime,
  } = usePlayerActions()

  const panelOpen = embed || isLyricsOpen

  const [lyrics, setLyrics] = useState<LyricsResponse | null>(
    null,
  )
  const [loading, setLoading] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  const [karaoke, setKaraoke] = useState<boolean>(readKaraoke)
  const [selectedLang, setSelectedLang] =
    useState<string>('original')
  const [activeIdx, setActiveIdx] = useState(-1)
  const [wordIdx, setWordIdx] = useState(-1)
  const activeRef = useRef<HTMLDivElement>(null)
  const rafIdRef = useRef<number | null>(null)

  const exit = useExitTransition(
    Boolean(track) && panelOpen,
    220,
  )

  useEffect(() => {
    if (!panelOpen || !track) {
      return
    }
    setSelectedLang('original')
    setVideoFailed(false)
    setLoading(true)
    api
      .getLyrics(track.id)
      .then(setLyrics)
      .catch(() => setLyrics(null))
      .finally(() => setLoading(false))
  }, [panelOpen, track?.id])

  useEffect(() => {
    if (exit.mounted) return
    setLyrics(null)
  }, [exit.mounted])

  useEffect(() => {
    if (embed || !panelOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeLyrics()
    }
    window.addEventListener('keydown', onKey)
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [embed, panelOpen, closeLyrics])

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
    lyrics?.synced_lines?.length && activeIdx < 0
      ? Math.max(
          0,
          lyrics.synced_lines[0].time_ms - currentTime * 1000,
        )
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
      ((currentTime * 1000 - current.time_ms) / spanMs) * 100,
    )
  }

  useEffect(() => {
    const lines = lyrics?.synced_lines
    if (
      !panelOpen ||
      !isPlaying ||
      !lines ||
      lines.length === 0
    ) {
      return
    }
    let cancelled = false
    const loop = () => {
      if (cancelled) return
      const ms = getPreciseTime() * 1000
      const nextLine = activeLineIndex(lines, ms)
      setActiveIdx((prev) =>
        prev === nextLine ? prev : nextLine,
      )
      const nextWord =
        karaokeActive && nextLine >= 0
          ? activeWordIndex(lines[nextLine], ms)
          : -1
      setWordIdx((prev) =>
        prev === nextWord ? prev : nextWord,
      )
      rafIdRef.current = requestAnimationFrame(loop)
    }
    rafIdRef.current = requestAnimationFrame(loop)
    return () => {
      cancelled = true
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current)
        rafIdRef.current = null
      }
    }
  }, [
    panelOpen,
    isPlaying,
    lyrics,
    karaokeActive,
    getPreciseTime,
  ])

  useEffect(() => {
    const lines = lyrics?.synced_lines
    if (!panelOpen || !lines || lines.length === 0) {
      setActiveIdx(-1)
      setWordIdx(-1)
      return
    }
    if (isPlaying) return
    const ms = currentTime * 1000
    const nextLine = activeLineIndex(lines, ms)
    setActiveIdx((prev) =>
      prev === nextLine ? prev : nextLine,
    )
    const nextWord =
      karaokeActive && nextLine >= 0
        ? activeWordIndex(lines[nextLine], ms)
        : -1
    setWordIdx((prev) =>
      prev === nextWord ? prev : nextWord,
    )
  }, [
    panelOpen,
    isPlaying,
    lyrics,
    karaokeActive,
    currentTime,
  ])

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    }
  }, [activeIdx])

  if (!exit.mounted || !track) return null

  const pct = duration ? (currentTime / duration) * 100 : 0

  const videoEnabled =
    localStorage.getItem('setting-video-enabled') !== 'false'
  const videoSrc =
    !embed &&
    track.video_key &&
    videoEnabled
      ? `/api/v1/tracks/${track.id}/video`
      : null

  const handleLineClick = (timeMs: number) => {
    if (!duration) return
    seek((timeMs / 1000 / duration) * 100)
  }

  const toggleKaraoke = () => {
    const next = !karaoke
    setKaraoke(next)
    try {
      localStorage.setItem(KARAOKE_KEY, next ? '1' : '0')
    } catch {}
  }

  const isAdmin = getIsAdmin()
  const uid = getUserId()
  const isOwner =
    track.uploaded_by_id != null &&
    uid != null &&
    track.uploaded_by_id === uid &&
    track.catalog_type === 'ugc'

  const showToolbar = hasWordTimes || translationItems.length > 0
  const toolbar = showToolbar ? (
    <div
      className={`fl-toolbar${embed ? ' fl-toolbar--embed' : ''}`}
    >
      {hasWordTimes && (
        <MotionPress
          variant="ghost"
          haptic="selection"
          className={`fl-toolbar-btn${karaokeActive ? ' fl-toolbar-btn-active' : ''}`}
          onClick={toggleKaraoke}
          aria-pressed={karaokeActive}
        >
          {t('lyrics.karaokeMode', 'Karaoke')}
        </MotionPress>
      )}
      {translationItems.length > 0 && (
        <select
          className="fl-lang-select"
          value={selectedLang}
          onChange={(e) =>
            setSelectedLang(e.target.value)
          }
          aria-label={t('redesign.player.lyricsLanguage', 'Language')}
        >
          <option value="original">
            {t('redesign.player.lyricsOriginal', 'Original')}
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
  ) : null

  const content = (
    <div
      className={`fl-content${embed ? ' fl-content--embed' : ''}`}
    >
      {loading && <div className="loader" />}

      {firstLineLeadInMs !== null && firstLineLeadInMs > 250 && (
        <button
          type="button"
          className="fl-countdown"
          onClick={() =>
            handleLineClick(lyrics!.synced_lines![0].time_ms)
          }
        >
          <span className="fl-countdown__label">
            {t('lyrics.startsIn', 'Starts in')}
          </span>
          <span className="fl-countdown__time">
            {(firstLineLeadInMs / 1000).toFixed(1)}
          </span>
        </button>
      )}

      {!loading && lyrics?.synced_lines?.length
        ? lyrics.synced_lines.map((line, i) => {
            const isActive = i === activeIdx
            const isPast = activeIdx > i
            const lineWordIdx =
              karaokeActive && isActive ? wordIdx : -1
            return (
              <m.div
                key={i}
                ref={isActive ? activeRef : null}
                layout
                initial={false}
                animate={
                  isActive && !lyricsReduce
                    ? { scale: 1.04, opacity: 1 }
                    : {
                        scale: 1,
                        opacity: isActive ? 1 : 0.55,
                      }
                }
                transition={SPRING_GENTLE}
                className={`fl-line${
                  isActive ? ' fl-line-active' : ''
                }${isPast ? ' fl-line-past' : ''}`}
                style={
                  {
                    ['--fl-line-progress']: `${
                      isActive ? lineProgressPct(i) : 0
                    }%`,
                  } as CSSProperties
                }
                aria-current={isActive ? 'true' : undefined}
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
                      className={`fl-word${j === lineWordIdx ? ' fl-word-active' : ''}${isActive && j < lineWordIdx ? ' fl-word-past' : ''}`}
                    >
                      {w.text}{' '}
                    </span>
                  ))
                ) : (
                  line.text
                )}
              </m.div>
            )
          })
        : !loading &&
          lyrics?.plain_text && (
            <pre className="fl-plain">
              {plainTextToRender}
            </pre>
          )}

      {!loading && !lyrics && (
        <p className="fl-no-lyrics">
          {t('lyrics.notFound', 'Текст не найден')}
        </p>
      )}

      {!loading && lyrics && (isAdmin || isOwner) && (
        <div className="lyrics-debug-attribution">
          <div className="lyrics-debug-row">
            <span className="lyrics-debug-label">
              {t(
                'redesign.player.lyricsSourceLabel',
                'Источник текста:',
              )}
            </span>
            <span className="lyrics-debug-value">
              {lyrics.source_name || '—'}
            </span>
          </div>
          <div className="lyrics-debug-row">
            <span className="lyrics-debug-label">
              {t(
                'redesign.player.lyricsSyncLabel',
                'Синхронизовал:',
              )}
            </span>
            <span className="lyrics-debug-value">
              {lyrics.sync_source_name || '—'}
            </span>
          </div>
        </div>
      )}
    </div>
  )

  const controls = (
    <div
      className={`fl-controls${embed ? ' fl-controls--embed' : ''}`}
    >
      <div className="fl-seek-wrap">
        <input
          type="range"
          className="fl-seek"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          style={
            {
              ['--progress']: `${pct}%`,
            } as CSSProperties
          }
          aria-label={t('redesign.player.seekAria', 'Seek')}
          onChange={(e) =>
            seek(Number(e.target.value))
          }
        />
      </div>
      <div className="fl-controls-row">
        <span className="fl-time">{fmt(currentTime)}</span>
        <div className="fl-btns">
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="ctrl-btn"
            ariaLabel={t(
              'redesign.player.prevAria',
              'Previous track',
            )}
            onClick={playPrev}
          >
            <Icon name="skip-back" size={18} />
          </MotionPress>
          <MotionPress
            type="button"
            variant="primary"
            haptic="medium"
            className={`play-btn${
              isPlaying ? ' play-btn--playing' : ''
            }`}
            ariaLabel={
              isPlaying
                ? t('redesign.player.pauseAria', 'Pause')
                : t('redesign.player.playAria', 'Play')
            }
            onClick={togglePlay}
          >
            <MorphIcon
              name={isPlaying ? 'pause' : 'play'}
              size={16}
              filled
            />
          </MotionPress>
          <MotionPress
            type="button"
            variant="icon"
            haptic="light"
            className="ctrl-btn"
            ariaLabel={t(
              'redesign.player.nextAria',
              'Next track',
            )}
            onClick={() => {
              void playNext()
            }}
          >
            <Icon name="skip-forward" size={18} />
          </MotionPress>
        </div>
        <span className="fl-time">{fmt(duration)}</span>
      </div>
    </div>
  )

  if (embed) {
    return (
      <div className="fl-embed rp-now-lyrics-embed">
        {toolbar}
        {content}
        {controls}
      </div>
    )
  }

  return (
    <div className={`fl-overlay${exit.cls}`}>
      {videoSrc && !videoFailed && (
        <video
          key={videoSrc}
          className="fl-video-bg"
          src={videoSrc}
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          onCanPlay={() => setVideoFailed(false)}
          onLoadedData={() => setVideoFailed(false)}
          onError={() => setVideoFailed(true)}
        />
      )}
      <div className="fl-gradient" />

      <div className="fl-header rp-now-fl-header">
        <BeatPulse
          bpm={
            (track as unknown as { bpm?: number }).bpm ??
            120
          }
          active={isPlaying}
          className="fl-header-cover rp-now-fl-cover"
        >
          <CoverImage coverKey={track.cover_key ?? null} />
        </BeatPulse>
        <div className="fl-header-meta rp-now-fl-meta">
          <span className="fl-header-title">{track.title}</span>
          {track.artist && (
            <span className="fl-header-artist">
              {track.artist}
            </span>
          )}
        </div>
        <MotionPress
          type="button"
          variant="icon"
          haptic="light"
          className="fl-close icon-btn"
          ariaLabel={t(
            'redesign.player.closeLyrics',
            'Close',
          )}
          onClick={closeLyrics}
        >
          <Icon name="x" size={18} />
        </MotionPress>
      </div>

      {toolbar}
      {content}
      {controls}
    </div>
  )
}
