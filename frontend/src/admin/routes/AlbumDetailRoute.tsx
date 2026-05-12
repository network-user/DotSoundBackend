import { useEffect, useRef, useState } from 'react'
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
  description: string | null
  cover_key: string | null
}

export function AlbumDetailRoute() {
  const { t } = useTranslation()
  const { albumId: albumIdParam } = useParams()
  const albumId = parseInt(albumIdParam ?? '', 10)
  const { showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const coverInputRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
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

  // per-track inline editing
  const [editingTrackId, setEditingTrackId] = useState<number | null>(
    null,
  )
  const [editTitle, setEditTitle] = useState('')
  const [editArtist, setEditArtist] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const trackCoverRefs = useRef<Map<number, HTMLInputElement>>(new Map())

  const detailQuery = useQuery({
    queryKey: ['admin', 'album', albumId],
    queryFn: () => adminApi.getAdminAlbum(albumId),
    enabled: Number.isFinite(albumId) && albumId > 0,
  })

  useEffect(() => {
    const d = detailQuery.data
    if (!d) return
    setTitle(String(d.title ?? ''))
    setDescription(d.description ?? '')
    setOwnerId(String(d.owner_id ?? ''))
    setIsPublic(Boolean(d.is_public))
    const trs = (d.tracks ?? []) as DetailTrack[]
    setOrderedTrackIds(trs.map((x) => x.id))
  }, [detailQuery.data])

  const refreshList = () =>
    qc.invalidateQueries({ queryKey: ['admin', 'albums'] })
  const refreshDetail = () => {
    qc.invalidateQueries({
      queryKey: ['admin', 'album', albumId],
    })
  }

  const saveMetaMutation = useMutation({
    mutationFn: async () => {
      const oid = parseInt(ownerId, 10)
      await adminApi.patchAdminAlbum(albumId, {
        title: title.trim() || undefined,
        description: description.trim() || null,
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

  const handleCoverChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    setBusy(true)
    try {
      await adminApi.uploadAdminAlbumCover(albumId, f)
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
      await adminApi.reorderAdminAlbumTracks(albumId, orderedTrackIds)
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
      await adminApi.removeAdminAlbumTrack(albumId, trackId)
      setOrderedTrackIds((prev) => prev.filter((id) => id !== trackId))
      if (editingTrackId === trackId) setEditingTrackId(null)
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
      await adminApi.addAdminAlbumTrack(albumId, trackId)
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

  // debounced track search for the add-modal
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
          res.items.filter((it) => !inPl.has(it.id as number)),
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

  const saveTrackMetaMut = useMutation({
    mutationFn: (args: {
      trackId: number
      title: string
      artist: string | null
      description: string | null
    }) =>
      adminApi.updateTrackMetadata(args.trackId, {
        title: args.title,
        artist: args.artist,
        description: args.description,
      }),
    onSuccess: () => {
      setEditingTrackId(null)
      refreshDetail()
    },
  })

  const uploadTrackCoverMut = useMutation({
    mutationFn: (args: { trackId: number; file: File }) =>
      adminApi.uploadTrackCover(args.trackId, args.file),
    onSuccess: () => refreshDetail(),
  })

  const handleSaveTrackMeta = async (tid: number) => {
    try {
      await saveTrackMetaMut.mutateAsync({
        trackId: tid,
        title: editTitle.trim(),
        artist: editArtist.trim() || null,
        description: editDescription.trim() || null,
      })
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    }
  }

  const handleTrackCoverChange = async (
    tid: number,
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    try {
      await uploadTrackCoverMut.mutateAsync({ trackId: tid, file: f })
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    }
  }

  const startEdit = (tr: DetailTrack) => {
    setEditingTrackId(tr.id)
    setEditTitle(tr.title ?? '')
    setEditArtist(tr.artist ?? '')
    setEditDescription(tr.description ?? '')
  }

  const coverKey = detailQuery.data?.cover_key as
    | string
    | null
    | undefined
  const coverSrc = coverKey
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(coverKey)}`
    : null

  if (!Number.isFinite(albumId) || albumId <= 0) {
    return (
      <section className="admin-card">
        <p className="admin-card__sub">
          {t('admin.albums.invalidId')}
        </p>
        <Link to={getAdminPanelRoute('/albums')}>
          {t('admin.albums.backToList')}
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
          {t('admin.albums.loadError')}
        </p>
        <Link to={getAdminPanelRoute('/albums')}>
          {t('admin.albums.backToList')}
        </Link>
      </section>
    )
  }

  return (
    <section className="admin-card admin-card--editor">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: 16,
        }}
      >
        <div>
          <Link
            to={getAdminPanelRoute('/albums')}
            className="admin-card__sub"
            style={{ textDecoration: 'none' }}
          >
            ← {t('admin.albums.backToList')}
          </Link>
          <h1 style={{ margin: '8px 0 0', fontSize: 22 }}>
            {t('admin.albums.editorTitle', { id: albumId })}
          </h1>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          marginBottom: 20,
        }}
      >
        {coverSrc ? (
          <img
            src={coverSrc}
            alt=""
            width={120}
            height={120}
            style={{
              objectFit: 'cover',
              borderRadius: 8,
              border: '1px solid var(--border)',
            }}
          />
        ) : (
          <div
            style={{
              width: 120,
              height: 120,
              borderRadius: 8,
              border: '1px dashed var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-secondary)',
            }}
          >
            <Icon name="music" size={40} />
          </div>
        )}
        <input
          ref={coverInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: 'none' }}
          onChange={handleCoverChange}
        />
        <MotionPress
          variant="ghost"
          disabled={busy}
          onClick={() => coverInputRef.current?.click()}
        >
          {t('admin.albums.changeCover')}
        </MotionPress>
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
          {t('admin.albums.fieldTitle')}
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
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
          {t('admin.albums.fieldDescription')}
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              color: 'var(--text)',
              resize: 'vertical',
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
          {t('admin.albums.fieldOwner')}
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
          {t('admin.albums.fieldPublic')}
        </label>
        <MotionPress
          variant="primary"
          onClick={() => void handleSaveMeta()}
          disabled={saveMetaMutation.isPending || busy}
        >
          {t('admin.albums.saveMeta')}
        </MotionPress>
      </div>

      <h2 style={{ margin: '24px 0 12px', fontSize: 17 }}>
        {t('admin.albums.tracksTitle')}
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
          const isEditing = editingTrackId === tid
          const coverUrl = tr?.cover_key
            ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(tr.cover_key)}`
            : null
          return (
            <li
              key={tid}
              style={{
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
                overflow: 'hidden',
              }}
            >
              {/* track row header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 10px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
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
                      <Icon name="music" size={16} />
                    )}
                  </div>
                  <span
                    style={{
                      fontSize: 14,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {tr?.title ?? `#${tid}`}
                    {tr?.artist ? ` — ${tr.artist}` : ''}
                  </span>
                </div>
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
                    aria-label="up"
                    disabled={busy || idx === 0}
                    onClick={() => moveTrack(idx, -1)}
                  >
                    <Icon name="chevron-up" size={18} />
                  </MotionPress>
                  <MotionPress
                    variant="ghost"
                    aria-label="down"
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
                    onClick={() => {
                      if (isEditing) {
                        setEditingTrackId(null)
                      } else if (tr) {
                        startEdit(tr)
                      }
                    }}
                  >
                    {isEditing
                      ? t('admin.common.cancel')
                      : t('admin.albums.editTrack')}
                  </MotionPress>
                  <MotionPress
                    variant="ghost"
                    disabled={busy}
                    onClick={() => void handleRemoveTrack(tid)}
                  >
                    {t('admin.albums.removeTrack')}
                  </MotionPress>
                </span>
              </div>

              {/* inline edit panel */}
              {isEditing && (
                <div
                  style={{
                    padding: '12px 14px',
                    borderTop: '1px solid var(--border)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                  }}
                >
                  {/* cover upload row */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                    }}
                  >
                    <div
                      style={{
                        width: 56,
                        height: 56,
                        borderRadius: 8,
                        overflow: 'hidden',
                        flexShrink: 0,
                        background: 'var(--surface)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: coverUrl
                          ? 'none'
                          : '1px dashed var(--border)',
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
                        <Icon name="music" size={20} />
                      )}
                    </div>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      style={{ display: 'none' }}
                      ref={(el) => {
                        if (el) trackCoverRefs.current.set(tid, el)
                        else trackCoverRefs.current.delete(tid)
                      }}
                      onChange={(e) =>
                        void handleTrackCoverChange(tid, e)
                      }
                    />
                    <MotionPress
                      variant="ghost"
                      disabled={uploadTrackCoverMut.isPending}
                      onClick={() =>
                        trackCoverRefs.current.get(tid)?.click()
                      }
                    >
                      {t('admin.albums.changeTrackCover')}
                    </MotionPress>
                  </div>

                  <label
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 3,
                      fontSize: 13,
                    }}
                  >
                    {t('admin.albums.fieldTitle')}
                    <input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 6,
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
                      gap: 3,
                      fontSize: 13,
                    }}
                  >
                    {t('admin.albums.trackArtist')}
                    <input
                      value={editArtist}
                      onChange={(e) => setEditArtist(e.target.value)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 6,
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
                      gap: 3,
                      fontSize: 13,
                    }}
                  >
                    {t('admin.albums.fieldDescription')}
                    <textarea
                      rows={2}
                      value={editDescription}
                      onChange={(e) =>
                        setEditDescription(e.target.value)
                      }
                      style={{
                        padding: '6px 10px',
                        borderRadius: 6,
                        border: '1px solid var(--border)',
                        background: 'var(--surface)',
                        color: 'var(--text)',
                        resize: 'vertical',
                      }}
                    />
                  </label>
                  <MotionPress
                    variant="primary"
                    disabled={
                      saveTrackMetaMut.isPending || !editTitle.trim()
                    }
                    onClick={() => void handleSaveTrackMeta(tid)}
                  >
                    {t('admin.albums.saveTrackMeta')}
                  </MotionPress>
                </div>
              )}
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
          {t('admin.albums.saveOrder')}
        </MotionPress>
        <MotionPress
          variant="ghost"
          disabled={busy}
          onClick={() => {
            setAddModal(true)
            setAddSearch('')
          }}
        >
          {t('admin.albums.addTrack')}
        </MotionPress>
      </div>

      {addModal && (
        <div
          className="admin-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setAddModal(false)
          }}
        >
          <div className="admin-modal">
            <h3>{t('admin.albums.addTrackTitle')}</h3>
            <div
              className="admin-toolbar"
              style={{ marginBottom: 12 }}
            >
              <input
                type="search"
                placeholder={t('admin.albums.addTrackSearch')}
                value={addSearch}
                autoFocus
                onChange={(e) => setAddSearch(e.target.value)}
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
                const art = it.artist as string | null | undefined
                const ck = it.cover_key as string | null | undefined
                const itemCoverUrl = ck
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
                      borderBottom: '1px solid var(--border)',
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
                      {itemCoverUrl ? (
                        <img
                          src={itemCoverUrl}
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
                      onClick={() => void handleAddTrack(id)}
                    >
                      {t('admin.albums.addTrack')}
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
                {t('admin.albums.addTrackAllInAlbum')}
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
