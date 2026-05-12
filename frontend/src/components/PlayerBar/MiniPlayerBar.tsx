import {
  useEffect,
  useRef,
  useState,
} from 'react'
import {
  AnimatePresence,
  type PanInfo,
  useMotionValue,
  useTransform,
} from 'framer-motion'
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
import { AddToPlaylistSheet } from '@/components/AddToPlaylistSheet/AddToPlaylistSheet'

const SWIPE_X_PX = 54
const SWIPE_VX = 350

const COVER_SPRING = {
  type: 'spring' as const,
  stiffness: 340,
  damping: 24,
  mass: 0.7,
}
const INFO_EASE = {
  duration: 0.16,
  ease: [0.32, 0, 0.18, 1] as [number, number, number, number],
}

export function MiniPlayerBar() {
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const { isPlaying } = usePlayerPlayback()
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
  } = usePlayerActions()
  const { isLiked, toggleLike } = useLikes()
  const telegramUserId = getUserId()

  const [likeBurst, setLikeBurst] = useState(false)
  const [overflowOpen, setOverflowOpen] = useState(false)
  const [addToPlOpen, setAddToPlOpen] = useState(false)
  const overflowRef = useRef<HTMLDivElement>(null)

  const x = useMotionValue(0)
  const prevOpacity = useTransform(
    x,
    [0, SWIPE_X_PX * 0.4, SWIPE_X_PX],
    [0, 0.4, 0.85],
  )
  const nextOpacity = useTransform(
    x,
    [-SWIPE_X_PX, -SWIPE_X_PX * 0.4, 0],
    [0.85, 0.4, 0],
  )

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

  const handleDragEnd = (_: unknown, info: PanInfo) => {
    const ox = info.offset.x
    const vx = info.velocity.x
    if (ox < -SWIPE_X_PX || vx < -SWIPE_VX) {
      haptic('light')
      void playNext()
    } else if (ox > SWIPE_X_PX || vx > SWIPE_VX) {
      haptic('light')
      void playPrev()
    }
  }

  const handleLikeClick = async () => {
    if (!liked) {
      setLikeBurst(true)
      window.setTimeout(() => setLikeBurst(false), 420)
    }
    haptic(liked ? 'light' : 'medium')
    await toggleLike(track.id, track)
  }

  const animKey = `${track.id}-${trackChangeSlide.bump}`

  return (
    <>
      <m.div
        className="mp-zone"
        drag={reduce ? false : 'x'}
        dragConstraints={{ left: -120, right: 120 }}
        dragElastic={0.14}
        dragMomentum={false}
        dragTransition={{
          bounceStiffness: 500,
          bounceDamping: 40,
        }}
        style={{ x }}
        onDragEnd={handleDragEnd}
      >
        {/* Swipe direction hints — fade in on drag */}
        <m.span
          className="mp-dir mp-dir--prev"
          style={{ opacity: prevOpacity }}
          aria-hidden="true"
        >
          <Icon name="skip-back" size={13} />
        </m.span>
        <m.span
          className="mp-dir mp-dir--next"
          style={{ opacity: nextOpacity }}
          aria-hidden="true"
        >
          <Icon name="skip-forward" size={13} />
        </m.span>

        {/* Cover — scale pop on track change */}
        <div
          className="mp-cover"
          onClick={() => openCard()}
        >
          <AnimatePresence initial={false} mode="wait">
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
          onClick={() => openCard()}
        >
          <AnimatePresence initial={false} mode="wait">
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
              <p className="mp-title">{track.title}</p>
              <p className="mp-artist">
                {track.artist ?? '—'}
              </p>
            </m.div>
          </AnimatePresence>
        </div>

        {/* Controls — pointer events isolated, no drag */}
        <div
          className="mp-actions"
          onPointerDown={(e) => e.stopPropagation()}
        >
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
              <Icon name="more-horizontal" size={16} />
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
      </m.div>

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
