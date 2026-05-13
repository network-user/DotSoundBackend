import {
  useEffect,
  useRef,
  useState,
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
  const overflowRef = useRef<HTMLDivElement>(null)
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
      wrap.style.setProperty('--progress', `${pct}%`)
    }
    write()
    if (!isPlaying) return
    let rafId = 0
    const frame = () => {
      write()
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

  if (!track) return null

  const liked = isLiked(track.id)
  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null
  const bpm = (track as unknown as { bpm?: number }).bpm
  const tapBpm = typeof bpm === 'number' ? bpm : 120
  const animKey = `${track.id}-${trackChangeSlide.bump}`

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
      {/* Seek bar — top of player bar, full width */}
      <div
        ref={seekWrapRef}
        className="mp-seek-wrap"
        onPointerDown={(e) => e.stopPropagation()}
      >
        {/* div-overlay: avoids WebKit pseudo-element CSS var bug */}
        <div
          className="mp-seek-track"
          aria-hidden="true"
        />
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
                {coverSrc ? (
                  <SharedCover
                    trackId={track.id}
                    src={coverSrc}
                    alt=""
                    className="mp-cover-img"
                  />
                ) : (
                  <div className="mp-cover-empty">
                    <Icon name="music" size={18} />
                  </div>
                )}
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

          <button
            className={`mp-btn${
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
              className="mp-btn"
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
