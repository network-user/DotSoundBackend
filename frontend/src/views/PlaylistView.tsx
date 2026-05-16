import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { BulkDownloadButton } from '@/components/Offline/BulkDownloadButton'
import { TrackList } from '@/components/TrackList/TrackList'
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
  usePlayerMeta,
} from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'

import type { PlaylistWithTracks, Track } from '@/types/api'

function trackCoverUrl(
  key: string | null | undefined,
  width: 120 | 240 | 480 = 240,
): string | null {
  if (!key) return null
  return coverProxyUrl(key, { width })
}

function pickCollageCovers(tracks: Track[]): (string | null)[] {
  const seen = new Set<string>()
  const result: (string | null)[] = []
  for (const t of tracks) {
    const url = trackCoverUrl(t.cover_key)
    if (!url) continue
    if (seen.has(url)) continue
    seen.add(url)
    result.push(url)
    if (result.length === 4) break
  }
  while (result.length < 4) result.push(null)
  return result
}

export function PlaylistView() {
  const { id: idParam } = useParams<{ id: string }>()
  const playlistId = Number(idParam)
  const navigate = useNavigate()
  const { t } = useTranslation()

  const { playTrack, toggleShuffle } = usePlayerActions()
  const { shuffleOn } = usePlayerMeta()

  const [playlist, setPlaylist] =
    useState<PlaylistWithTracks | null>(null)
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
    if (!Number.isFinite(playlistId)) return
    let cancelled = false
    setPlaylist(null)
    setError(null)
    api
      .getPlaylist(playlistId)
      .then((d) => {
        if (cancelled) return
        setPlaylist(d)
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
  }, [playlistId, t])

  const tracks = playlist?.tracks ?? null
  usePrefetchTracks(tracks, 'playlist')

  const collageCovers = useMemo(
    () => pickCollageCovers(playlist?.tracks ?? []),
    [playlist?.tracks],
  )
  const heroUrl = collageCovers.find((u) => u) ?? null
  const allSame =
    heroUrl != null &&
    collageCovers.every(
      (c) => c === null || c === heroUrl,
    )

  const handlePlayAll = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      await playTrack(tracks[0], { contextTracks: tracks })
    } catch (e) {
      showIsland({ kind: 'error', title: getApiErrorMessage(e, t('redesign.artist.playError')), durationMs: 4000 })
    }
  }, [tracks, playTrack, t])

  const handleShuffle = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      if (!shuffleOn) toggleShuffle()
      const shuffled = [...tracks].sort(() => Math.random() - 0.5)
      await playTrack(shuffled[0], { contextTracks: shuffled })
    } catch (e) {
      showIsland({ kind: 'error', title: getApiErrorMessage(e, t('redesign.artist.playError')), durationMs: 4000 })
    }
  }, [tracks, shuffleOn, toggleShuffle, playTrack, t])

  if (!Number.isFinite(playlistId)) {
    return (
      <section className="view active rf-playlist">
        <div className="rf-artist__error">
          {t('redesign.artist.invalidId')}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="view active rf-playlist">
        <header className="rf-playlist__chrome">
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
    <section className="view active rf-playlist">
      <header className="rf-playlist__chrome">
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
          {playlist?.name ?? ''}
        </span>
      </header>

      <AmbientStage
        coverUrl={heroUrl}
        className="rf-playlist__hero"
      >
        <div className="rf-playlist__hero-inner">
          <div
            className={
              'rf-playlist__collage' +
              (allSame ? ' rf-playlist__collage--single' : '')
            }
          >
            {allSame && heroUrl ? (
              <KenBurnsCover src={heroUrl} alt="" />
            ) : (
              collageCovers.map((url, i) => (
                <div
                  key={i}
                  className="rf-playlist__collage-cell"
                >
                  {url ? (
                    <img
                      src={url}
                      alt=""
                      loading="lazy"
                      decoding="async"
                    />
                  ) : (
                    <Icon name="music" size={20} />
                  )}
                </div>
              ))
            )}
          </div>
          <h1 className="rf-playlist__title">
            {playlist?.name ?? ' '}
          </h1>
          {playlist && (
            <p className="rf-playlist__sub">
              {t('redesign.artist.tracksCount', {
                count: tracks?.length ?? 0,
              })}
            </p>
          )}
          <div className="rf-playlist__actions">
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
            <BulkDownloadButton tracks={tracks} />
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
