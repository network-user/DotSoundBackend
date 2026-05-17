import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import { AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerPlayback,
} from '@/store/PlayerContext'
import { getUserId, haptic } from '@/lib/telegram'
import { m, useReducedMotion } from '@/lib/motion'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { SharedCover } from '@/components/ui/SharedCover'
import { SpectrumMicroBars } from '@/components/ui/SpectrumMicroBars'
import { AddToPlaylistSheet } from '@/components/AddToPlaylistSheet/AddToPlaylistSheet'
import { useSwipeX } from '@/hooks/useSwipeX'
import {
  coverProxySizes,
  coverProxySrcSet,
  coverProxyUrl,
} from '@/lib/coverProxy'
import { isPerfLiteActive } from '@/lib/glassPerformance'
import {
  extractCoverPalette,
  type CoverPalette,
} from '@/lib/coverPalette'

const COVER_SPRING = {
  type: 'spring' as const,
  stiffness: 340,
  damping: 24,
  mass: 0.7,
}
const INFO_EASE = {
  duration: 0.16,
  ease: [0.32, 0, 0.18, 1] as [
    number,
    number,
    number,
    number,
  ],
}
const SWIPE_THRESHOLD = 52
const MINI_WAVE_BARS = 34
const FALLBACK_WAVE_BARS = [
  30, 46, 26, 58, 38, 72, 44, 64, 34, 82, 48, 66,
  40, 76, 54, 62, 36, 70, 50, 84, 42, 60, 32, 74,
  46, 68, 28, 56, 40, 78, 52, 64, 36, 50,
]

function buildMiniWaveBars(
  data: number[] | null | undefined,
): number[] {
  if (!data || data.length === 0) {
    return FALLBACK_WAVE_BARS
  }
  const bars: number[] = []
  const step = data.length / MINI_WAVE_BARS
  for (let i = 0; i < MINI_WAVE_BARS; i += 1) {
    const start = Math.floor(i * step)
    const end = Math.max(
      start + 1,
      Math.floor((i + 1) * step),
    )
    const slice = data.slice(start, end)
    const avg =
      slice.reduce((sum, amp) => sum + Math.abs(amp), 0) /
      slice.length
    bars.push(Math.round(24 + Math.min(1, avg) * 62))
  }
  return bars
}

