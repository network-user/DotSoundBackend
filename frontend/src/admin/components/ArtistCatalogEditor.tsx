import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Press } from '@/components/ui/Press'
import { Sheet } from '@/components/ui/Sheet'
import { useStepUp } from './auth/StepUpDialog'
import { useAdminPrompt } from './layout/AdminPromptContext'
import { adminApi } from '../lib/adminApi'

type CatalogReleaseRow = {
  id: number
  title: string
  track_count: number
  manual_lock: boolean
  soundcloud_album_id: number | null
  display_position: number
}

function reorderIds(
  ids: number[],
  from: number,
  to: number,
): number[] {
  if (
    from === to ||
    from < 0 ||
    to < 0 ||
    from >= ids.length ||
    to >= ids.length
  ) {
    return ids
  }
  const next = [...ids]
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}

export function ArtistCatalogEditor({
  artistId,
  artistName,
  open,
  onClose,
}: {
  artistId: number
  artistName: string
  open: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const stepUp = useStepUp()
  const { showAlert, showConfirm } = useAdminPrompt()
  const [scUser, setScUser] = useState('')
  const [scPerm, setScPerm] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [selectedReleaseId, setSelectedReleaseId] = useState<
    number | null
  >(null)
  const [trackSearch, setTrackSearch] = useState('')
  const [pendingTrackIds, setPendingTrackIds] = useState<
    number[] | null
  >(null)
  const avatarInputRef = useRef<HTMLInputElement>(null)

  const overview = useQuery({
    queryKey: ['admin', 'catalog', artistId],
    queryFn: () => adminApi.catalogOverview(artistId),
    enabled: open,
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchInterval: (q) =>
      q.state.data?.catalog_sync_state === 'running'
        ? 1500
        : false,
  })

  useEffect(() => {
    if (!overview.data) return
    const u = overview.data.soundcloud_user_id
    setScUser(u === null ? '' : String(u))
    setScPerm(overview.data.soundcloud_permalink || '')
  }, [overview.data])

  const releaseDetail = useQuery({
    queryKey: [
      'admin',
      'catalog',
      artistId,
      'release',
      selectedReleaseId,
    ],
    queryFn: () =>
      adminApi.catalogReleaseDetail(
        artistId,
        selectedReleaseId!,
      ),
    enabled: open && selectedReleaseId !== null,
  })

  useEffect(() => {
    if (!releaseDetail.data) {
      setPendingTrackIds(null)
      return
    }
    const ids = releaseDetail.data.tracks
      .slice()
      .sort((a, b) => a.position - b.position)
      .map((row) => row.track.id as number)
    setPendingTrackIds(ids)
  }, [releaseDetail.data])

  const trackHits = useQuery({
    queryKey: [
      'admin',
      'catalog',
      artistId,
      'trackSearch',
      trackSearch,
    ],
    queryFn: () =>
      adminApi.catalogSearchTracks(artistId, {
        search: trackSearch,
        page: 1,
        size: 20,
      }),
    enabled: open && trackSearch.trim().length >= 2,
  })

  const uploadAvatar = useMutation({
    mutationFn: (file: File) =>
      adminApi.catalogUploadAvatar(artistId, file),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
    },
  })

  const saveSc = useMutation({
    mutationFn: () => {
      let soundcloud_user_id: number | null | undefined
      if (scUser.trim() === '') {
        soundcloud_user_id = null
      } else {
        const n = Number.parseInt(scUser, 10)
        if (Number.isNaN(n)) {
          return Promise.reject(
            new Error(
              t('admin.artists.catalog.invalidScUserId'),
            ),
          )
        }
        soundcloud_user_id = n
      }
      return adminApi.catalogPatchSoundcloud(artistId, {
        soundcloud_user_id,
        soundcloud_permalink:
          scPerm.trim() === '' ? null : scPerm.trim(),
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
    },
  })

  const createRelease = useMutation({
    mutationFn: () =>
      adminApi.catalogCreateRelease(artistId, {
        title: newTitle.trim() || 'Untitled',
      }),
    onSuccess: () => {
      setNewTitle('')
      qc.invalidateQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
    },
  })

  const reorderMutation = useMutation({
    mutationFn: (ordered: number[]) =>
      adminApi.catalogReorderReleases(artistId, ordered),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
    },
  })

  const saveTracks = useMutation({
    mutationFn: (ids: number[]) =>
      adminApi.catalogSetReleaseTracks(
        artistId,
        selectedReleaseId!,
        ids,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: [
          'admin',
          'catalog',
          artistId,
          'release',
          selectedReleaseId,
        ],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
    },
  })

  const deleteRelease = useMutation({
    mutationFn: (rid: number) =>
      adminApi.catalogDeleteRelease(artistId, rid),
    onSuccess: () => {
      setSelectedReleaseId(null)
      qc.invalidateQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
    },
  })

  const patchRelease = useMutation({
    mutationFn: (args: {
      releaseId: number
      manual_lock: boolean
    }) =>
      adminApi.catalogPatchRelease(
        artistId,
        args.releaseId,
        {
          manual_lock: args.manual_lock,
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
      qc.invalidateQueries({
        queryKey: [
          'admin',
          'catalog',
          artistId,
          'release',
          selectedReleaseId,
        ],
      })
    },
  })

  const catalogSyncBusy =
    overview.data?.catalog_sync_state === 'running'

  const releasesOrdered: CatalogReleaseRow[] = useMemo(() => {
    const items = overview.data?.releases ?? []
    return items
      .slice()
      .sort(
        (a, b) =>
          a.display_position - b.display_position ||
          a.id - b.id,
      )
  }, [overview.data])

  const syncStatusBanner = useMemo(() => {
    const row = overview.data
    if (!row) return null
    const st = row.catalog_sync_state
    if (st === 'idle') return null
    const mode = row.catalog_sync_mode
    const modeLine =
      mode === 'release'
        ? t('admin.artists.catalog.syncModeRelease')
        : mode === 'full'
          ? t('admin.artists.catalog.syncModeFull')
          : null
    const err = row.catalog_sync_error
    const det = row.catalog_sync_detail as
      | Record<string, unknown>
      | null
      | undefined
    let detailLine: string | null = null
    if (st === 'success' && det) {
      if (typeof det.albums_synced === 'number') {
        const seen =
          typeof det.albums_seen === 'number'
            ? det.albums_seen
            : det.albums_synced
        detailLine = t('admin.artists.catalog.syncDetailFull', {
          synced: det.albums_synced,
          seen,
        })
      } else if (typeof det.soundcloud_album_id === 'number') {
        detailLine = t('admin.artists.catalog.syncDetailRelease', {
          id: det.soundcloud_album_id,
        })
      }
    }
    const updated = row.catalog_sync_updated_at
    const lines: string[] = []
    if (st === 'running') {
      lines.push(t('admin.artists.catalog.syncStateRunning'))
      if (modeLine) lines.push(modeLine)
      if (det && typeof det.phase === 'string') {
        if (det.phase === 'queued') {
          lines.push(t('admin.artists.catalog.syncProgressQueued'))
        } else if (det.phase === 'list_soundcloud_albums') {
          lines.push(
            t('admin.artists.catalog.syncProgressListAlbums'),
          )
        } else if (det.phase === 'albums') {
          const td = det.albums_total
          const dd = det.albums_done
          if (
            typeof td === 'number' &&
            typeof dd === 'number'
          ) {
            lines.push(
              t('admin.artists.catalog.syncProgressAlbums', {
                done: dd,
                total: td,
              }),
            )
          }
        } else if (det.phase === 'station_similar') {
          lines.push(
            t('admin.artists.catalog.syncProgressStation'),
          )
        } else if (det.phase === 'release') {
          const rid = det.soundcloud_album_id
          if (typeof rid === 'number') {
            lines.push(
              t('admin.artists.catalog.syncProgressRelease', {
                id: rid,
              }),
            )
          }
        }
      }
    } else if (st === 'success') {
      lines.push(t('admin.artists.catalog.syncStateSuccess'))
      if (modeLine) lines.push(modeLine)
      if (detailLine) lines.push(detailLine)
      if (det && det.station_synced === true) {
        lines.push(
          t('admin.artists.catalog.syncDetailStationOk'),
        )
      } else if (det && det.station_skipped_manual === true) {
        lines.push(
          t('admin.artists.catalog.syncDetailStationSkipped'),
        )
      }
    } else if (st === 'error') {
      lines.push(t('admin.artists.catalog.syncStateError'))
      if (err) lines.push(err)
    }
    if (updated) lines.push(updated)
    return { st, lines }
  }, [overview.data, t])

  async function onSyncFull() {
    const ok = await stepUp.request('catalog.sync.run')
    if (!ok) return
    try {
      await adminApi.catalogSyncFull(artistId)
      await qc.refetchQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
      await showAlert(
        t('admin.artists.catalog.syncQueued'),
      )
    } catch (e) {
      await showAlert(
        (e as Error).message ||
          t('admin.common.unknownError'),
      )
    }
  }

  async function onSyncRelease(rid: number) {
    const ok = await stepUp.request('catalog.sync.run')
    if (!ok) return
    try {
      await adminApi.catalogSyncRelease(artistId, rid)
      await qc.refetchQueries({
        queryKey: ['admin', 'catalog', artistId],
      })
      await showAlert(
        t('admin.artists.catalog.syncQueued'),
      )
    } catch (e) {
      await showAlert(
        (e as Error).message ||
          t('admin.common.unknownError'),
      )
    }
  }

  async function confirmDeleteRelease(rid: number) {
    const ok = await showConfirm(
      t('admin.artists.catalog.confirmDeleteRelease'),
      { danger: true },
    )
    if (!ok) return
    try {
      await deleteRelease.mutateAsync(rid)
    } catch (e) {
      await showAlert(
        (e as Error).message ||
          t('admin.common.unknownError'),
      )
    }
  }

  function moveRelease(from: number, dir: -1 | 1) {
    const ids = releasesOrdered.map((r) => r.id)
    const to = from + dir
    if (to < 0 || to >= ids.length) return
    reorderMutation.mutate(reorderIds(ids, from, to))
  }

  function moveTrack(from: number, dir: -1 | 1) {
    if (!pendingTrackIds) return
    const to = from + dir
    if (to < 0 || to >= pendingTrackIds.length) return
    setPendingTrackIds(
      reorderIds(pendingTrackIds, from, to),
    )
  }

  function onTrackDragStart(
    e: React.DragEvent,
    idx: number,
  ) {
    e.dataTransfer.setData('text/plain', String(idx))
    e.dataTransfer.effectAllowed = 'move'
  }

  function onTrackDragOver(e: React.DragEvent) {
    e.preventDefault()
  }

  function onTrackDrop(e: React.DragEvent, toIdx: number) {
    e.preventDefault()
    if (!pendingTrackIds) return
    const from = Number.parseInt(
      e.dataTransfer.getData('text/plain'),
      10,
    )
    if (Number.isNaN(from)) return
    setPendingTrackIds(
      reorderIds(pendingTrackIds, from, toIdx),
    )
  }

  function addTrackHit(id: number) {
    setPendingTrackIds((prev) => {
      const base = prev ?? []
      if (base.includes(id)) return base
      return [...base, id]
    })
  }

  const detail = releaseDetail.data
  const manualLocked = Boolean(detail?.manual_lock)

  return (
    <Sheet
      open={open}
      onClose={onClose}
      ariaLabel={t('admin.artists.catalog.sheetLabel')}
    >
      <div className="admin-catalog-editor">
        <h2>
          {t('admin.artists.catalog.title', {
            name: artistName,
          })}
        </h2>
        <p className="admin-auth-hint admin-mono">
          id={artistId}
        </p>
        {overview.error && (
          <div className="admin-error">
            {(overview.error as Error).message}
          </div>
        )}
        <section className="admin-catalog-section">
          <h3>{t('admin.artists.catalog.soundcloud')}</h3>
          <div className="admin-catalog-grid">
            <label>
              {t('admin.artists.catalog.scUserId')}
              <input
                value={scUser}
                onChange={(e) => setScUser(e.target.value)}
                inputMode="numeric"
              />
            </label>
            <label>
              {t('admin.artists.catalog.scPermalink')}
              <input
                value={scPerm}
                onChange={(e) => setScPerm(e.target.value)}
              />
            </label>
          </div>
          <Press
            variant="primary"
            disabled={saveSc.isPending}
            onClick={() => {
              saveSc.mutate(undefined, {
                onError: async (err) => {
                  await showAlert(
                    (err as Error).message ||
                      t('admin.common.unknownError'),
                  )
                },
              })
            }}
          >
            {t('admin.artists.catalog.saveSoundcloud')}
          </Press>
        </section>
        <section className="admin-catalog-section">
          <h3>{t('admin.artists.catalog.avatar')}</h3>
          <p className="admin-auth-hint">
            {t('admin.artists.catalog.avatarHint')}
          </p>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              flexWrap: 'wrap',
            }}
          >
            <CoverImage
              coverKey={overview.data?.image_key ?? null}
              size={72}
            />
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0]
                e.target.value = ''
                if (!f) return
                uploadAvatar.mutate(f, {
                  onError: async (err) => {
                    await showAlert(
                      (err as Error).message ||
                        t('admin.common.unknownError'),
                    )
                  },
                })
              }}
            />
            <Press
              variant="ghost"
              disabled={uploadAvatar.isPending}
              onClick={() => avatarInputRef.current?.click()}
            >
              {uploadAvatar.isPending
                ? t('admin.artists.catalog.avatarUploading')
                : t('admin.artists.catalog.avatarUpload')}
            </Press>
          </div>
        </section>
        <section className="admin-catalog-section">
          <h3>{t('admin.artists.catalog.sync')}</h3>
          {syncStatusBanner && (
            <div
              className={
                syncStatusBanner.st === 'error'
                  ? 'admin-error admin-catalog-sync-status'
                  : 'admin-catalog-sync-status'
              }
              data-state={syncStatusBanner.st}
            >
              {syncStatusBanner.lines.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
              {catalogSyncBusy && overview.isFetching && (
                <div className="admin-auth-hint">
                  {t('admin.artists.catalog.syncPolling')}
                </div>
              )}
            </div>
          )}
          <Press
            variant="ghost"
            disabled={catalogSyncBusy}
            onClick={() => void onSyncFull()}
          >
            {t('admin.artists.catalog.syncFull')}
          </Press>
        </section>
        <section className="admin-catalog-section">
          <h3>{t('admin.artists.catalog.releases')}</h3>
          <div className="admin-catalog-new">
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t(
                'admin.artists.catalog.newReleasePlaceholder',
              )}
            />
            <Press
              variant="ghost"
              disabled={
                createRelease.isPending || !newTitle.trim()
              }
              onClick={() => createRelease.mutate()}
            >
              {t('admin.artists.catalog.addRelease')}
            </Press>
          </div>
          <ul className="admin-catalog-release-list">
            {releasesOrdered.map((rel, idx) => (
              <li key={rel.id}>
                <button
                  type="button"
                  className={
                    selectedReleaseId === rel.id
                      ? 'admin-catalog-rel-selected'
                      : 'admin-catalog-rel'
                  }
                  onClick={() => setSelectedReleaseId(rel.id)}
                >
                  <span className="admin-mono">{rel.id}</span>{' '}
                  {rel.title}{' '}
                  <span className="admin-auth-hint">
                    ({rel.track_count})
                  </span>
                  {rel.soundcloud_album_id !== null && (
                    <span className="admin-tag">
                      SC
                    </span>
                  )}
                  {rel.manual_lock && (
                    <span className="admin-tag">
                      LOCK
                    </span>
                  )}
                </button>
                <div className="admin-catalog-rel-actions">
                  <Press
                    variant="ghost"
                    onClick={() => moveRelease(idx, -1)}
                  >
                    ↑
                  </Press>
                  <Press
                    variant="ghost"
                    onClick={() => moveRelease(idx, 1)}
                  >
                    ↓
                  </Press>
                  <Press
                    variant="ghost"
                    disabled={catalogSyncBusy}
                    onClick={() => void onSyncRelease(rel.id)}
                  >
                    {t('admin.artists.catalog.syncRelease')}
                  </Press>
                  <Press
                    variant="ghost"
                    onClick={() =>
                      void confirmDeleteRelease(rel.id)
                    }
                  >
                    {t('admin.artists.catalog.deleteRelease')}
                  </Press>
                </div>
              </li>
            ))}
          </ul>
        </section>
        {selectedReleaseId !== null &&
          releaseDetail.isSuccess &&
          detail && (
            <section className="admin-catalog-section">
              <h3>
                {t('admin.artists.catalog.releaseEditor')}
              </h3>
              <label className="admin-catalog-check">
                <input
                  type="checkbox"
                  checked={manualLocked}
                  onChange={(e) =>
                    patchRelease.mutate({
                      releaseId: selectedReleaseId,
                      manual_lock: e.target.checked,
                    })
                  }
                />
                {t('admin.artists.catalog.manualLock')}
              </label>
              {pendingTrackIds && (
                <>
                  <ul className="admin-catalog-track-list">
                    {pendingTrackIds.map((tid, tidx) => (
                      <li
                        key={`${tid}-${tidx}`}
                        draggable
                        onDragStart={(ev) =>
                          onTrackDragStart(ev, tidx)
                        }
                        onDragOver={onTrackDragOver}
                        onDrop={(ev) =>
                          onTrackDrop(ev, tidx)
                        }
                      >
                        <span className="admin-mono">
                          {tid}
                        </span>
                        <div className="admin-catalog-rel-actions">
                          <Press
                            variant="ghost"
                            onClick={() =>
                              moveTrack(tidx, -1)
                            }
                          >
                            ↑
                          </Press>
                          <Press
                            variant="ghost"
                            onClick={() => moveTrack(tidx, 1)}
                          >
                            ↓
                          </Press>
                          <Press
                            variant="ghost"
                            onClick={() =>
                              setPendingTrackIds((prev) =>
                                (prev ?? []).filter(
                                  (_, i) => i !== tidx,
                                ),
                              )
                            }
                          >
                            {t(
                              'admin.artists.catalog.removeTrack',
                            )}
                          </Press>
                        </div>
                      </li>
                    ))}
                  </ul>
                  <Press
                    variant="primary"
                    disabled={
                      saveTracks.isPending ||
                      pendingTrackIds.length === 0
                    }
                    onClick={() =>
                      saveTracks.mutate(pendingTrackIds)
                    }
                  >
                    {t(
                      'admin.artists.catalog.saveTrackOrder',
                    )}
                  </Press>
                </>
              )}
              <div className="admin-catalog-search">
                <input
                  value={trackSearch}
                  onChange={(e) =>
                    setTrackSearch(e.target.value)
                  }
                  placeholder={t(
                    'admin.artists.catalog.trackSearchPlaceholder',
                  )}
                />
                {trackHits.data && (
                  <ul className="admin-catalog-hits">
                    {trackHits.data.items.map((row) => {
                      const id = row.id as number
                      const title = String(row.title ?? '')
                      return (
                        <li key={id}>
                          <button
                            type="button"
                            className="admin-link"
                            onClick={() => addTrackHit(id)}
                          >
                            <span className="admin-mono">
                              {id}
                            </span>{' '}
                            {title}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            </section>
          )}
        {selectedReleaseId !== null && releaseDetail.isLoading && (
          <p className="admin-auth-hint">
            {t('admin.common.loading')}
          </p>
        )}
        <div className="admin-catalog-footer">
          <Press variant="ghost" onClick={onClose}>
            {t('admin.common.cancel')}
          </Press>
        </div>
      </div>
    </Sheet>
  )
}
