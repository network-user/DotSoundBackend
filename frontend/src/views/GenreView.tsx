import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'

import { api, getApiErrorMessage } from '@/lib/api'
import { VARIANTS_FADE_UP, m, SPRING_GENTLE } from '@/lib/motion'
import { setBackButton } from '@/lib/telegram'

import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { usePrefetchTracks } from '@/store/PrefetchContext'

import type { GenreMixItem } from '@/types/api'

type GenreTab = 'top' | 'new' | 'artists'

const TABS: { id: GenreTab; labelKey: string }[] = [
  { id: 'top', labelKey: 'redesign.artist.genreTabTop' },
  { id: 'new', labelKey: 'redesign.artist.genreTabNew' },
  { id: 'artists', labelKey: 'redesign.artist.genreTabArtists' },
]

export function GenreView() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()

  const { playTrack, toggleShuffle } = usePlayerActions()
  const { shuffleOn } = usePlayerMeta()

  const [tab, setTab] = useState<GenreTab>('top')
  const [mix, setMix] = useState<GenreMixItem | null>(null)
  const [loading, setLoading] = useState(true)
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
    if (!slug) return
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getGenreMix(slug)
      .then((d) => {
        if (cancelled) return
        setMix(d)
      })
      .catch((e) => {
        if (cancelled) return
        setError(
          getApiErrorMessage(e, t('redesign.artist.loadError')),
        )
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [slug, t])

  const tracks = loading ? null : (mix?.tracks ?? [])
  usePrefetchTracks(mix?.tracks ?? null, 'genre_mix')

  const handlePlayAll = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      await playTrack(tracks[0])
    } catch (e) {
      showIsland({ kind: 'error', title: getApiErrorMessage(e, t('redesign.artist.playError')), durationMs: 4000 })
    }
  }, [tracks, playTrack, t])

  const handleShuffle = useCallback(async () => {
    if (!tracks || tracks.length === 0) return
    try {
      if (!shuffleOn) toggleShuffle()
      const pick =
        tracks[Math.floor(Math.random() * tracks.length)]
      await playTrack(pick)
    } catch (e) {
      showIsland({ kind: 'error', title: getApiErrorMessage(e, t('redesign.artist.playError')), durationMs: 4000 })
    }
  }, [tracks, shuffleOn, toggleShuffle, playTrack, t])

  if (!slug) {
    return (
      <section className="view active rf-genre">
        <div className="rf-artist__error">
          {t('redesign.artist.invalidId')}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="view active rf-genre">
        <header className="rf-genre__chrome">
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
    <section className="view active rf-genre">
      <header className="rf-genre__chrome">
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
          {mix?.title ?? slug}
        </span>
      </header>

      <div className="rf-genre__hero">
        <div className="rf-genre__hero-inner">
          <h1 className="rf-genre__title">
            {mix?.title ?? slug}
          </h1>
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
      </div>

      <div
        className="rf-genre__tabs"
        role="tablist"
        aria-label={mix?.title ?? slug}
      >
        {TABS.map((tabDef) => {
          const active = tab === tabDef.id
          return (
            <button
              type="button"
              key={tabDef.id}
              role="tab"
              aria-selected={active}
              data-active={active ? 'true' : 'false'}
              className="rf-genre__tab"
              onClick={() => setTab(tabDef.id)}
            >
              {active && (
                <m.span
                  layoutId="genre-tab-indicator"
                  className="rf-genre__tab-indicator"
                  transition={SPRING_GENTLE}
                />
              )}
              {t(tabDef.labelKey)}
            </button>
          )
        })}
      </div>

      <m.div
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
        key={tab}
      >
        {tab === 'top' ? (
          <TrackList
            tracks={tracks}
            emptyMessage={t('redesign.artist.noTracks')}
          />
        ) : (
          <div className="rf-artist__error">
            {t('redesign.artist.genreTabSoon')}
          </div>
        )}
      </m.div>
    </section>
  )
}
