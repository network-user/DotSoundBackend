import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Icon } from '@/components/Icon/Icon'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

interface AlbumRow {
  id: number
  title: string
  owner_id: number
  is_public: boolean
  created_at: string
  track_count: number
}

interface DetailTrack {
  id: number
  title: string
  artist: string | null
}

export function AlbumsRoute() {
  const { t } = useTranslation()
  const { showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const coverInputRef = useRef<HTMLInputElement>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [ownerId, setOwnerId] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const [orderedTrackIds, setOrderedTrackIds] = useState<number[]>([])
  const [addModal, setAddModal] = useState(false)
  const [addSearch, setAddSearch] = useState('')
  const [addPage, setAddPage] = useState(1)
  const [busy, setBusy] = useState(false)

  const { data, isFetching } = useQuery({
    queryKey: ['admin', 'albums', page, search],
    queryFn: () =>
      adminApi.listAdminAlbums({
        page,
        size: 25,
        search: search || undefined,
      }),
    placeholderData: keepPreviousData,
  })

  const detailQuery = useQuery({
    queryKey: ['admin', 'album', selectedId],
    queryFn: () => adminApi.getAdminAlbum(selectedId!),
    enabled: selectedId != null,
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

  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / 25))
  const rows = (data?.items ?? []) as AlbumRow[]

  const refreshList = () =>
    qc.invalidateQueries({ queryKey: ['admin', 'albums'] })
  const refreshDetail = () => {
    qc.invalidateQueries({ queryKey: ['admin', 'album'] })
  }

  const saveMetaMutation = useMutation({
    mutationFn: async () => {
      if (selectedId == null) return
      const oid = parseInt(ownerId, 10)
      await adminApi.patchAdminAlbum(selectedId, {
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
    if (!f || selectedId == null) return
    setBusy(true)
    try {
      await adminApi.uploadAdminAlbumCover(selectedId, f)
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
    if (selectedId == null) return
    setBusy(true)
    try {
      await adminApi.reorderAdminAlbumTracks(
        selectedId,
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
    if (selectedId == null) return
    setBusy(true)
    try {
      await adminApi.removeAdminAlbumTrack(selectedId, trackId)
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
    if (selectedId == null) return
    setBusy(true)
    try {
      await adminApi.addAdminAlbumTrack(selectedId, trackId)
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

  const addQuery = useQuery({
    queryKey: ['admin', 'albums', 'pick-track', addPage, addSearch],
    queryFn: () =>
      adminApi.listTracks({
        page: addPage,
        size: 15,
        search: addSearch || undefined,
      }),
    enabled: addModal,
  })

  const columns: ColumnDef<AlbumRow>[] = [
    {
      accessorKey: 'id',
      header: t('admin.albums.colId'),
      cell: ({ row }) => row.original.id,
    },
    {
      accessorKey: 'title',
      header: t('admin.albums.colTitle'),
      cell: ({ row }) => row.original.title,
    },
    {
      accessorKey: 'owner_id',
      header: t('admin.albums.colOwner'),
      cell: ({ row }) => row.original.owner_id,
    },
    {
      accessorKey: 'track_count',
      header: t('admin.albums.colTracks'),
      cell: ({ row }) => row.original.track_count,
    },
    {
      id: 'pub',
      header: t('admin.albums.colPublic'),
      cell: ({ row }) =>
        row.original.is_public ? (
          <StatusPill kind="ok">
            {t('admin.albums.public')}
          </StatusPill>
        ) : (
          <StatusPill kind="warn">
            {t('admin.albums.private')}
          </StatusPill>
        ),
    },
    {
      id: 'open',
      header: '',
      cell: ({ row }) => (
        <Press
          variant="ghost"
          onClick={() => setSelectedId(row.original.id)}
        >
          {t('admin.albums.open')}
        </Press>
      ),
    },
  ]

  const coverKey = detailQuery.data?.cover_key as
    | string
    | null
    | undefined
  const coverSrc = coverKey
    ? `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(coverKey)}`
    : null

  return (
    <div className="admin-albums-layout">
      <section className="admin-card">
        <h1>{t('admin.albums.title')}</h1>
        <div className="admin-toolbar">
          <input
            type="search"
            placeholder={t('admin.albums.searchPlaceholder')}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
        </div>
        <DataTable
          columns={columns}
          rows={rows}
          emptyHint={t('admin.albums.empty')}
        />
        <div className="admin-pagination">
          <Press
            variant="ghost"
            disabled={page <= 1 || isFetching}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            {t('admin.common.prev')}
          </Press>
          <span>
            {page} / {totalPages} ·{' '}
            {t('admin.common.total', { count: total })}
          </span>
          <Press
            variant="ghost"
            disabled={page >= totalPages || isFetching}
            onClick={() =>
              setPage((p) => Math.min(totalPages, p + 1))
            }
          >
            {t('admin.common.next')}
          </Press>
        </div>
      </section>

      <section className="admin-card">
        {selectedId == null ? (
          <p className="admin-card__sub">
            {t('admin.albums.selectHint')}
          </p>
        ) : detailQuery.isLoading ? (
          <p className="admin-card__sub">…</p>
        ) : detailQuery.isError ? (
          <p className="admin-card__sub">
            {t('admin.albums.loadError')}
          </p>
        ) : (
          <>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                marginBottom: 12,
              }}
            >
              <h2 style={{ margin: 0 }}>
                {t('admin.albums.editorTitle', {
                  id: selectedId,
                })}
              </h2>
              <Press
                variant="ghost"
                onClick={() => setSelectedId(null)}
              >
                {t('admin.albums.close')}
              </Press>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                marginBottom: 16,
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
              <Press
                variant="default"
                disabled={busy}
                onClick={() => coverInputRef.current?.click()}
              >
                {t('admin.albums.changeCover')}
              </Press>
            </div>

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
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
              <Press
                variant="primary"
                onClick={() => void handleSaveMeta()}
                disabled={saveMetaMutation.isPending || busy}
              >
                {t('admin.albums.saveMeta')}
              </Press>
            </div>

            <h3 style={{ margin: '20px 0 8px', fontSize: 15 }}>
              {t('admin.albums.tracksTitle')}
            </h3>
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
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
                      <Press
                        variant="ghost"
                        aria-label="up"
                        disabled={busy || idx === 0}
                        onClick={() => moveTrack(idx, -1)}
                      >
                        <Icon name="chevron-up" size={18} />
                      </Press>
                      <Press
                        variant="ghost"
                        aria-label="down"
                        disabled={
                          busy ||
                          idx === orderedTrackIds.length - 1
                        }
                        onClick={() => moveTrack(idx, 1)}
                      >
                        <Icon name="chevron-down" size={18} />
                      </Press>
                      <Press
                        variant="ghost"
                        disabled={busy}
                        onClick={() => void handleRemoveTrack(tid)}
                      >
                        {t('admin.albums.removeTrack')}
                      </Press>
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
              <Press
                variant="default"
                disabled={busy}
                onClick={() => void handleSaveOrder()}
              >
                {t('admin.albums.saveOrder')}
              </Press>
              <Press
                variant="default"
                disabled={busy}
                onClick={() => {
                  setAddModal(true)
                  setAddPage(1)
                  setAddSearch('')
                }}
              >
                {t('admin.albums.addTrack')}
              </Press>
            </div>
          </>
        )}
      </section>

      {addModal && (
        <div
          className="admin-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setAddModal(false)
          }}
        >
          <div className="admin-modal">
            <h3>{t('admin.albums.addTrackTitle')}</h3>
            <div className="admin-toolbar" style={{ marginBottom: 12 }}>
              <input
                type="search"
                placeholder={t('admin.albums.addTrackSearch')}
                value={addSearch}
                onChange={(e) => {
                  setAddSearch(e.target.value)
                  setAddPage(1)
                }}
              />
            </div>
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                maxHeight: 320,
                overflow: 'auto',
              }}
            >
              {(addQuery.data?.items ?? []).map(
                (it: Record<string, unknown>) => {
                  const id = it.id as number
                  const ttl = String(it.title ?? '')
                  const art = it.artist as string | null
                  return (
                    <li key={id} style={{ marginBottom: 6 }}>
                      <Press
                        variant="ghost"
                        disabled={busy}
                        onClick={() => void handleAddTrack(id)}
                        style={{
                          width: '100%',
                          justifyContent: 'flex-start',
                        }}
                      >
                        {ttl}
                        {art ? ` — ${art}` : ''}{' '}
                        <span
                          style={{
                            color: 'var(--text-secondary)',
                          }}
                        >
                          #{id}
                        </span>
                      </Press>
                    </li>
                  )
                },
              )}
            </ul>
            <div className="admin-pagination">
              <Press
                variant="ghost"
                disabled={addPage <= 1}
                onClick={() =>
                  setAddPage((p) => Math.max(1, p - 1))
                }
              >
                {t('admin.common.prev')}
              </Press>
              <Press
                variant="ghost"
                disabled={
                  !addQuery.data ||
                  (addQuery.data.items?.length ?? 0) < 15
                }
                onClick={() => setAddPage((p) => p + 1)}
              >
                {t('admin.common.next')}
              </Press>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
