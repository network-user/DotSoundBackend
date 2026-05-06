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
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'

interface DetailTrack {
  id: number
  title: string
  artist: string | null
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
  const [addPage, setAddPage] = useState(1)
  const [busy, setBusy] = useState(false)

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
    qc.invalidateQueries({ queryKey: ['admin', 'album'] })
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
      await adminApi.reorderAdminAlbumTracks(
        albumId,
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
      await adminApi.removeAdminAlbumTrack(albumId, trackId)
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
        <Link to="/admin/albums">{t('admin.albums.backToList')}</Link>
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
        <Link to="/admin/albums">{t('admin.albums.backToList')}</Link>
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
            to="/admin/albums"
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
                  onClick={() => void handleRemoveTrack(tid)}
                >
                  {t('admin.albums.removeTrack')}
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
          {t('admin.albums.saveOrder')}
        </MotionPress>
        <MotionPress
          variant="ghost"
          disabled={busy}
          onClick={() => {
            setAddModal(true)
            setAddPage(1)
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
                      <MotionPress
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
                      </MotionPress>
                    </li>
                  )
                },
              )}
            </ul>
            <div className="admin-pagination">
              <MotionPress
                variant="ghost"
                disabled={addPage <= 1}
                onClick={() =>
                  setAddPage((p) => Math.max(1, p - 1))
                }
              >
                {t('admin.common.prev')}
              </MotionPress>
              <MotionPress
                variant="ghost"
                disabled={
                  !addQuery.data ||
                  (addQuery.data.items?.length ?? 0) < 15
                }
                onClick={() => setAddPage((p) => p + 1)}
              >
                {t('admin.common.next')}
              </MotionPress>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
