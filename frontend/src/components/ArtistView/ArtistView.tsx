import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ArtistAvatarViewer } from '@/components/ArtistView/ArtistAvatarViewer'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import type {
  ArtistDetail,
  ArtistSourceProfile,
  ArtistSupplementalResponse,
  DiscographyItem,
  Track,
} from '@/types/api'

interface Props {
  artistId: number
  onClose: () => void
}

interface ArtistViewData {
  source_id: string | null
  source_name: string | null
  source_page_url: string | null
  bio: string | null
  birth_date: string | null
  birthplace: string | null
  country: string | null
  image_url: string | null
  website_url: string | null
  discography: DiscographyItem[]
}

function hasAnyInfo(view: ArtistViewData): boolean {
  return Boolean(
    view.bio ||
      view.birth_date ||
      view.birthplace ||
      view.country ||
      view.website_url ||
      view.discography.length > 0,
  )
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value
    ? value
    : null
}

function buildMergedView(
  artist: ArtistDetail,
): ArtistViewData {
  return {
    source_id: artist.primary_source_id ?? null,
    source_name: null,
    source_page_url: null,
    bio: artist.bio,
    birth_date: artist.birth_date,
    birthplace: artist.birthplace,
    country: artist.country,
    image_url: artist.image_url,
    website_url: artist.website_url,
    discography: Array.isArray(artist.discography)
      ? (artist.discography as DiscographyItem[])
      : [],
  }
}

function buildProfileView(
  profile: ArtistSourceProfile,
  fallbackImage: string | null,
): ArtistViewData {
  return {
    source_id: profile.source_id,
    source_name: profile.source_name,
    source_page_url: profile.source_page_url ?? null,
    bio: asString(profile.bio),
    birth_date: asString(profile.birth_date),
    birthplace: asString(profile.birthplace),
    country: asString(profile.country),
    image_url:
      asString(profile.image_url) || fallbackImage,
    website_url: asString(profile.website_url),
    discography: Array.isArray(profile.discography)
      ? profile.discography
      : [],
  }
}

function computeAge(iso: string | null): number | null {
  if (!iso) return null
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return null
  const year = Number(m[1])
  const month = Number(m[2])
  const day = Number(m[3])
  const now = new Date()
  let age = now.getUTCFullYear() - year
  const beforeBirthday =
    now.getUTCMonth() + 1 < month ||
    (now.getUTCMonth() + 1 === month &&
      now.getUTCDate() < day)
  if (beforeBirthday) age -= 1
  return age >= 0 ? age : null
}

