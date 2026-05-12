import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { getAdminPanelRoute } from '@/lib/adminPath'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'

interface DetailTrack {
  id: number
  title: string
  artist: string | null
}

export function PlaylistDetailRoute() {
  const { t } = useTranslation()
  const { playlistId: playlistIdParam } = useParams()
  const playlistId = parseInt(playlistIdParam ?? '', 10)
  const { showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [ownerId, setOwnerId] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const [orderedTrackIds, setOrderedTrackIds] = useState<number[]>([])
  const [addModal, setAddModal] = useState(false)
  const [addSearch, setAddSearch] = useState('')
  const [addResults, setAddResults] = useState<
    Array<Record<string, unknown>>
  >([])
  const [addLoading, setAddLoading] = useState(false)
  const [busy, setBusy] = useState(false)

  const detailQuery = useQuery({
    queryKey: ['admin', 'playlist', playlistId],
    queryFn: () => adminApi.getAdminPlaylist(playlistId),
    enabled: Number.isFinite(playlistId) && playlistId > 0,
  })

  useEffect(() => {
    const d = detailQuery.data
    if (!d) return
    setName(String(d.name ?? ''))
    setOwnerId(String(d.owner_id ?? ''))
    setIsPublic(Boolean(d.is_public))
    const trs = (d.tracks ?? []) as DetailTrack[]
    setOrderedTrackIds(trs.map((x) => x.id))
  }, [detailQuery.data])

  const refreshList = () =>
    qc.invalidateQueries({ queryKey: ['admin', 'playlists'] })
  const refreshDetail = () => {
    qc.invalidateQueries({
      queryKey: ['admin', 'playlist', playlistId],
    })
  }

  const saveMetaMutation = useMutation({
    mutationFn: async () => {
      const oid = parseInt(ownerId, 10)
      await adminApi.patchAdminPlaylist(playlistId, {
        name: name.trim() || undefined,
        is_public: isPublic,
        owner_id: Number.isFinite(oid) ? oid : undefined,
      })
    },
    onSuccess: () => {
      refreshList()
      refreshDetail()
    },
  })

  const handleSaveMeta = async () => {
    try {
      await saveMetaMutation.mutateAsync()
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    }
  }

  const trackById = new Map<number, DetailTrack>()
  const dtracks = (detailQuery.data?.tracks ?? []) as DetailTrack[]
  for (const tr of dtracks) {
    trackById.set(tr.id, tr)
  }

  const moveTrack = (idx: number, dir: -1 | 1) => {
    const j = idx + dir
    if (j < 0 || j >= orderedTrackIds.length) return
    setOrderedTrackIds((prev) => {
      const next = [...prev]
      ;[next[idx], next[j]] = [next[j], next[idx]]
      return next
    })
  }

  const handleSaveOrder = async () => {
    setBusy(true)
    try {
      await adminApi.reorderAdminPlaylistTracks(
        playlistId,
        orderedTrackIds,
      )
      refreshDetail()
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusy(false)
    }
  }

  const handleRemoveTrack = async (trackId: number) => {
    setBusy(true)
    try {
      await adminApi.removeAdminPlaylistTrack(playlistId, trackId)
      setOrderedTrackIds((prev) =>
        prev.filter((id) => id !== trackId),
      )
      refreshDetail()
      refreshList()
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusy(false)
    }
  }

  const handleAddTrack = async (trackId: number) => {
    setBusy(true)
    try {
      await adminApi.addAdminPlaylistTrack(playlistId, trackId)
      setAddModal(false)
      refreshDetail()
      refreshList()
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!addModal) {
      setAddResults([])
      return
    }
    let cancelled = false
    setAddLoading(true)
    const timer = window.setTimeout(async () => {
      try {
        const res = await adminApi.listTracks({
          search: addSearch.trim() || undefined,
          size: 20,
        })
        if (cancelled) return
        const inPl = new Set(orderedTrackIds)
        setAddResults(
          res.items.filter(
            (it) => !inPl.has(it.id as number),
          ),
        )
      } catch {
        if (!cancelled) setAddResults([])
      } finally {
        if (!cancelled) setAddLoading(false)
      }
    }, 300)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [addModal, addSearch, orderedTrackIds])

  if (!Number.isFinite(playlistId) || playlistId <= 0) {
    return (
      <section className="admin-card">
        <p className="admin-card__sub">
          {t('admin.playlists.invalidId')}
        </p>
        <Link to={getAdminPanelRoute('/playlists')}>
          {t('admin.playlists.backToList')}
        </Link>
      </section>
    )
  }

  if (detailQuery.isLoading) {
    return (
      <section className="admin-card">
        <p className="admin-card__sub">…</p>
      </section>
    )
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <section className="admin-card">
        <p className="admin-card__sub">
          {t('admin.playlists.loadError')}
        </p>
        <Link to={getAdminPanelRoute('/playlists')}>
          {t('admin.playlists.backToList')}
        </Link>
      </section>
    )
  }

  return (
    <section className="admin-card admin-card--editor">
      <div style={{ marginBottom: 16 }}>
        <Link
          to={getAdminPanelRoute('/playlists')}
          className="admin-card__sub"
          style={{ textDecoration: 'none' }}
        >
          ← {t('admin.playlists.backToList')}
        </Link>
        <h1 style={{ margin: '8px 0 0', fontSize: 22 }}>
          {t('admin.playlists.editorTitle', { id: playlistId })}
        </h1>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 20,
          color: 'var(--text-secondary)',
        }}
      >
        <Icon name="list" size={28} />
        <span style={{ fontSize: 14 }}>
          {t('admin.playlists.editorHint')}
        </span>
      </div>

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          maxWidth: 560,
        }}
      >
        <label
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            fontSize: 13,
          }}
        >
          {t('admin.playlists.fieldName')}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              color: 'var(--text)',
            }}
          />
        </label>
        <label
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            fontSize: 13,
          }}
        >
          {t('admin.playlists.fieldOwner')}
          <input
            inputMode="numeric"
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              color: 'var(--text)',
            }}
          />
        </label>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 13,
          }}
        >
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
          />
          {t('admin.playlists.fieldPublic')}
        </label>
        <MotionPress
          variant="primary"
          onClick={() => void handleSaveMeta()}
          disabled={saveMetaMutation.isPending || busy}
        >
          {t('admin.playlists.saveMeta')}
        </MotionPress>
      </div>

      <h2 style={{ margin: '24px 0 12px', fontSize: 17 }}>
        {t('admin.playlists.tracksTitle')}
      </h2>
      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          maxWidth: 720,
        }}
      >
        {orderedTrackIds.map((tid, idx) => {
          const tr = trackById.get(tid)
          return (
            <li
              key={tid}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 8,
                padding: '8px 10px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
              }}
            >
              <span
                style={{
                  fontSize: 14,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {tr?.title ?? `#${tid}`}
                {tr?.artist ? ` — ${tr.artist}` : ''}
              </span>
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  flexShrink: 0,
                }}
              >
                <MotionPress
                  variant="ghost"
                  disabled={busy || idx === 0}
                  onClick={() => moveTrack(idx, -1)}
                >
                  <Icon name="chevron-up" size={18} />
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  disabled={
                    busy || idx === orderedTrackIds.length - 1
                  }
                  onClick={() => moveTrack(idx, 1)}
                >
                  <Icon name="chevron-down" size={18} />
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  disabled={busy}
                  onClick={() => void handleRemoveTrack(tid)}
                >
                  {t('admin.playlists.removeTrack')}
                </MotionPress>
              </span>
            </li>
          )
        })}
      </ul>
      <div
        style={{
          display: 'flex',
          gap: 8,
          marginTop: 12,
          flexWrap: 'wrap',
        }}
      >
        <MotionPress
          variant="ghost"
          disabled={busy}
          onClick={() => void handleSaveOrder()}
        >
          {t('admin.playlists.saveOrder')}
        </MotionPress>
        <MotionPress
          variant="ghost"
          disabled={busy}
          onClick={() => {
            setAddModal(true)
            setAddSearch('')
          }}
        >
          {t('admin.playlists.addTrack')}
        </MotionPress>
      </div>

      {addModal && (
        <div
          className="admin-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget)
              setAddModal(false)
          }}
        >
          <div className="admin-modal">
            <h3>{t('admin.playlists.addTrackTitle')}</h3>
            <div
              className="admin-toolbar"
              style={{ marginBottom: 12 }}
            >
              <input
                type="search"
                placeholder={t(
                  'admin.playlists.addTrackSearch',
                )}
                value={addSearch}
                autoFocus
                onChange={(e) =>
                  setAddSearch(e.target.value)
                }
              />
            </div>
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                maxHeight: 360,
                overflowY: 'auto',
              }}
            >
              {addResults.map((it) => {
                const id = it.id as number
                const ttl = String(it.title ?? '')
                const art = it.artist as
                  | string
                  | null
                  | undefined
                const ck = it.cover_key as
                  | string
                  | null
                  | undefined
                const coverUrl = ck
                  ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(ck)}`
                  : null
                return (
                  <li
                    key={id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '5px 2px',
                      borderBottom:
                        '1px solid var(--border)',
                    }}
                  >
                    <div
                      style={{
                        width: 38,
                        height: 38,
                        borderRadius: 6,
                        overflow: 'hidden',
                        flexShrink: 0,
                        background: 'var(--surface)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {coverUrl ? (
                        <img
                          src={coverUrl}
                          alt=""
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            display: 'block',
                          }}
                        />
                      ) : (
                        <Icon name="music" size={18} />
                      )}
                    </div>
                    <div
                      style={{
                        flex: 1,
                        overflow: 'hidden',
                        minWidth: 0,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 500,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {ttl}
                      </div>
                      {art && (
                        <div
                          style={{
                            fontSize: 12,
                            color: 'var(--text-secondary)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {art}
                        </div>
                      )}
                    </div>
                    <MotionPress
                      variant="ghost"
                      disabled={busy}
                      style={{ flexShrink: 0, fontSize: 13 }}
                      onClick={() =>
                        void handleAddTrack(id)
                      }
                    >
                      {t('admin.playlists.addTrack')}
                    </MotionPress>
                  </li>
                )
              })}
            </ul>
            {addResults.length === 0 && !addLoading && (
              <p
                className="admin-card__sub"
                style={{ margin: '12px 0 4px' }}
              >
                {t(
                  'admin.playlists.addTrackAllInPlaylist',
                )}
              </p>
            )}
            {addLoading && (
              <p
                className="admin-card__sub"
                style={{ margin: '12px 0 4px' }}
              >
                …
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
