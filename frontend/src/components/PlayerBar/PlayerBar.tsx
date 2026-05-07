import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { type PanInfo } from 'framer-motion'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import { haptic } from '@/lib/telegram'
import { useRipple } from '@/components/ui/Ripple'
import {
  m,
  SPRING_GENTLE,
  SPRING_SNAPPY,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { SharedCover } from '@/components/ui/SharedCover'

const PLATFORM_LABELS: Record<string, string> = {
  youtube: 'YouTube',
  bandcamp: 'Bandcamp',
  vk: 'VK Музыка',
  yandex: 'Яндекс Музыка',
}

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

const SWIPE_UP_THRESHOLD = 80

export function PlayerBar() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const {
    currentTime,
    duration,
    isPlaying,
  } = usePlayerState()
  const {
    track,
    repeatMode,
    shuffleOn,
    hlsError,
  } = usePlayerMeta()
  const {
    togglePlay,
    seek,
    playNext,
    playPrev,
    openCard,
    openEq,
    openQueue,
    stop,
    toggleRepeat,
    toggleShuffle,
    clearHlsError,
    radioMode,
  } = usePlayerActions()
  const { isLiked, toggleLike } = useLikes()
  const [likeBurst, setLikeBurst] = useState(false)
  const [overflowOpen, setOverflowOpen] = useState(false)
  const [smoothPct, setSmoothPct] = useState(0)
  const overflowRef = useRef<HTMLDivElement>(null)
  const playRef = useRef<HTMLButtonElement>(null)
  useRipple(playRef)
  const targetPct = duration ? (currentTime / duration) * 100 : 0

  useEffect(() => {
    const next = Math.max(0, Math.min(100, targetPct))
    setSmoothPct((prev) => {
      const diff = next - prev
      if (Math.abs(diff) < 0.12) return next
      const step = isPlaying ? 0.24 : 0.36
      return prev + diff * step
    })
  }, [targetPct, isPlaying])

  useEffect(() => {
    if (!overflowOpen) return
    const onDocClick = (
      e: globalThis.MouseEvent,
    ) => {
      if (
        overflowRef.current &&
        !overflowRef.current.contains(e.target as Node)
      ) {
        setOverflowOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape')
        setOverflowOpen(false)
    }
    document.addEventListener(
      'pointerdown',
      onDocClick,
    )
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener(
        'pointerdown',
        onDocClick,
      )
      window.removeEventListener('keydown', onKey)
    }
  }, [overflowOpen])

  if (!track) return null

  const pct = smoothPct
  const liked = isLiked(track.id)

  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null

  const handleOpenCard = (e: MouseEvent) => {
    e.stopPropagation()
    openCard()
  }

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!liked) {
      setLikeBurst(true)
      window.setTimeout(
        () => setLikeBurst(false),
        420,
      )
    }
    haptic(liked ? 'light' : 'medium')
    await toggleLike(track.id)
  }

  const handlePlay = (e: MouseEvent) => {
    e.stopPropagation()
    haptic('light')
    togglePlay()
  }

  const handleNext = (e: MouseEvent) => {
    e.stopPropagation()
    haptic('light')
    playNext()
  }

  const handlePrev = (e: MouseEvent) => {
    e.stopPropagation()
    haptic('light')
    playPrev()
  }

  const handleDragEnd = (
    _: unknown,
    info: PanInfo,
  ) => {
    if (info.offset.y < -SWIPE_UP_THRESHOLD) {
      haptic('medium')
      navigate('/now-playing')
    }
  }

  const seekStyle = {
    '--progress': `${pct}%`,
  } as CSSProperties

  const repeatTitle =
    repeatMode === 'none'
      ? 'Повтор выкл.'
      : repeatMode === 'one'
        ? 'Повтор трека'
        : 'Повтор всех'

  const trackBpm = (track as unknown as { bpm?: number }).bpm
  const tapBpm =
    typeof trackBpm === 'number' ? trackBpm : 120

  return (
    <m.div
      id="player-bar"
      className="rp-player-bar"
      drag={reduce ? false : 'y'}
      dragConstraints={{ top: -8, bottom: 0 }}
      dragElastic={0.25}
      dragMomentum={false}
      onDragEnd={handleDragEnd}
      transition={SPRING_GENTLE}
    >
      <div
        id="pb-seek-wrap"
        className="pb-seek-zone rp-player-seek"
      >
        <m.input
          type="range"
          id="pb-seek"
          min={0}
          max={100}
          step={0.1}
          value={pct}
          style={seekStyle}
          aria-label="Перемотка трека"
          onChange={(e) =>
            seek(Number(e.currentTarget.value))
          }
          whileTap={
            reduce ? undefined : { scaleY: 1.5 }
          }
          transition={SPRING_SNAPPY}
        />
      </div>

      <div id="pb-row" className="pb-row-v2">
        <div
          className="pb-cover-img pb-clickable pb-cover-with-viz rp-player-cover"
          onClick={handleOpenCard}
        >
          <div className="pb-cover-inner">
            {coverSrc ? (
              <SharedCover
                trackId={track.id}
                src={coverSrc}
                alt=""
                className="pb-cover-vt"
              />
            ) : (
              <Icon name="music" size={18} />
            )}
          </div>
        </div>

        <div
          id="pb-info"
          className="pb-clickable"
          onClick={handleOpenCard}
        >
          <div
            key={track.id}
            className="pb-info-meta"
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                minWidth: 0,
              }}
            >
              <p
                className="pb-title"
                style={{ flex: 1, minWidth: 0 }}
                dir="auto"
              >
                {track.title}
              </p>
              {radioMode && (
                <MotionPress
                  variant="ghost"
                  haptic="selection"
                  className="player-radio-badge player-radio-badge--active"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate('/radio')
                  }}
                  title={t('redesign.playerBar.radioMode')}
                >
                  <span className="player-radio-badge__dot" />
                  {t('redesign.playerBar.radioMode')}
                </MotionPress>
              )}
            </div>
            <p
              className="pb-artist hint"
              dir="auto"
            >
              {track.artist ?? '—'}
            </p>
          </div>
          {track.source_platform &&
            track.source_platform !== 'soundcloud' &&
            track.source_url && (
              <a
                className="pb-source-link"
                href={track.source_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) =>
                  e.stopPropagation()
                }
                title={`Слушать на ${PLATFORM_LABELS[track.source_platform] ?? track.source_platform}`}
              >
                <Icon
                  name={`source-${track.source_platform}`}
                  size={12}
                />
                <span>
                  {PLATFORM_LABELS[
                    track.source_platform
                  ] ?? track.source_platform}
                </span>
              </a>
            )}
        </div>

        <div id="pb-controls" className="pb-ctl-v2">
          <MotionPress
            variant="icon"
            className="ctrl-btn pb-prev"
            onClick={handlePrev}
            ariaLabel="Предыдущий"
            haptic="light"
          >
            <Icon name="skip-back" size={18} />
          </MotionPress>
          <MotionPress
            ref={playRef}
            variant="icon"
            className={`play-btn${
              isPlaying ? ' play-btn--playing' : ''
            }`}
            onClick={handlePlay}
            ariaLabel={
              isPlaying ? 'Пауза' : 'Воспроизвести'
            }
            haptic="light"
          >
            <BeatPulse
              bpm={tapBpm}
              active={isPlaying}
            >
              <MorphIcon
                name={isPlaying ? 'pause' : 'play'}
                filled
                size={18}
              />
            </BeatPulse>
          </MotionPress>
          <MotionPress
            variant="icon"
            className="ctrl-btn"
            onClick={handleNext}
            ariaLabel="Следующий"
            haptic="light"
          >
            <Icon name="skip-forward" size={18} />
          </MotionPress>
          <MotionPress
            variant="icon"
            className={`icon-btn pb-like${liked ? ' liked' : ''}${
              likeBurst ? ' pb-like-burst' : ''
            }`}
            onClick={handleLike}
            ariaLabel={
              liked ? 'Убрать лайк' : 'Лайк'
            }
            aria-pressed={liked}
            haptic={liked ? 'light' : 'medium'}
          >
            <MorphIcon
              name="heart"
              filled={liked}
              size={18}
            />
          </MotionPress>
          <div
            className="pb-overflow-wrap"
            ref={overflowRef}
          >
            <MotionPress
              variant="icon"
              className="ctrl-btn pb-overflow-btn"
              onClick={(e) => {
                e.stopPropagation()
                setOverflowOpen((v) => !v)
              }}
              ariaLabel="Дополнительно"
              aria-expanded={overflowOpen}
              aria-haspopup="menu"
            >
              <Icon
                name="more-horizontal"
                size={18}
              />
            </MotionPress>
            {overflowOpen && (
              <div
                className="pb-overflow-menu"
                role="menu"
              >
                <MotionPress
                  role="menuitem"
                  variant="ghost"
                  haptic="selection"
                  className="pb-menu-item"
                  onClick={() => {
                    setOverflowOpen(false)
                    openQueue()
                  }}
                >
                  <Icon name="queue" size={16} />
                  {t('redesign.playerBar.queueMenu')}
                </MotionPress>
                <MotionPress
                  role="menuitem"
                  variant="ghost"
                  haptic="selection"
                  className="pb-menu-item"
                  onClick={() => {
                    setOverflowOpen(false)
                    openEq()
                  }}
                >
                  <Icon name="eq" size={16} />
                  {t('redesign.playerBar.eqMenu')}
                </MotionPress>
                <MotionPress
                  role="menuitem"
                  variant="ghost"
                  haptic="selection"
                  className={`pb-menu-item ${shuffleOn ? 'active' : ''}`}
                  onClick={() => {
                    toggleShuffle()
                    setOverflowOpen(false)
                  }}
                >
                  <Icon name="shuffle" size={16} />
                  {t('redesign.playerBar.shuffleMenu')}
                </MotionPress>
                <MotionPress
                  role="menuitem"
                  variant="ghost"
                  haptic="selection"
                  className={`pb-menu-item ${repeatMode !== 'none' ? 'active' : ''}`}
                  onClick={() => {
                    toggleRepeat()
                    setOverflowOpen(false)
                  }}
                  title={repeatTitle}
                >
                  <Icon
                    name={
                      repeatMode === 'one'
                        ? 'repeat-one'
                        : 'repeat'
                    }
                    size={16}
                  />
                  {repeatTitle}
                </MotionPress>
                <MotionPress
                  role="menuitem"
                  variant="ghost"
                  haptic="selection"
                  className="pb-menu-item pb-menu-item-danger"
                  onClick={() => {
                    setOverflowOpen(false)
                    stop()
                  }}
                >
                  <Icon name="x" size={16} />
                  {t('redesign.playerBar.stopMenu')}
                </MotionPress>
              </div>
            )}
          </div>
        </div>
      </div>

      <div id="pb-time">
        <span>{fmt(currentTime)}</span>
        <span>{fmt(duration)}</span>
      </div>

      {hlsError && (
        <div
          className="pb-error-toast"
          onClick={clearHlsError}
          role="button"
          aria-label="Закрыть ошибку"
        >
          <span>{hlsError}</span>
          <Icon name="x" size={14} />
        </div>
      )}
    </m.div>
  )
}
