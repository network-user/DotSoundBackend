import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'

import '@/styles/redesign-artist.css'

import { api, getApiErrorMessage } from '@/lib/api'
import { coverProxyUrl } from '@/lib/coverProxy'
import { VARIANTS_FADE_UP, m } from '@/lib/motion'
import { setBackButton } from '@/lib/telegram'

import {
  usePlayerActions,
} from '@/store/PlayerContext'

import type { Track } from '@/types/api'

function trackCoverUrl(
  key: string | null | undefined,
): string | null {
  if (!key) return null
  return coverProxyUrl(key, { width: 480 })
}

function openExternalLink(url: string) {
  try {
    const tg = (
      window as unknown as {
        Telegram?: {
          WebApp?: {
            openLink?: (u: string) => void
          }
        }
      }
    ).Telegram?.WebApp
    if (tg?.openLink) {
      tg.openLink(url)
      return
    }
  } catch {
    /* ignore */
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

export function ExternalTrackView() {
  const { id: idParam } = useParams<{ id: string }>()
  const trackId = Number(idParam)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { playTrack } = usePlayerActions()

  const [track, setTrack] = useState<Track | null>(null)
  const [error, setError] = useState<string | null>(null)

  const goBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate('/')
    }
  }, [navigate])

  useEffect(() => {
    setBackButton(true, goBack)
    return () => {
      setBackButton(false)
    }
  }, [goBack])

  useEffect(() => {
    if (!Number.isFinite(trackId)) return
    let cancelled = false
    setTrack(null)
    setError(null)
    api
      .getTrack(trackId)
      .then((d) => {
        if (cancelled) return
        setTrack(d)
      })
      .catch((e) => {
        if (cancelled) return
        setError(
          getApiErrorMessage(e, t('redesign.artist.loadError')),
        )
      })
    return () => {
      cancelled = true
    }
  }, [trackId, t])

  const heroUrl = useMemo(
    () => trackCoverUrl(track?.cover_key),
    [track?.cover_key],
  )

  const badgeKey = useMemo(() => {
    if (!track) return null
    if (track.catalog_type === 'licensed') {
      return 'redesign.artist.badgeLicensed'
    }
    if (track.catalog_type === 'external_reference') {
      return 'redesign.artist.badgeExternal'
    }
    return null
  }, [track])

  const sourceName = track?.source_name ?? null
  const sourceUrl =
    track?.source_url ?? track?.canonical_source_url ?? null

  const handlePlay = useCallback(async () => {
    if (!track) return
    try {
      await playTrack(track)
    } catch (e) {
      showIsland({ kind: 'error', title: getApiErrorMessage(e, t('redesign.artist.playError')), durationMs: 4000 })
    }
  }, [track, playTrack, t])

  const handleOpenSource = useCallback(() => {
    if (!sourceUrl) return
    openExternalLink(sourceUrl)
  }, [sourceUrl])

  if (!Number.isFinite(trackId)) {
    return (
      <section className="view active rf-external">
        <div className="rf-artist__error">
          {t('redesign.artist.invalidId')}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="view active rf-external">
        <header className="rf-external__chrome">
          <MotionPress
            variant="icon"
            haptic="light"
            ariaLabel={t('redesign.artist.backAria')}
            onClick={goBack}
          >
            <Icon name="chevron" size={20} className="back-chevron" />
          </MotionPress>
        </header>
        <div className="rf-artist__error">{error}</div>
      </section>
    )
  }

  return (
    <section className="view active rf-external">
      <header className="rf-external__chrome">
        <MotionPress
          variant="icon"
          haptic="light"
          ariaLabel={t('redesign.artist.backAria')}
          onClick={goBack}
        >
          <Icon name="chevron" size={20} className="back-chevron" />
        </MotionPress>
        <span
          className="rf-artist__chrome-title"
          aria-hidden="true"
        >
          {track?.title ?? ''}
        </span>
      </header>

      <AmbientStage
        coverUrl={heroUrl}
        className="rf-external__hero"
      >
        <div className="rf-external__hero-inner">
          <div className="rf-external__hero-art">
            {heroUrl ? (
              <KenBurnsCover src={heroUrl} alt="" />
            ) : (
              <Icon name="music" size={48} />
            )}
          </div>
          {badgeKey && (
            <span className="rf-external__badge">
              <Icon name="link-external" size={12} />
              {t(badgeKey)}
            </span>
          )}
          <h1 className="rf-external__title">
            {track?.title ?? ' '}
          </h1>
          {track?.artist && (
            <p className="rf-external__artist">
              {track.artist}
            </p>
          )}
          <div className="rf-external__actions">
            <MotionPress
              variant="primary"
              haptic="medium"
              onClick={() => {
                void handlePlay()
              }}
              disabled={!track}
            >
              <Icon name="play" size={16} />
              <span>{t('redesign.artist.play')}</span>
            </MotionPress>
            {sourceName && sourceUrl && (
              <MotionPress
                variant="ghost"
                haptic="light"
                onClick={handleOpenSource}
                className="rf-external__source-btn"
              >
                <Icon name="link-external" size={14} />
                <span>{sourceName}</span>
              </MotionPress>
            )}
          </div>
        </div>
      </AmbientStage>

      {track?.description && (
        <m.div
          initial="hidden"
          animate="visible"
          variants={VARIANTS_FADE_UP}
          className="rf-artist__sections"
        >
          <section className="rf-artist__section">
            <h2 className="rf-artist__section-title">
              {t('redesign.artist.about')}
            </h2>
            <p className="rf-artist__bio">
              {track.description}
            </p>
          </section>
        </m.div>
      )}
    </section>
  )
}
