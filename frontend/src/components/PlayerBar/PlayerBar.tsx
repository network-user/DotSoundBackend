import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
} from 'react'
import {
  PlayerBarSeek,
  PlayerBarTime,
} from './PlayerBarProgress'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { type PanInfo } from 'framer-motion'
import { Icon } from '@/components/Icon/Icon'
import { useLikes } from '@/store/LikesContext'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerPlayback,
} from '@/store/PlayerContext'
import { getUserId, haptic } from '@/lib/telegram'
import { useRipple } from '@/components/ui/Ripple'
import {
  m,
  SPRING_GENTLE,
  useReducedMotion,
} from '@/lib/motion'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { SharedCover } from '@/components/ui/SharedCover'
import { useMatchMedia } from '@/hooks/useMatchMedia'
import { useDesktopFinePointer } from '@/hooks/useDesktopFinePointer'
import { useNavigateToArtistByName } from '@/hooks/useNavigateToArtistByName'
import { AddToPlaylistSheet } from '@/components/AddToPlaylistSheet/AddToPlaylistSheet'

const PLATFORM_LABELS: Record<string, string> = {
  youtube: 'YouTube',
  bandcamp: 'Bandcamp',
  vk: 'VK Музыка',
  yandex: 'Яндекс Музыка',
}

const SWIPE_UP_THRESHOLD = 80