function cleanWikiText(s: string | null): string | null {
  if (!s) return null
  const cleaned = s
    .replace(/\{\{[^}]*\}\}/g, '')
    .replace(/\[\[(?:[^\]|]+)\|([^\]]+)\]\]/g, '$1')
    .replace(/\[\[([^\]]+)\]\]/g, '$1')
    .replace(/[{}\[\]|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned || null
}

const stageProgress: Record<string, number> = {
  queued: 5,
  searching: 20,
  processing: 50,
  saving: 85,
  done: 100,
  not_found: 100,
  error: 100,
}

export function ArtistView({
  artistId,
  onClose,
}: Props) {
  const { t } = useTranslation()
  const [artist, setArtist] =
    useState<ArtistDetail | null>(null)
  const [tracks, setTracks] = useState<
    Track[] | null
  >(null)
  const [bioOpen, setBioOpen] = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [enrichError, setEnrichError] = useState<
    string | null
  >(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugStage, setDebugStage] =
    useState<string | null>(null)
  const [debugLogs, setDebugLogs] = useState<
    string[]
  >([])
  const [debugRunning, setDebugRunning] =
    useState(false)
  const [debugTaskId, setDebugTaskId] =
    useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [selectedSourceId, setSelectedSourceId] =
    useState<string | null>(null)
  const [avatarOpen, setAvatarOpen] = useState(false)
  const [supplemental, setSupplemental] =
    useState<ArtistSupplementalResponse | null>(null)
  const [refreshingSupplemental, setRefreshingSupplemental] =
    useState(false)
  const supplementalPollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const isAdmin = getIsAdmin()

  useEffect(() => {
    if (!debugRunning) return
    setElapsed(0)
    const iv = setInterval(
      () => setElapsed((e) => e + 1),
      1000,
    )
    return () => clearInterval(iv)
  }, [debugRunning])

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({
        behavior: 'smooth',
      })
    }
  }, [debugLogs])

  useEffect(() => {
    let cancelled = false
    setArtist(null)
    setTracks(null)
    setBioOpen(false)
    setSelectedSourceId(null)
    setAvatarOpen(false)
    setSupplemental(null)

    api
      .getArtist(artistId)
      .then((data) => {
        if (!cancelled) setArtist(data)
      })
      .catch(() => {
        if (!cancelled) setArtist(null)
      })
    api
      .getArtistTracks(artistId)
      .then((res) => {
        if (!cancelled) setTracks(res.items)
      })
      .catch(() => {
        if (!cancelled) setTracks([])
      })
    api
      .getArtistSupplemental(artistId)
      .then((data) => {
        if (!cancelled) {
          setSupplemental(data)
          if (data.status === 'fetching' || data.status === 'pending') {
            startSupplementalPoll(artistId, 0, () => cancelled)
          }
        }
      })
      .catch(() => { /* supplemental is optional */ })

    return () => {
      cancelled = true
      if (supplementalPollRef.current) clearTimeout(supplementalPollRef.current)
    }
  }, [artistId])

  function startSupplementalPoll(
    id: number,
    attempts: number,
    isCancelled: () => boolean,
  ) {
    if (attempts >= 20) return
    supplementalPollRef.current = setTimeout(async () => {
      if (isCancelled()) return
      try {
        const data = await api.getArtistSupplemental(id)
        if (!isCancelled()) {
          setSupplemental(data)
          if (data.status === 'fetching' || data.status === 'pending') {
            startSupplementalPoll(id, attempts + 1, isCancelled)
          }
        }
      } catch { }
    }, 3000)
  }

  const handleRefreshSupplemental = async () => {
    setRefreshingSupplemental(true)
    if (supplementalPollRef.current) clearTimeout(supplementalPollRef.current)
    let cancelled = false
    try {
      const data = await api.refreshArtistSupplemental(artistId)
      setSupplemental(data)
      if (data.status === 'fetching' || data.status === 'pending') {
        startSupplementalPoll(artistId, 0, () => cancelled)
      }
    } catch { /* ignore */ } finally {
      setRefreshingSupplemental(false)
    }
  }

  const handleEnrich = async () => {
    setEnriching(true)
    setEnrichError(null)
    try {
      const updated =
        await api.enrichArtist(artistId)
      setArtist(updated)
    } catch {
      setEnrichError(t('artist.enrich_failed'))
    } finally {
      setEnriching(false)
    }
  }

  const handleEnrichWatch = async () => {
    setDebugRunning(true)
    setDebugStage('queued')
    setDebugLogs([])
    setDebugTaskId(null)
    setDebugOpen(true)
    setEnrichError(null)
    let taskId = ''
    try {
      const res = await api.enrichArtistWatch(artistId)
      taskId = res.task_id
      setDebugTaskId(taskId)
    } catch {
      setDebugRunning(false)
      setDebugStage('error')
      setEnrichError(t('artist.enrich_failed'))
      return
    }
    const terminal = new Set([
      'done',
      'not_found',
      'error',
    ])
    while (true) {
      await new Promise((r) => setTimeout(r, 1000))
      let status
      try {
        status = await api.getArtistEnrichStatus(
          artistId,
          taskId,
        )
      } catch {
        continue
      }
      setDebugStage(status.stage ?? null)
      setDebugLogs(status.logs ?? [])
      if (
        status.stage &&
        terminal.has(status.stage)
      ) {
        break
      }
      if (status.status !== 'pending') break
    }
    try {
      const updated = await api.getArtist(artistId)
      setArtist(updated)
    } catch {
      /* ignore refresh failures */
    }
    setDebugRunning(false)
  }

  const profiles = useMemo<ArtistSourceProfile[]>(
    () =>
      artist?.source_profiles?.filter(
        (p): p is ArtistSourceProfile =>
          Boolean(p && p.source_id && p.source_name),
      ) ?? [],
    [artist],
  )

  const view = useMemo<ArtistViewData | null>(() => {
    if (!artist) return null
    if (selectedSourceId === 'yandex') {
      return {
        source_id: 'yandex',
        source_name: t('artistSupplemental.tabLabel', { defaultValue: 'Яндекс' }),
        source_page_url: null,
        bio: supplemental?.content ?? null,
        birth_date: null,
        birthplace: null,
        country: null,
        image_url: artist.image_url,
        website_url: null,
        discography: [],
      }
    }
    if (selectedSourceId) {
      const found = profiles.find(
        (p) => p.source_id === selectedSourceId,
      )
      if (found) {
        return buildProfileView(found, artist.image_url)
      }
    }
    return buildMergedView(artist)
  }, [artist, profiles, selectedSourceId, supplemental])

  const primaryProfile = useMemo<
    ArtistSourceProfile | null
  >(() => {
    if (!profiles.length) return null
    if (artist?.primary_source_id) {
      const exact = profiles.find(
        (p) => p.source_id === artist.primary_source_id,
      )
      if (exact) return exact
    }
    return profiles[0]
  }, [artist?.primary_source_id, profiles])

  if (!artist || !view) {
    return (
      <div className="author-view">
        <div className="author-view-header">
          <button
            className="author-back-btn icon-btn"
            onClick={onClose}
          >
            <Icon name="chevron" size={18} />
            {t('common.back', {
              defaultValue: 'Назад',
            })}
          </button>
        </div>
        <div className="author-hero">
          <div className="profile-avatar skeleton" />
          <div
            className="skeleton"
            style={{
              width: 160,
              height: 20,
              borderRadius: 6,
              marginTop: 12,
            }}
          />
        </div>
      </div>
    )
  }

  const computedAge =
    selectedSourceId === null
      ? artist.age
      : view.birth_date
        ? computeAge(view.birth_date)
        : null

  const metaParts: string[] = []
  if (computedAge !== null && computedAge !== undefined) {
    metaParts.push(t('artist.age', { count: computedAge }))
  }
  const cleanBirthplace = cleanWikiText(view.birthplace)
  if (cleanBirthplace) {
    metaParts.push(cleanBirthplace)
  } else if (view.country) {
    metaParts.push(view.country)
  }
  if (metaParts.length === 0) {
    metaParts.push(t('artist.performer'))
  }
  const infoKnown = hasAnyInfo(view)
  const showPending =
    !infoKnown &&
    (artist.enrichment_status === 'pending' ||
      artist.enrichment_status === 'in_progress')
  const showNoInfo =
    !infoKnown &&
    !showPending &&
    (artist.enrichment_status === 'done' ||
      artist.enrichment_status === 'not_found' ||
      artist.enrichment_status === 'failed')

  const progressPct =
    stageProgress[debugStage ?? ''] ?? 5
  const avatarSrc = view.image_url || artist.image_url
  const sourceName =
    view.source_name ??
    primaryProfile?.source_name ??
    null
  const sourcePageUrl =
    view.source_page_url ??
    primaryProfile?.source_page_url ??
    null

  return (
    <div className="author-view">
      <div className="author-view-header">
        <button
          className="author-back-btn icon-btn"
          onClick={onClose}
        >
          <Icon name="chevron" size={18} />
          {t('common.back', {
            defaultValue: 'Назад',
          })}
        </button>
      </div>

      <div className="author-hero">
        {avatarSrc ? (
          <button
            type="button"
            className="artist-avatar-button"
            onClick={() => setAvatarOpen(true)}
            aria-label={t('artist.avatar_open')}
          >
            <div className="profile-avatar">
              <img src={avatarSrc} alt={artist.name} />
            </div>
          </button>
        ) : (
          <div className="profile-avatar">
            {artist.name.charAt(0).toUpperCase()}
          </div>
        )}
        <div className="author-name">
          {artist.name}
        </div>
        <p
          className="author-username"
          style={{ marginTop: 8 }}
        >
          {metaParts.join(' • ')}
        </p>

        {(profiles.length > 0 || supplemental?.status === 'done') && (
          <div
            className="artist-source-switcher"
            role="tablist"
            aria-label={t('artist.sources_label')}
          >
            <button
              type="button"
              role="tab"
              aria-selected={selectedSourceId === null}
              className={
                selectedSourceId === null
                  ? 'artist-source-chip active'
                  : 'artist-source-chip'
              }
              onClick={() => setSelectedSourceId(null)}
            >
              {t('artist.bio_title')}
            </button>
            {profiles.map((p) => (
              <button
                key={p.source_id}
                type="button"
                role="tab"
                aria-selected={selectedSourceId === p.source_id}
                className={
                  selectedSourceId === p.source_id
                    ? 'artist-source-chip active'
                    : 'artist-source-chip'
                }
                onClick={() => setSelectedSourceId(p.source_id)}
              >
                {p.source_name}
              </button>
            ))}
            {supplemental && (supplemental.status === 'done' || supplemental.status === 'fetching' || supplemental.status === 'pending') && (
              <button
                type="button"
                role="tab"
                aria-selected={selectedSourceId === 'yandex'}
                className={
                  selectedSourceId === 'yandex'
                    ? 'artist-source-chip active'
                    : 'artist-source-chip'
                }
                onClick={() => supplemental.status === 'done' ? setSelectedSourceId('yandex') : undefined}
                disabled={supplemental.status !== 'done'}
                title={supplemental.status !== 'done' ? t('artistSupplemental.loading', { defaultValue: 'Загрузка...' }) : undefined}
              >
                {supplemental.status === 'done'
                  ? t('artistSupplemental.tabLabel', { defaultValue: 'Яндекс' })
                  : t('artistSupplemental.loading', { defaultValue: 'Яндекс…' })}
              </button>
            )}
          </div>
        )}

        {sourceName && (
          <div className="artist-source-attribution">
            {t('artist.source_attribution')}:{' '}
            {sourcePageUrl ? (
              <a
                href={sourcePageUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {sourceName}
              </a>
            ) : (
              sourceName
            )}
          </div>
        )}

        {isAdmin && (
          <div
            className="artist-admin-actions"
            style={{ marginTop: 12 }}
          >
            <div className="artist-admin-row">
              <button
                className="btn-primary artist-enrich-btn"
                onClick={handleEnrich}
                disabled={enriching || debugRunning}
              >
                {enriching
                  ? t('artist.enrich_loading')
                  : t('artist.enrich_button')}
              </button>
              <button
                className="btn-secondary artist-enrich-btn"
                onClick={handleEnrichWatch}
                disabled={enriching || debugRunning}
                title={t('artist.debug_run')}
              >
                {debugRunning
                  ? t('artist.debug_running')
                  : t('artist.debug_run')}
              </button>
            </div>

            {enrichError && (
              <div
                className="form-error"
                style={{ marginTop: 6 }}
              >
                {enrichError}
              </div>
            )}

            {(debugRunning ||
              (debugLogs.length > 0 &&
                debugStage !== null)) && (
              <div style={{ marginTop: 10 }}>
                {/* Progress bar */}
                <div
                  style={{
                    width: '100%',
                    height: 3,
                    borderRadius: 2,
                    background:
                      'rgba(255,255,255,0.08)',
                    overflow: 'hidden',
                    marginBottom: 8,
                  }}
                >
                  <div
                    style={{
                      width: `${progressPct}%`,
                      height: '100%',
                      borderRadius: 2,
                      background:
                        'rgba(255,255,255,0.5)',
                      transition:
                        'width 0.6s ease-in-out',
                    }}
                  />
                </div>

                {/* Stage + elapsed + gear toggle */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 12,
                    color: 'rgba(255,255,255,0.5)',
                  }}
                >
                  <span>
                    {debugRunning
                      ? t(
                          'artist.enrich_loading',
                          'Обогащение...',
                        )
                      : debugStage ?? ''}
                  </span>
                  {debugRunning && (
                    <span
                      style={{
                        fontSize: 11,
                        color: 'rgba(255,255,255,0.3)',
                      }}
                    >
                      {elapsed}s
                    </span>
                  )}
                  <button
                    onClick={() =>
                      setDebugOpen((v) => !v)
                    }
                    style={{
                      marginLeft: 'auto',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 2,
                      display: 'flex',
                      alignItems: 'center',
                      color: 'rgba(255,255,255,0.7)',
                    }}
                    title={t('artist.debug_toggle')}
                    aria-label={t(
                      'artist.debug_toggle',
                    )}
                  >
                    <Icon name="settings" size={16} />
                  </button>
                </div>

                {/* DevTools panel */}
                {debugOpen && (
                  <div
                    style={{
                      background:
                        'rgba(10,10,10,0.95)',
                      border:
                        '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 10,
                      padding: '8px 10px',
                      fontSize: 10,
                      fontFamily: 'monospace',
                      color: 'rgba(255,255,255,0.7)',
                      maxHeight: '40vh',
                      overflow: 'auto',
                      marginTop: 8,
                      backdropFilter: 'blur(8px)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        marginBottom: 6,
                        flexWrap: 'wrap',
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 700,
                          color: '#fff',
                          fontSize: 11,
                        }}
                      >
                        DevTools — Artist
                      </span>
                      <span
                        style={{
                          padding: '1px 5px',
                          borderRadius: 4,
                          fontSize: 9,
                          background: debugRunning
                            ? 'rgba(250,204,21,0.2)'
                            : 'rgba(74,222,128,0.2)',
                          color: debugRunning
                            ? '#facc15'
                            : '#4ade80',
                        }}
                      >
                        {debugRunning
                          ? 'RUNNING'
                          : 'DONE'}
                      </span>
                      <button
                        onClick={() =>
                          setDebugLogs([])
                        }
                        style={{
                          marginLeft: 'auto',
                          background:
                            'rgba(255,255,255,0.08)',
                          border: 'none',
                          color:
                            'rgba(255,255,255,0.5)',
                          borderRadius: 4,
                          padding: '2px 6px',
                          fontSize: 9,
                          cursor: 'pointer',
                        }}
                      >
                        Clear
                      </button>
                      <button
                        onClick={() =>
                          setDebugOpen(false)
                        }
                        style={{
                          background:
                            'rgba(255,255,255,0.08)',
                          border: 'none',
                          color:
                            'rgba(255,255,255,0.5)',
                          borderRadius: 4,
                          padding: '2px 6px',
                          fontSize: 9,
                          cursor: 'pointer',
                        }}
                      >
                        Close
                      </button>
                    </div>
                    <div
                      style={{
                        color: 'rgba(255,255,255,0.4)',
                        fontSize: 9,
                        marginBottom: 4,
                      }}
                    >
                      task: {debugTaskId ?? '-'}
                      {' | '}
                      elapsed: {elapsed}s
                      {' | '}
                      stage: {debugStage ?? '-'}
                    </div>
                    <div
                      style={{
                        borderTop:
                          '1px solid rgba(255,255,255,0.08)',
                        paddingTop: 4,
                      }}
                    >
                      {debugLogs.length === 0 ? (
                        <div
                          style={{
                            color:
                              'rgba(255,255,255,0.3)',
                          }}
                        >
                          {t('artist.debug_empty')}
                        </div>
                      ) : (
                        debugLogs.map((line, i) => (
                          <div
                            key={i}
                            style={{
                              padding: '1px 0',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                            }}
                          >
                            {line}
                          </div>
                        ))
                      )}
                      <div ref={logEndRef} />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {view.bio && (
        <div className="artist-bio-section">
          <button
            className="section-header artist-bio-toggle"
            onClick={() => setBioOpen((v) => !v)}
          >
            <span className="section-title">
              {t('artist.bio_title')}
            </span>
            <span className="artist-bio-chevron">
              <Icon name="chevron" size={14} />
            </span>
          </button>
          <div
            className={
              bioOpen
                ? 'artist-bio-text'
                : 'artist-bio-text artist-bio-collapsed'
            }
          >
            {view.bio}
          </div>
          {!bioOpen && (
            <button
              className="artist-bio-more"
              onClick={() => setBioOpen(true)}
            >
              {t('artist.bio_show_more')}
            </button>
          )}
          {bioOpen && (
            <button
              className="artist-bio-more"
              onClick={() => setBioOpen(false)}
            >
              {t('artist.bio_show_less')}
            </button>
          )}
        </div>
      )}

      {(view.birth_date ||
        cleanBirthplace ||
        view.website_url) && (
        <div className="artist-meta-row">
          {view.birth_date && (
            <span>
              {t('artist.born')}: {view.birth_date}
            </span>
          )}
          {cleanBirthplace && (
            <span>
              {t('artist.birthplace')}:{' '}
              {cleanBirthplace}
            </span>
          )}
          {view.website_url && (
            <a
              href={view.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="artist-website-link"
            >
              {t('artist.website')}
            </a>
          )}
        </div>
      )}

      {showPending && (
        <div className="artist-empty-info">
          {t('artist.enrichment_pending')}
        </div>
      )}

      {showNoInfo && (
        <div className="artist-empty-info">
          {t('artist.no_info')}
        </div>
      )}

      {view.discography.length > 0 && (
        <div className="artist-discography">
          <div className="section-header">
            <span className="section-title">
              {t('artist.discography_title')}{' '}
              ({view.discography.length})
            </span>
          </div>
          {view.discography.map((item, i) => (
            <div
              key={`${item.title}-${i}`}
              className="discography-item"
            >
              {item.url ? (
                <a
                  className="discography-title"
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {item.title}
                </a>
              ) : (
                <span className="discography-title">
                  {item.title}
                </span>
              )}
              {item.year && (
                <span className="discography-year">
                  {item.year}
                </span>
              )}
              {item.type && (
                <span className="discography-type">
                  {item.type}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Admin: refresh Yandex supplemental (only when done) */}
      {isAdmin && supplemental?.status === 'done' && (
        <div style={{ padding: '0 16px 8px' }}>
          <button
            className="btn-secondary artist-supplemental-refresh"
            onClick={handleRefreshSupplemental}
            disabled={refreshingSupplemental}
          >
            <Icon name="refresh" size={13} />
            {refreshingSupplemental
              ? t('trackInfo.loading', { defaultValue: 'Обновление...' })
              : t('trackInfo.refresh', { defaultValue: 'Обновить Яндекс' })}
          </button>
        </div>
      )}

      {/* Platform tracks */}
      <div className="section-header">
        <span className="section-title">
          {t('artist.tracks_title')}{' '}
          {tracks !== null && tracks.length > 0
            ? `(${tracks.length})`
            : ''}
        </span>
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage={t('artist.tracks_empty')}
      />

      {avatarOpen && avatarSrc && (
        <ArtistAvatarViewer
          src={avatarSrc}
          alt={artist.name}
          onClose={() => setAvatarOpen(false)}
        />
      )}
    </div>
  )
}
