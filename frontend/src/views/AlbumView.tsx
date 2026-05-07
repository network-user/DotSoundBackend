import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import { useToast } from '@/components/ui/Toast'

import { api, getApiErrorMessage } from '@/lib/api'
import { VARIANTS_FADE_UP, m } from '@/lib/motion'
import { setBackButton } from '@/lib/telegram'

import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'

import type { AlbumWithTracksRecord } from '@/types/api'

function albumCoverUrl(
  key: string | null | undefined,
): string | null {
  if (!key) return null
  return (
    '/api/v1/tracks/cover_proxy?key=' +
    encodeURIComponent(key)
  )
}

export function AlbumView() {
  const { id: idParam } = useParams<{ id: string }>()
  const albumId = Number(idParam)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const toast = useToast()

  const { playTrack, toggleShuffle } = usePlayerActions()
  const { shuffleOn } = usePlayerMeta()

  const [album, setAlbum] =
    useState<AlbumWithTracksRecord | null>(null)
  const [error, setError] = useState<string | null>(null)

  const goBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      navigate('/library')
    }
  }, [navigate])

  useEffect(() => {
    setBackButton(true, goBack)
    return () => {
      setBackButton(false)
    }
  }, [goBack])

  useEffect(() => {
    if (!Number.isFinite(albumId)) return
    let cancelled = false
    setAlbum(null)
    setError(null)
    api
      .getAlbum(albumId)
      .then((d) => {
        if (cancelled) return
        setAlbum(d)
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
  }, [albumId, t])

  const tracks = album?.tracks ?? null
  usePrefetchTracks(tracks, 'album')

  const heroUrl = useMemo(
    () => albumCoverUrl(album?.cover_key),
    [album?.cover_key],
  )

  const handlePlayAll = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      await playTrack(tracks[0])
    } catch (e) {
      toast.error(getApiErrorMessage(e, t('redesign.artist.playError')))
    }
  }, [tracks, playTrack, toast, t])

  const handleShuffle = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      if (!shuffleOn) toggleShuffle()
      const pick =
        tracks[Math.floor(Math.random() * tracks.length)]
      await playTrack(pick)
    } catch (e) {
      toast.error(getApiErrorMessage(e, t('redesign.artist.playError')))
    }
  }, [tracks, shuffleOn, toggleShuffle, playTrack, toast, t])

  if (!Number.isFinite(albumId)) {
    return (
      <section className="view active rf-album">
        <div className="rf-artist__error">
          {t('redesign.artist.invalidId')}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="view active rf-album">
        <header className="rf-album__chrome">
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
    <section className="view active rf-album">
      <header className="rf-album__chrome">
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
          {album?.title ?? ''}
        </span>
      </header>

      <AmbientStage
        coverUrl={heroUrl}
        className="rf-album__hero"
      >
        <div className="rf-album__hero-inner">
          <div className="rf-album__hero-art">
            {heroUrl ? (
              <KenBurnsCover src={heroUrl} alt="" />
            ) : (
              <Icon name="music" size={48} />
            )}
          </div>
          <h1 className="rf-album__title">
            {album?.title ?? ' '}
          </h1>
          {album?.description && (
            <p className="rf-album__sub">
              {album.description}
            </p>
          )}
          <div className="rf-album__actions">
            <MotionPress
              variant="primary"
              haptic="medium"
              onClick={() => {
                void handlePlayAll()
              }}
              disabled={!tracks || tracks.length === 0}
            >
              <Icon name="play" size={16} />
              <span>{t('redesign.artist.play')}</span>
            </MotionPress>
            <MotionPress
              variant="ghost"
              haptic="selection"
              onClick={() => {
                void handleShuffle()
              }}
              disabled={!tracks || tracks.length === 0}
            >
              <Icon name="shuffle" size={16} />
              <span>{t('redesign.artist.shuffle')}</span>
            </MotionPress>
          </div>
        </div>
      </AmbientStage>

      <m.div
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
      >
        <TrackList
          tracks={tracks}
          emptyMessage={t('redesign.artist.noTracks')}
        />
      </m.div>
    </section>
  )
}