export function PlayerBar() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const { duration, isPlaying } = usePlayerPlayback()
  const {
    track,
    volume,
    repeatMode,
    shuffleOn,
    hlsError,
  } = usePlayerMeta()
  const {
    togglePlay,
    seek,
    getPreciseTime,
    playNext,
    playPrev,
    openCard,
    openEq,
    openQueue,
    stop,
    setVolume,
    toggleRepeat,
    toggleShuffle,
    clearHlsError,
    radioMode,
  } = usePlayerActions()
  const { isLiked, toggleLike } = useLikes()
  const showBarVolume = useMatchMedia('(min-width: 561px)')
  const desktopFineNav = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()
  const [likeBurst, setLikeBurst] = useState(false)
  const [overflowOpen, setOverflowOpen] = useState(false)
  const [addToPlOpen, setAddToPlOpen] = useState(false)
  const [volumePinned, setVolumePinned] = useState(false)
  const [volumeHover, setVolumeHover] = useState(false)
  const overflowRef = useRef<HTMLDivElement>(null)
  const volumeRef = useRef<HTMLDivElement>(null)
  const volumeCloseTimerRef = useRef<number | null>(null)
  const playRef = useRef<HTMLButtonElement>(null)
  const playerBarRef = useRef<HTMLDivElement>(null)
  useRipple(playRef)

  const volumeOpen =
    showBarVolume && (volumePinned || volumeHover)

  const clearVolumeCloseTimer = () => {
    if (volumeCloseTimerRef.current !== null) {
      window.clearTimeout(volumeCloseTimerRef.current)
      volumeCloseTimerRef.current = null
    }
  }

  const scheduleVolumeClose = () => {
    clearVolumeCloseTimer()
    volumeCloseTimerRef.current = window.setTimeout(() => {
      setVolumeHover(false)
      volumeCloseTimerRef.current = null
    }, 180)
  }

  useEffect(() => {
    if (!showBarVolume) {
      clearVolumeCloseTimer()
      setVolumePinned(false)
      setVolumeHover(false)
    }
  }, [showBarVolume])

  useEffect(() => {
    if (!overflowOpen && !volumeOpen) return
    const onDocClick = (
      e: globalThis.MouseEvent,
    ) => {
      const target = e.target as Node
      const inOverflow =
        overflowRef.current?.contains(target) ?? false
      const inVolume =
        volumeRef.current?.contains(target) ?? false
      if (!inOverflow) setOverflowOpen(false)
      if (!inVolume) {
        clearVolumeCloseTimer()
        setVolumePinned(false)
        setVolumeHover(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        clearVolumeCloseTimer()
        setOverflowOpen(false)
        setVolumePinned(false)
        setVolumeHover(false)
      }
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
      clearVolumeCloseTimer()
    }
  }, [overflowOpen, volumeOpen])

  if (!track) return null

  const liked = isLiked(track.id)

  const coverSrc = track.cover_key
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(track.cover_key)}`
    : null

  const handleOpenCard = (e: MouseEvent) => {
    e.stopPropagation()
    openCard()
  }

  const runLikeToggle = async () => {
    if (!liked) {
      setLikeBurst(true)
      window.setTimeout(
        () => setLikeBurst(false),
        420,
      )
    }
    haptic(liked ? 'light' : 'medium')
    await toggleLike(track.id, track)
  }

  const handleLike = async (e: MouseEvent) => {
    e.stopPropagation()
    await runLikeToggle()
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

  const repeatTitle =
    repeatMode === 'none'
      ? 'Повтор выкл.'
      : repeatMode === 'one'
        ? 'Повтор трека'
        : 'Повтор всех'

  const trackBpm = (track as unknown as { bpm?: number }).bpm
  const tapBpm =
    typeof trackBpm === 'number' ? trackBpm : 120
  const volumePct = Math.round(volume * 100)
  const volumeIcon =
    volume <= 0.01
      ? 'volume-off'
      : volume < 0.5
        ? 'volume-low'
        : 'volume-high'
  const telegramUserId = getUserId()

  return (
    <>
    <m.div
      ref={playerBarRef}
      id="player-bar"
      className="rp-player-bar"
      drag={reduce ? false : 'y'}
      dragConstraints={{ top: -8, bottom: 0 }}
      dragElastic={0.25}
      dragMomentum={false}
      onDragEnd={handleDragEnd}
      transition={SPRING_GENTLE}
    >
      <span
        className="rp-player-bar__hint"
        aria-hidden="true"
      />
      <PlayerBarSeek
        duration={duration}
        trackId={track.id}
        isPlaying={isPlaying}
        getPreciseTime={getPreciseTime}
        onSeek={seek}
        parentRef={playerBarRef}
      />

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
              <Icon name="music" size={20} />
            )}
          </div>
        </div>

        <div
          id="pb-info"
          className={
            desktopFineNav ? undefined : 'pb-clickable'
          }
          onClick={
            desktopFineNav ? undefined : handleOpenCard
          }
        >
          <div
            key={track.id}
            className="pb-info-meta"
          >
            <div
              className={
                desktopFineNav ? 'pb-clickable' : undefined
              }
              onClick={
                desktopFineNav
                  ? handleOpenCard
                  : undefined
              }
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
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                minWidth: 0,
              }}
            >
              {radioMode && (
                <MotionPress
                  variant="ghost"
                  haptic="selection"
                  className="player-radio-pill"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate('/radio')
                  }}
                  title={t('redesign.playerBar.radioMode')}
                  ariaLabel={t('redesign.playerBar.radioMode')}
                >
                  <span
                    className="player-radio-pill__waves"
                    aria-hidden="true"
                  >
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className="player-radio-pill__label">
                    LIVE
                  </span>
                </MotionPress>
              )}
              <p
                className={
                  desktopFineNav && track.artist
                    ? 'pb-artist hint pb-artist--nav'
                    : 'pb-artist hint'
                }
                dir="auto"
                style={
                  desktopFineNav && track.artist
                    ? {
                        cursor: 'pointer',
                        flex: 1,
                        minWidth: 0,
                      }
                    : { flex: 1, minWidth: 0 }
                }
                onClick={
                  desktopFineNav && track.artist
                    ? (e) => {
                        e.stopPropagation()
                        void goArtistByName(track.artist)
                      }
                    : undefined
                }
              >
                {track.artist ?? '—'}
              </p>
            </div>
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
          {showBarVolume ? (
            <div
              className="pb-volume-wrap"
              ref={volumeRef}
              onMouseEnter={() => {
                clearVolumeCloseTimer()
                setVolumeHover(true)
              }}
              onMouseLeave={() => {
                if (!volumePinned) {
                  scheduleVolumeClose()
                }
              }}
              onFocusCapture={() => {
                clearVolumeCloseTimer()
                setVolumeHover(true)
              }}
              onBlurCapture={(e) => {
                if (
                  !e.currentTarget.contains(
                    e.relatedTarget as Node | null,
                  )
                ) {
                  if (!volumePinned) {
                    scheduleVolumeClose()
                  }
                }
              }}
            >
              <MotionPress
                variant="icon"
                className="ctrl-btn pb-volume-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  clearVolumeCloseTimer()
                  setVolumePinned((v) => !v)
                  setOverflowOpen(false)
                }}
                ariaLabel="Громкость"
                aria-expanded={volumeOpen}
                aria-haspopup="dialog"
              >
                <Icon
                  name={volumeIcon}
                  size={18}
                />
              </MotionPress>
              {volumeOpen && (
                <div
                  className="pb-volume-pop"
                  role="dialog"
                  aria-label="Регулировка громкости"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="pb-volume-slider-wrap">
                    <input
                      type="range"
                      className="pb-volume-slider"
                      min={0}
                      max={100}
                      step={1}
                      value={volumePct}
                      style={
                        {
                          '--progress': `${volumePct}%`,
                        } as CSSProperties
                      }
                      onChange={(e) =>
                        setVolume(
                          Number(e.currentTarget.value) / 100,
                        )
                      }
                      aria-label="Громкость плеера"
                    />
                  </div>
                  <div className="pb-volume-value">
                    {volumePct}%
                  </div>
                </div>
              )}
            </div>
          ) : null}
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
          <div className="pb-overflow-wrap" ref={overflowRef}>
            <MotionPress
              variant="icon"
              className="ctrl-btn pb-overflow-btn"
              onClick={(e) => {
                e.stopPropagation()
                setOverflowOpen((v) => !v)
                clearVolumeCloseTimer()
                setVolumePinned(false)
                setVolumeHover(false)
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
                {telegramUserId ? (
                  <MotionPress
                    role="menuitem"
                    variant="ghost"
                    haptic="selection"
                    className="pb-menu-item"
                    onClick={() => {
                      setOverflowOpen(false)
                      setAddToPlOpen(true)
                    }}
                  >
                    <Icon name="list" size={16} />
                    {t('redesign.playerBar.addToPlaylistMenu')}
                  </MotionPress>
                ) : null}
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

      <PlayerBarTime
        duration={duration}
        trackId={track.id}
        isPlaying={isPlaying}
        getPreciseTime={getPreciseTime}
      />

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