export function MiniPlayerBar() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const { isPlaying, duration } = usePlayerPlayback()
  const {
    track,
    trackChangeSlide,
    shuffleOn,
    repeatMode,
  } = usePlayerMeta()
  const {
    togglePlay,
    playNext,
    playPrev,
    openCard,
    openQueue,
    openEq,
    stop,
    toggleShuffle,
    toggleRepeat,
    seek,
    getPreciseTime,
    radioMode,
    getAnalyser,
  } = usePlayerActions()
  const { isLiked, toggleLike } = useLikes()
  const telegramUserId = getUserId()

  const [likeBurst, setLikeBurst] = useState(false)
  const [overflowOpen, setOverflowOpen] = useState(false)
  const [addToPlOpen, setAddToPlOpen] = useState(false)
  const [swipeDx, setSwipeDx] = useState(0)
  const [palette, setPalette] =
    useState<CoverPalette | null>(null)
  const overflowRef = useRef<HTMLDivElement>(null)
  const shellRef = useRef<HTMLDivElement>(null)
  const seekInputRef = useRef<HTMLInputElement>(null)
  const seekWrapRef = useRef<HTMLDivElement>(null)
  const seekDraggingRef = useRef(false)

  useEffect(() => {
    const el = seekInputRef.current
    const wrap = seekWrapRef.current
    if (!el || !wrap) return
    const write = () => {
      const t = getPreciseTime()
      const pct = duration
        ? Math.max(0, Math.min(100, (t / duration) * 100))
        : 0
      if (!seekDraggingRef.current) {
        el.value = String(pct)
      }
      shellRef.current?.style.setProperty(
        '--progress',
        `${pct}%`,
      )
      wrap.style.setProperty('--progress', `${pct}%`)
    }
    write()
    if (!isPlaying) return
    let rafId = 0
    let lastPaint = 0
    const frameMs = isPerfLiteActive() ? 1000 / 30 : 1000 / 60
    const frame = (now: number) => {
      if (now - lastPaint >= frameMs) {
        lastPaint = now
        write()
      }
      rafId = requestAnimationFrame(frame)
    }
    rafId = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(rafId)
  }, [isPlaying, track?.id, duration, getPreciseTime])

  const barSwipe = useSwipeX({
    threshold: SWIPE_THRESHOLD,
    onProgress: setSwipeDx,
    onSwipeLeft: () => {
      haptic('light')
      void playNext()
    },
    onSwipeRight: () => {
      haptic('light')
      void playPrev()
    },
    // Временно: свайп вверх не открывает карточку трека (openCard).
    // onSwipeUp: () => {
    //   haptic('medium')
    //   openCard()
    // },
  })

  useEffect(() => {
    if (!overflowOpen) return
    const handler = (e: globalThis.MouseEvent) => {
      if (
        !overflowRef.current?.contains(
          e.target as Node,
        )
      ) {
        setOverflowOpen(false)
      }
    }
    document.addEventListener('pointerdown', handler)
    return () =>
      document.removeEventListener(
        'pointerdown',
        handler,
      )
  }, [overflowOpen])

  const coverSrc = track?.cover_key
    ? coverProxyUrl(track.cover_key, { width: 120 })
    : null
  const waveBars = useMemo(
    () => buildMiniWaveBars(track?.waveform_data),
    [track?.id, track?.waveform_data],
  )

  useEffect(() => {
    let cancelled = false
    if (!coverSrc) {
      setPalette(null)
      return
    }
    void extractCoverPalette(coverSrc).then((p) => {
      if (!cancelled) {
        setPalette(p)
      }
    })
    return () => {
      cancelled = true
    }
  }, [coverSrc])

  if (!track) return null

  const liked = isLiked(track.id)
  const coverSrcSet = track.cover_key
    ? coverProxySrcSet(track.cover_key)
    : undefined
  const bpm = (track as unknown as { bpm?: number }).bpm
  const tapBpm = typeof bpm === 'number' ? bpm : 120
  const animKey = `${track.id}-${trackChangeSlide.bump}`
  const shellStyle = {
    '--mp-cover-image': coverSrc ? `url("${coverSrc}")` : 'none',
    '--mp-tone-a': palette?.tones[0] ?? 'rgba(255,255,255,0.18)',
    '--mp-tone-b': palette?.tones[1] ?? 'rgba(255,255,255,0.10)',
    '--mp-tone-c': palette?.tones[2] ?? 'rgba(0,0,0,0.44)',
  } as CSSProperties

  const handleLikeClick = async () => {
    if (!liked) {
      setLikeBurst(true)
      window.setTimeout(() => setLikeBurst(false), 420)
    }
    haptic(liked ? 'light' : 'medium')
    await toggleLike(track.id, track)
  }

  return (
    <>
      <div
        ref={shellRef}
        className="mp-shell"
        style={shellStyle}
      >
      {/* Seek bar — top of player bar, full width */}
      <div
        ref={seekWrapRef}
        className="mp-seek-wrap"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="mp-wave-track" aria-hidden="true">
          <div className="mp-wave-bars">
            {waveBars.map((height, index) => (
              <span
                key={`idle-${index}`}
                style={
                  {
                    '--mp-wave-h': `${height}%`,
                  } as CSSProperties
                }
              />
            ))}
          </div>
          <div className="mp-wave-fill">
            <div className="mp-wave-bars">
              {waveBars.map((height, index) => (
                <span
                  key={`fill-${index}`}
                  style={
                    {
                      '--mp-wave-h': `${height}%`,
                    } as CSSProperties
                  }
                />
              ))}
            </div>
          </div>
        </div>
        <input
          ref={seekInputRef}
          type="range"
          className="mp-seek"
          min={0}
          max={100}
          step={0.1}
          defaultValue={0}
          aria-label="Перемотка"
          onPointerDown={() => {
            seekDraggingRef.current = true
          }}
          onPointerUp={() => {
            seekDraggingRef.current = false
          }}
          onPointerCancel={() => {
            seekDraggingRef.current = false
          }}
          onChange={(e) =>
            seek(Number(e.currentTarget.value))
          }
        />
      </div>

      <div
        className="mp-zone"
        {...barSwipe}
      >
        {/* Swipeable content: cover + info — slides horizontally on drag */}
        <div
          className="mp-swipe-content"
          style={{
            transform: `translateX(${
              swipeDx * 0.45
            }px)`,
            transition:
              swipeDx === 0
                ? 'transform 220ms cubic-bezier(0.32,0,0.18,1)'
                : 'none',
            willChange:
              swipeDx !== 0 ? 'transform' : 'auto',
          }}
        >
          {/* Cover — scale pop on track change */}
          <div
            className="mp-cover"
            onClick={() => {
              haptic('light')
              openCard()
            }}
          >
            <AnimatePresence
              initial={false}
              mode="wait"
            >
              <m.div
                key={animKey}
                className="mp-cover-frame"
                initial={
                  reduce
                    ? { opacity: 0 }
                    : { opacity: 0, scale: 0.76 }
                }
                animate={{ opacity: 1, scale: 1 }}
                exit={
                  reduce
                    ? { opacity: 0 }
                    : { opacity: 0, scale: 1.14 }
                }
                transition={COVER_SPRING}
              >
                <SharedCover
                  trackId={track.id}
                  src={coverSrc}
                  srcSet={coverSrcSet}
                  sizes={coverProxySizes(56)}
                  alt=""
                  className="mp-cover-img"
                />
                {/*
                  SharedCover already renders a styled empty/error
                  fallback when src is null OR when the image
                  request fails (404 / SW miss / CDN stall). We
                  used to gate on coverSrc and fall through to a
                  bare ``<Icon name="music" />`` which on small
                  displays looked like the broken-image glyph next
                  to a stray "site logo" tile.
                */}
              </m.div>
            </AnimatePresence>
          </div>

          {/* Track info — slide-up on track change */}
          <div
            className="mp-info"
            onClick={() => {
              haptic('light')
              openCard()
            }}
          >
            <AnimatePresence
              initial={false}
              mode="wait"
            >
              <m.div
                key={animKey}
                className="mp-info-body"
                initial={
                  reduce
                    ? { opacity: 0 }
                    : { opacity: 0, y: 9 }
                }
                animate={{ opacity: 1, y: 0 }}
                exit={
                  reduce
                    ? { opacity: 0 }
                    : { opacity: 0, y: -6 }
                }
                transition={INFO_EASE}
              >
                <p className="mp-title">
                  {track.title}
                </p>
                <p className="mp-artist">
                  {track.artist ?? '—'}
                </p>
              </m.div>
            </AnimatePresence>
          </div>
        </div>

        {/* Controls — pointer isolated, no swipe from here */}
        <div
          className="mp-actions"
          onPointerDown={(e) => e.stopPropagation()}
        >
          {radioMode && (
            <button
              type="button"
              className="mp-live-badge"
              onClick={(e) => {
                e.stopPropagation()
                haptic('light')
                navigate('/radio')
              }}
              aria-label={t('redesign.playerBar.radioMode')}
            >
              <SpectrumMicroBars
                active={isPlaying}
                getAnalyser={getAnalyser}
              />
            </button>
          )}

          <div className="mp-transport">
          <button
            className="mp-btn mp-btn--skip"
            onClick={() => {
              haptic('light')
              void playPrev()
            }}
            aria-label="Предыдущий"
          >
            <Icon name="skip-back" size={16} />
          </button>

          <button
            className={`mp-btn mp-btn--play${
              isPlaying ? ' mp-btn--playing' : ''
            }`}
            onClick={() => {
              haptic('light')
              togglePlay()
            }}
            aria-label={
              isPlaying ? 'Пауза' : 'Воспроизвести'
            }
          >
            <BeatPulse bpm={tapBpm} active={isPlaying}>
              <MorphIcon
                name={isPlaying ? 'pause' : 'play'}
                filled
                size={18}
              />
            </BeatPulse>
          </button>

          <button
            className="mp-btn mp-btn--skip"
            onClick={() => {
              haptic('light')
              void playNext()
            }}
            aria-label="Следующий"
          >
            <Icon name="skip-forward" size={16} />
          </button>
          </div>

          <button
            className={`mp-btn mp-btn--like${
              liked ? ' mp-btn--liked' : ''
            }${likeBurst ? ' mp-btn--burst' : ''}`}
            onClick={async () => {
              await handleLikeClick()
            }}
            aria-label={
              liked ? 'Убрать лайк' : 'Лайк'
            }
            aria-pressed={liked}
          >
            <MorphIcon
              name="heart"
              filled={liked}
              size={16}
            />
          </button>

          <div
            className="mp-overflow-wrap"
            ref={overflowRef}
          >
            <button
              className="mp-btn mp-btn--more"
              onClick={() =>
                setOverflowOpen((v) => !v)
              }
              aria-label="Дополнительно"
              aria-expanded={overflowOpen}
              aria-haspopup="menu"
            >
              <Icon
                name="more-horizontal"
                size={16}
              />
            </button>

            {overflowOpen && (
              <div
                className="mp-overflow-menu"
                role="menu"
              >
                <button
                  className="mp-menu-item"
                  role="menuitem"
                  onClick={() => {
                    setOverflowOpen(false)
                    haptic('light')
                    openQueue()
                  }}
                >
                  <Icon name="queue" size={14} />
                  {t('redesign.playerBar.queueMenu')}
                </button>
                {telegramUserId ? (
                  <button
                    className="mp-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setOverflowOpen(false)
                      haptic('light')
                      setAddToPlOpen(true)
                    }}
                  >
                    <Icon name="list" size={14} />
                    {t(
                      'redesign.playerBar.addToPlaylistMenu',
                    )}
                  </button>
                ) : null}
                <button
                  className="mp-menu-item"
                  role="menuitem"
                  onClick={() => {
                    setOverflowOpen(false)
                    haptic('light')
                    openEq()
                  }}
                >
                  <Icon name="eq" size={14} />
                  {t('redesign.playerBar.eqMenu')}
                </button>
                <button
                  className={`mp-menu-item${
                    shuffleOn
                      ? ' mp-menu-item--active'
                      : ''
                  }`}
                  role="menuitem"
                  onClick={() => {
                    toggleShuffle()
                    setOverflowOpen(false)
                    haptic('light')
                  }}
                >
                  <Icon name="shuffle" size={14} />
                  {t(
                    'redesign.playerBar.shuffleMenu',
                  )}
                </button>
                <button
                  className={`mp-menu-item${
                    repeatMode !== 'none'
                      ? ' mp-menu-item--active'
                      : ''
                  }`}
                  role="menuitem"
                  onClick={() => {
                    toggleRepeat()
                    setOverflowOpen(false)
                    haptic('light')
                  }}
                >
                  <Icon
                    name={
                      repeatMode === 'one'
                        ? 'repeat-one'
                        : 'repeat'
                    }
                    size={14}
                  />
                  {repeatMode === 'none'
                    ? 'Повтор выкл.'
                    : repeatMode === 'one'
                      ? 'Повтор трека'
                      : 'Повтор всех'}
                </button>
                <button
                  className="mp-menu-item mp-menu-item--danger"
                  role="menuitem"
                  onClick={() => {
                    setOverflowOpen(false)
                    haptic('light')
                    stop()
                  }}
                >
                  <Icon name="x" size={14} />
                  {t('redesign.playerBar.stopMenu')}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div
        className="mp-touch-bottom-fill"
        aria-hidden
      />
      </div>

      {telegramUserId ? (
        <AddToPlaylistSheet
          open={addToPlOpen}
          onClose={() => setAddToPlOpen(false)}
          trackId={track.id}
        />
      ) : null}
    </>
  )
}
