import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
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

  const overview = useQuery({
    queryKey: ['admin', 'catalog', artistId],
    queryFn: () => adminApi.catalogOverview(artistId),
    enabled: open,
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

  async function onSyncFull() {
    const ok = await stepUp.request('catalog.sync.run')
    if (!ok) return
    try {
      await adminApi.catalogSyncFull(artistId)
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
          <h3>{t('admin.artists.catalog.sync')}</h3>
          <Press variant="ghost" onClick={() => void onSyncFull()}>
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
