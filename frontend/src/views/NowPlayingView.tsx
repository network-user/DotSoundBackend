import {
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, type PanInfo } from 'framer-motion'
import {
  m,
  SPRING_GENTLE,
  TWEEN_FAST,
  useReducedMotion,
} from '@/lib/motion'
import {
  usePlayerActions,
  usePlayerMeta,
  usePlayerState,
} from '@/store/PlayerContext'
import { getInternalUserId, getIsAdmin } from '@/lib/telegram'
import { useLikes } from '@/store/LikesContext'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { SharedCover } from '@/components/ui/SharedCover'
import { BeatPulse } from '@/components/ui/BeatPulse'
import { FullscreenLyrics } from '@/components/FullscreenLyrics/FullscreenLyrics'
import { QueuePanelContent } from '@/components/QueueSheet/QueueSheet'
import { PlaybackModeIndicator } from '@/components/PlayerBar/PlaybackModeIndicator'
import { haptic } from '@/lib/telegram'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { useDesktopFinePointer } from '@/hooks/useDesktopFinePointer'
import { useNavigateToArtistByName } from '@/hooks/useNavigateToArtistByName'
import { useSwipeX } from '@/hooks/useSwipeX'
import {
  coverProxySizes,
  coverProxySrcSet,
  coverProxyUrl,
} from '@/lib/coverProxy'

const SWIPE_DOWN_THRESHOLD = 120
const SWIPE_COVER_THRESHOLD = 72

const COVER_VARIANTS = {
  enter: (dir: 'left' | 'right' | null) => ({
    x: dir === 'left' ? '42%' : dir === 'right' ? '-42%' : 0,
    opacity: 0,
    scale: dir ? 0.88 : 0.94,
  }),
  center: { x: 0, opacity: 1, scale: 1 },
  exit: (dir: 'left' | 'right' | null) => ({
    x: dir === 'left' ? '-42%' : dir === 'right' ? '42%' : 0,
    opacity: 0,
    scale: dir ? 0.88 : 0.94,
  }),
}

const COVER_TRANSITION = {
  duration: 0.22,
  ease: [0.32, 0, 0.18, 1] as [number, number, number, number],
}

type Tab = 'now' | 'lyrics' | 'queue'

function fmt(sec: number) {
  if (!sec || isNaN(sec)) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
    .toString()
    .padStart(2, '0')
  return `${m}:${s}`
}

