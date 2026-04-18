import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'
import type { ArtistDetail, Track } from '@/types/api'

interface Props {
  artistId: number
  onClose: () => void
}

function hasAnyInfo(artist: ArtistDetail): boolean {
  return Boolean(
    artist.bio ||
      artist.birth_date ||
      artist.birthplace ||
      artist.country ||
      artist.website_url,
  )
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

    return () => {
      cancelled = true
    }
  }, [artistId])

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

  if (!artist) {
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

  const metaParts: string[] = []
  if (artist.age !== null && artist.age !== undefined) {
    metaParts.push(t('artist.age', { count: artist.age }))
  }
  const cleanBirthplace = cleanWikiText(
    artist.birthplace,
  )
  if (cleanBirthplace) {
    metaParts.push(cleanBirthplace)
  } else if (artist.country) {
    metaParts.push(artist.country)
  }
  if (metaParts.length === 0) {
    metaParts.push(t('artist.performer'))
  }
  const infoKnown = hasAnyInfo(artist)
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
        <div className="profile-avatar">
          {artist.image_url ? (
            <img
              src={artist.image_url}
              alt={artist.name}
            />
          ) : (
            artist.name.charAt(0).toUpperCase()
          )}
        </div>
        <div className="author-name">
          {artist.name}
        </div>
        <p
          className="author-username"
          style={{ marginTop: 8 }}
        >
          {metaParts.join(' • ')}
        </p>

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

      {artist.bio && (
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
            {artist.bio}
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

      {(artist.birth_date ||
        cleanBirthplace ||
        artist.website_url) && (
        <div className="artist-meta-row">
          {artist.birth_date && (
            <span>
              {t('artist.born')}:{' '}
              {artist.birth_date}
            </span>
          )}
          {cleanBirthplace && (
            <span>
              {t('artist.birthplace')}:{' '}
              {cleanBirthplace}
            </span>
          )}
          {artist.website_url && (
            <a
              href={artist.website_url}
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

      {/* Discography from external sources */}
      {artist.discography &&
        artist.discography.length > 0 && (
          <div className="artist-discography">
            <div className="section-header">
              <span className="section-title">
                {t('artist.discography_title', {
                  defaultValue: 'Дискография',
                })}{' '}
                ({artist.discography.length})
              </span>
            </div>
            {artist.discography.map(
              (item, i) => (
                <div
                  key={i}
                  className="discography-item"
                >
                  <span className="discography-title">
                    {item.title}
                  </span>
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
              ),
            )}
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
    </div>
  )
}