export function NowPlayingView() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const reduce = useReducedMotion()
  const { track, shuffleOn, repeatMode, queue } = usePlayerMeta()
  const {
    currentTime,
    duration,
    isPlaying,
  } = usePlayerState()
  const {
    togglePlay,
    seek,
    playNext,
    playPrev,
    openLyrics,
    openQueue,
    openCard,
    toggleShuffle,
    toggleRepeat,
    getPreciseTime,
  } = usePlayerActions()
  const desktopFineNav = useDesktopFinePointer()
  const goArtistByName = useNavigateToArtistByName()
  const { isLiked, toggleLike } = useLikes()

  usePrefetchTracks(
    queue.length > 0 ? queue : null,
    'queue',
  )

  const [tab, setTab] = useState<Tab>(
    () => track?.has_lyrics ? 'lyrics' : 'now',
  )
  const [likeBurst, setLikeBurst] = useState(false)
  const [swipeDx, setSwipeDx] = useState(0)
  const swipeDirRef = useRef<'left' | 'right' | null>(null)

  useEffect(() => {
    if (!track) {
      const tid = window.setTimeout(
        () => navigate('/'),
        80,
      )
      return () => window.clearTimeout(tid)
    }
  }, [track, navigate])

  if (!track) {
    return (
      <div className="rp-now rp-now--empty">
        <div className="rp-now__shell">
          <p style={{ padding: 24, textAlign: 'center' }}>
            {t(
              'redesign.player.emptyPlayback',
            )}
          </p>
        </div>
      </div>
    )
  }

  const liked = isLiked(track.id)
  const coverSrc = track.cover_key
    ? coverProxyUrl(track.cover_key, { width: 480 })
    : null
  const coverSrcSet = track.cover_key
    ? coverProxySrcSet(track.cover_key)
    : undefined

  const pct =
    Number.isFinite(duration) &&
    Number.isFinite(currentTime) &&
    duration > 0
      ? Math.max(0, Math.min(100, (currentTime / duration) * 100))
      : 0
  const trackBpm = (track as unknown as { bpm?: number }).bpm
  const tabBpm =
    typeof trackBpm === 'number' ? trackBpm : 120

  const handleClose = () => {
    haptic('light')
    navigate(-1)
  }

  const handleDragEnd = (
    _: unknown,
    info: PanInfo,
  ) => {
    if (info.offset.y > SWIPE_DOWN_THRESHOLD) {
      handleClose()
    }
  }

  const coverSwipe = useSwipeX({
    disabled: desktopFineNav,
    threshold: SWIPE_COVER_THRESHOLD,
    onProgress: setSwipeDx,
    onSwipeLeft: () => {
      haptic('light')
      swipeDirRef.current = 'left'
      playNext()
    },
    onSwipeRight: () => {
      haptic('light')
      swipeDirRef.current = 'right'
      playPrev()
    },
  })

  const handleLike = async () => {
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

  const internalUid = getInternalUserId()
  const isUploader =
    internalUid !== null &&
    track.uploaded_by_id === internalUid &&
    track.catalog_type === 'ugc'
  const canLyricsChrome =
    Boolean(track.has_lyrics) ||
    isUploader ||
    getIsAdmin() ||
    import.meta.env.DEV

  const handleShare = async () => {
    const url = `${window.location.origin}/mini_app/track/${track.id}`
    try {
      if (navigator.share) {
        await navigator.share({
          title: track.title,
          url,
        })
      } else {
        await navigator.clipboard.writeText(url)
      }
    } catch {
      /* ignore */
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    {
      id: 'now',
      label: t('redesign.player.tabNow'),
    },
    ...(canLyricsChrome
      ? ([
          {
            id: 'lyrics',
            label: t('redesign.player.tabLyrics'),
          },
        ] as const)
      : []),
    {
      id: 'queue',
      label: t('redesign.player.tabQueue'),
    },
  ]

  const handleTab = (next: Tab) => {
    haptic('light')
    setTab(next)
  }

  const tabSwipe = useSwipeX({
    disabled: desktopFineNav,
    threshold: 52,
    onSwipeLeft: () => {
      const idx = tabs.findIndex((t) => t.id === tab)
      if (idx < tabs.length - 1) {
        haptic('light')
        handleTab(tabs[idx + 1].id)
      }
    },
    onSwipeRight: () => {
      const idx = tabs.findIndex((t) => t.id === tab)
      if (idx > 0) {
        haptic('light')
        handleTab(tabs[idx - 1].id)
      }
    },
  })

  useEffect(() => {
    if (tab === 'lyrics' && !canLyricsChrome) {
      setTab('now')
    }
  }, [tab, canLyricsChrome])

  useEffect(() => {
    if (!track) return
    setTab(track.has_lyrics ? 'lyrics' : 'now')
  }, [track?.id])

  return (
    <m.section
      className="rp-now"
      drag={reduce ? false : 'y'}
      dragConstraints={{ top: 0, bottom: 0 }}
      dragElastic={0.18}
      dragMomentum={false}
      onDragEnd={handleDragEnd}
      initial={
        reduce ? { opacity: 0 } : { opacity: 0, y: 30 }
      }
      animate={{ opacity: 1, y: 0 }}
      exit={
        reduce ? { opacity: 0 } : { opacity: 0, y: 40 }
      }
      transition={SPRING_GENTLE}
    >
      <div className="rp-now__bg" aria-hidden="true">
        <AmbientStage coverUrl={coverSrc}>
          {coverSrc && (
            <KenBurnsCover
              src={coverSrc}
              srcSet={coverSrcSet}
              alt=""
              duration={22}
              className="rp-now__bg-kb"
            />
          )}
        </AmbientStage>
        <div className="rp-now__scrim" />
      </div>

      <div className="rp-now__shell">
        <div className="rp-now__topbar">
          <MotionPress
            variant="icon"
            ariaLabel={t(
              'redesign.player.close',
            )}
            haptic="light"
            onClick={handleClose}
          >
            <Icon name="chevron-down" size={20} />
          </MotionPress>
          <span className="rp-now__title">
            {t(
              'redesign.player.screenTitle',
            )}
          </span>
          {canLyricsChrome ? (
            <MotionPress
              variant="icon"
              ariaLabel={t(
                'redesign.player.menu',
              )}
              haptic="light"
              onClick={() => {
                haptic('light')
                openLyrics()
              }}
            >
              <Icon name="dots" size={18} />
            </MotionPress>
          ) : (
            <span className="rp-now__topbar-spacer" aria-hidden />
          )}
        </div>

        <div className="rp-now__handle" aria-hidden="true" />

        <div className="rp-now__split">
          <div
            className="rp-now__hero"
            {...(desktopFineNav ? {} : coverSwipe)}
            style={
              desktopFineNav
                ? undefined
                : {
                    touchAction: 'pan-y',
                    userSelect: 'none',
                  }
            }
          >
            {!desktopFineNav && Math.abs(swipeDx) > 16 && (
              <div
                className="rp-now__swipe-hint"
                aria-hidden="true"
                style={{
                  opacity: Math.min(
                    Math.abs(swipeDx) / SWIPE_COVER_THRESHOLD,
                    0.88,
                  ),
                }}
              >
                <Icon
                  name={swipeDx < 0 ? 'skip-forward' : 'skip-back'}
                  size={30}
                />
              </div>
            )}
            {reduce ? (
              <div className="rp-now__cover">
                {coverSrc ? (
                  <SharedCover
                    trackId={track.id}
                    src={coverSrc}
                    srcSet={coverSrcSet}
                    sizes={coverProxySizes(360)}
                    alt={track.title}
                  />
                ) : (
                  <div className="rp-now__cover-fallback">
                    <Icon name="music" size={48} />
                  </div>
                )}
              </div>
            ) : (
              <AnimatePresence
                mode="wait"
                initial={false}
                custom={swipeDirRef.current}
              >
                <m.div
                  key={track.id}
                  className="rp-now__cover"
                  custom={swipeDirRef.current}
                  variants={COVER_VARIANTS}
                  initial="enter"
                  animate="center"
                  exit="exit"
                  transition={COVER_TRANSITION}
                  onAnimationComplete={() => {
                    swipeDirRef.current = null
                  }}
                >
                  {coverSrc ? (
                    <SharedCover
                      trackId={track.id}
                      src={coverSrc}
                      srcSet={coverSrcSet}
                      sizes={coverProxySizes(360)}
                      alt={track.title}
                    />
                  ) : (
                    <div className="rp-now__cover-fallback">
                      <Icon name="music" size={48} />
                    </div>
                  )}
                </m.div>
              </AnimatePresence>
            )}
          </div>

          <div className="rp-now__split-right">
        <div className="rp-now__meta">
          <h1
            className={
              desktopFineNav
                ? 'rp-now__meta-title rp-now__meta-title--nav'
                : 'rp-now__meta-title'
            }
            dir="auto"
            role={
              desktopFineNav ? 'button' : undefined
            }
            tabIndex={desktopFineNav ? 0 : undefined}
            onClick={
              desktopFineNav
                ? () => {
                    haptic('light')
                    openCard()
                  }
                : undefined
            }
            onKeyDown={
              desktopFineNav
                ? (e) => {
                    if (
                      e.key === 'Enter' ||
                      e.key === ' '
                    ) {
                      e.preventDefault()
                      haptic('light')
                      openCard()
                    }
                  }
                : undefined
            }
          >
            {track.title}
          </h1>
          <p
            className={
              desktopFineNav && track.artist
                ? 'rp-now__meta-artist rp-now__meta-artist--nav'
                : 'rp-now__meta-artist'
            }
            dir="auto"
            role={
              desktopFineNav && track.artist
                ? 'link'
                : undefined
            }
            tabIndex={
              desktopFineNav && track.artist
                ? 0
                : undefined
            }
            onClick={
              desktopFineNav && track.artist
                ? () => {
                    haptic('light')
                    void goArtistByName(track.artist)
                  }
                : undefined
            }
            onKeyDown={
              desktopFineNav && track.artist
                ? (e) => {
                    if (
                      e.key === 'Enter' ||
                      e.key === ' '
                    ) {
                      e.preventDefault()
                      haptic('light')
                      void goArtistByName(track.artist)
                    }
                  }
                : undefined
            }
          >
            {track.track_artists?.[0]?.image_url && (
              <img
                className="rp-now__artist-avatar"
                src={track.track_artists[0].image_url}
                alt=""
                aria-hidden="true"
              />
            )}
            {track.artist ?? '—'}
          </p>
          <PlaybackModeIndicator
            shuffleOn={shuffleOn}
            variant="now-playing"
          />
        </div>

        <div className="rp-now__seek">
          <div className="rp-now__seek-bar">
            <div
              className="rp-now__seek-fill"
              style={{ width: `${pct}%` }}
            />
            <input
              className="rp-now__seek-input"
              type="range"
              min={0}
              max={100}
              step={0.1}
              value={pct}
              aria-label={t(
                'redesign.player.seekAria',
              )}
              onChange={(e) =>
                seek(Number(e.currentTarget.value))
              }
            />
          </div>
          <div className="rp-now__seek-times">
            <span>{fmt(currentTime)}</span>
            <span>{fmt(duration)}</span>
          </div>
        </div>

        <div className="rp-now__controls">
          <MotionPress
            variant="icon"
            ariaLabel={t('redesign.player.shuffleAria')}
            haptic="selection"
            aria-pressed={shuffleOn}
            className={shuffleOn ? 'rp-now__ctl-active' : ''}
            onClick={toggleShuffle}
          >
            <Icon name="shuffle" size={20} />
          </MotionPress>
          <MotionPress
            variant="icon"
            ariaLabel={t(
              'redesign.player.prevAria',
            )}
            haptic="light"
            onClick={() => playPrev()}
          >
            <Icon name="skip-back" size={28} />
          </MotionPress>
          <div className="rp-now__ctl-center">
            <MotionPress
              variant="icon"
              ariaLabel={t(
                'redesign.player.seekBack10Aria',
              )}
              haptic="light"
              className="rp-now__ctl-seek10"
              onClick={() => {
                const t0 = getPreciseTime()
                seek(
                  Math.max(
                    0,
                    duration > 0
                      ? ((t0 - 10) / duration) * 100
                      : 0,
                  ),
                )
              }}
            >
              <Icon name="rewind-10" size={26} />
            </MotionPress>
            <MotionPress
              variant="icon"
              className="rp-now__ctl-play"
              ariaLabel={
                isPlaying
                  ? t('redesign.player.pauseAria')
                  : t('redesign.player.playAria')
              }
              haptic="medium"
              onClick={() => togglePlay()}
            >
              <BeatPulse
                bpm={tabBpm}
                active={isPlaying}
              >
                <MorphIcon
                  name="play"
                  filled={isPlaying}
                  size={28}
                />
              </BeatPulse>
            </MotionPress>
            <MotionPress
              variant="icon"
              ariaLabel={t(
                'redesign.player.seekForward10Aria',
              )}
              haptic="light"
              className="rp-now__ctl-seek10"
              onClick={() => {
                const t0 = getPreciseTime()
                seek(
                  Math.min(
                    100,
                    duration > 0
                      ? ((t0 + 10) / duration) * 100
                      : 0,
                  ),
                )
              }}
            >
              <Icon name="forward-10" size={26} />
            </MotionPress>
          </div>
          <MotionPress
            variant="icon"
            ariaLabel={t(
              'redesign.player.nextAria',
            )}
            haptic="light"
            onClick={() => playNext()}
          >
            <Icon name="skip-forward" size={28} />
          </MotionPress>
          <MotionPress
            variant="icon"
            ariaLabel={t('redesign.player.repeatAria')}
            haptic="selection"
            aria-pressed={repeatMode !== 'none'}
            className={repeatMode !== 'none' ? 'rp-now__ctl-active' : ''}
            onClick={toggleRepeat}
          >
            <Icon
              name={repeatMode === 'one' ? 'repeat-one' : 'repeat'}
              size={20}
            />
          </MotionPress>
        </div>

        <div className="rp-now__secondary">
          <m.div
            animate={
              likeBurst && !reduce
                ? { scale: [1, 1.25, 1] }
                : { scale: 1 }
            }
            transition={
              reduce ? TWEEN_FAST : SPRING_GENTLE
            }
          >
            <MotionPress
              variant="icon"
              ariaLabel={
                liked
                  ? t(
                      'redesign.player.unlikeAria',
                    )
                  : t(
                      'redesign.player.likeAria',
                    )
              }
              aria-pressed={liked}
              onClick={handleLike}
              haptic={liked ? 'light' : 'medium'}
            >
              <MorphIcon
                name="heart"
                filled={liked}
                size={22}
              />
            </MotionPress>
          </m.div>
          <MotionPress
            variant="icon"
            ariaLabel={t(
              'redesign.player.shareAria',
            )}
            onClick={handleShare}
          >
            <Icon name="share-arrow" size={20} />
          </MotionPress>
          <MotionPress
            variant="icon"
            ariaLabel={t(
              'redesign.player.openQueueAria',
            )}
            onClick={() => {
              haptic('light')
              openQueue()
            }}
          >
            <Icon name="queue" size={20} />
          </MotionPress>
        </div>
          </div>
        </div>

        <div
          className="rp-now__tabs"
          role="tablist"
        >
          <m.span
            layoutId={
              reduce ? undefined : 'rp-now-tab-pill'
            }
            className="rp-now__tab-pill"
            style={{
              left: `calc(4px + ${
                tabs.findIndex((tabItem) => tabItem.id === tab) *
                  (100 / tabs.length)
              }% )`,
            }}
            transition={SPRING_GENTLE}
          />
          {tabs.map((it) => (
            <MotionPress
              key={it.id}
              role="tab"
              variant="ghost"
              haptic="selection"
              aria-selected={tab === it.id}
              className={[
                'rp-now__tab',
                tab === it.id
                  ? 'rp-now__tab--active'
                  : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => handleTab(it.id)}
            >
              {it.label}
            </MotionPress>
          ))}
        </div>

        <div
          className="rp-now__panel"
          role="tabpanel"
          {...(!desktopFineNav ? tabSwipe : {})}
          style={
            !desktopFineNav
              ? { touchAction: 'pan-x pan-y' }
              : undefined
          }
        >
          {tab === 'now' && (
            <NowPanel
              description={track.description}
              aboutLabel={t(
                'redesign.player.aboutTrack',
              )}
            />
          )}
          {tab === 'lyrics' && <FullscreenLyrics embed />}
          {tab === 'queue' && <QueuePanelContent inline />}
        </div>
      </div>
    </m.section>
  )
}

function NowPanel({
  description,
  aboutLabel,
}: {
  description?: string | null
  aboutLabel: string
}): ReactNode {
  if (!description) {
    return null
  }
  return (
    <div className="rp-now__about">
      <h2
        style={{
          fontSize: 'var(--fs-15)',
          fontWeight: 600,
          letterSpacing: 'var(--ls-snug)',
          color: 'var(--text-secondary)',
          margin: '0 0 8px',
        }}
      >
        {aboutLabel}
      </h2>
      <p
        style={{
          color: 'var(--text)',
          fontSize: 'var(--fs-14)',
          lineHeight: 'var(--lh-normal)',
          whiteSpace: 'pre-line',
        }}
      >
        {description}
      </p>
    </div>
  )
}
