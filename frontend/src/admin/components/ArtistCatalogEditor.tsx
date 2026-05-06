import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { CoverImage } from '@/components/CoverImage/CoverImage'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
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
  cover_key: string | null
}

type WorkspaceTrackRow = {
  position: number
  track: Record<string, unknown>
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

function reorderWorkspaceRows(
  rows: WorkspaceTrackRow[],
  from: number,
  to: number,
): WorkspaceTrackRow[] {
  const ids = rows.map((r) => r.track.id as number)
  const newIds = reorderIds(ids, from, to)
  const byId = new Map(
    rows.map((r) => [r.track.id as number, r.track]),
  )
  return newIds.map((id, i) => ({
    position: i,
    track: byId.get(id)!,
  }))
}

function trackStr(t: Record<string, unknown>, key: string): string {
  const v = t[key]
  if (v === null || v === undefined) return ''
  return String(v)
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
  const [workspaceTracks, setWorkspaceTracks] = useState<
    WorkspaceTrackRow[] | null
  >(null)
  const [baselineTrackIds, setBaselineTrackIds] = useState<
    number[] | null
  >(null)
  const [releaseMeta, setReleaseMeta] = useState({
    title: '',
    release_kind: '',
    released_at: '',
  })
  const [releaseMetaDirty, setReleaseMetaDirty] = useState(false)
  const [discographyItems, setDiscographyItems] = useState<
    {
      title: string
      year: number | null
      type: string | null
      url: string | null
    }[]
  >([])
  const [discographyDirty, setDiscographyDirty] =
    useState(false)
  const [artistSettingsOpen, setArtistSettingsOpen] =
    useState(false)
  const [allTracksPage, setAllTracksPage] = useState(1)
  const avatarInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) setAllTracksPage(1)
  }, [artistId, open])
  const releaseCoverInputRef = useRef<HTMLInputElement>(null)

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

  const discographyQuery = useQuery({
    queryKey: ['admin', 'artist-discography', artistId],
    queryFn: () => adminApi.artistDiscography(artistId),
    enabled: open,
  })

  useEffect(() => {
    if (!discographyQuery.data) return
    setDiscographyItems(discographyQuery.data)
    setDiscographyDirty(false)
  }, [discographyQuery.data])

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

  const detail = releaseDetail.data

  useEffect(() => {
    if (!releaseDetail.data || selectedReleaseId === null) {
      setWorkspaceTracks(null)
      setBaselineTrackIds(null)
      return
    }
    const rows = releaseDetail.data.tracks
      .slice()
      .sort((a, b) => a.position - b.position)
      .map((row) => ({
        position: row.position,
        track: row.track,
      }))
    setWorkspaceTracks(rows)
    setBaselineTrackIds(
      rows.map((r) => r.track.id as number),
    )
  }, [releaseDetail.data, selectedReleaseId])

  useEffect(() => {
    if (!detail) {
      setReleaseMeta({
        title: '',
        release_kind: '',
        released_at: '',
      })
      setReleaseMetaDirty(false)
      return
    }
    const ra = detail.released_at
    setReleaseMeta({
      title: detail.title,
      release_kind: detail.release_kind ?? '',
      released_at:
        ra === null || ra === undefined
          ? ''
          : String(ra).slice(0, 10),
    })
    setReleaseMetaDirty(false)
  }, [
    detail?.id,
    detail?.title,
    detail?.release_kind,
    detail?.released_at,
  ])

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

  const allTracksByArtist = useQuery({
    queryKey: [
      'admin',
      'catalog',
      artistId,
      'allTracks',
      allTracksPage,
    ],
    queryFn: () =>
      adminApi.catalogSearchTracks(artistId, {
        page: allTracksPage,
        size: 50,
      }),
    enabled: open,
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
      qc.invalidateQueries({
        queryKey: [
          'admin',
          'catalog',
          artistId,
          'allTracks',
        ],
      })
    },
  })

  const saveDiscography = useMutation({
    mutationFn: () =>
      adminApi.artistDiscographySave(
        artistId,
        discographyItems,
      ),
    onSuccess: (data) => {
      setDiscographyItems(data)
      setDiscographyDirty(false)
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

  const saveReleaseMeta = useMutation({
    mutationFn: () =>
      adminApi.catalogPatchRelease(
        artistId,
        selectedReleaseId!,
        {
          title: releaseMeta.title.trim(),
          release_kind:
            releaseMeta.release_kind.trim() === ''
              ? null
              : releaseMeta.release_kind.trim(),
          released_at:
            releaseMeta.released_at.trim() === ''
              ? null
              : releaseMeta.released_at.trim(),
        },
      ),
    onSuccess: () => {
      setReleaseMetaDirty(false)
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

  const uploadReleaseCover = useMutation({
    mutationFn: (file: File) =>
      adminApi.catalogUploadReleaseCover(
        artistId,
        selectedReleaseId!,
        file,
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

  const saveTrackRow = useMutation({
    mutationFn: (args: {
      trackId: number
      title: string
      artist: string
      description: string
    }) =>
      adminApi.updateTrackMetadata(args.trackId, {
        title: args.title.trim(),
        artist:
          args.artist.trim() === '' ? null : args.artist.trim(),
        description:
          args.description.trim() === ''
            ? null
            : args.description.trim(),
      }),
    onSuccess: (_data, args) => {
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
        queryKey: [
          'admin',
          'catalog',
          artistId,
          'allTracks',
        ],
      })
      setWorkspaceTracks((prev) => {
        if (!prev) return prev
        return prev.map((row) => {
          if ((row.track.id as number) !== args.trackId) {
            return row
          }
          return {
            ...row,
            track: {
              ...row.track,
              title: args.title.trim(),
              artist:
                args.artist.trim() === ''
                  ? null
                  : args.artist.trim(),
              description:
                args.description.trim() === ''
                  ? null
                  : args.description.trim(),
            },
          }
        })
      })
    },
  })

  const uploadTrackCoverMut = useMutation({
    mutationFn: (args: { trackId: number; file: File }) =>
      adminApi.uploadTrackCover(args.trackId, args.file),
    onSuccess: (data) => {
      const id = data.id as number
      const ck = data.cover_key as string | null | undefined
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
        queryKey: [
          'admin',
          'catalog',
          artistId,
          'allTracks',
        ],
      })
      setWorkspaceTracks((prev) => {
        if (!prev) return prev
        return prev.map((row) => {
          if ((row.track.id as number) !== id) return row
          return {
            ...row,
            track: { ...row.track, cover_key: ck ?? null },
          }
        })
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

  const currentTrackIds = useMemo(() => {
    if (!workspaceTracks) return []
    return workspaceTracks.map((r) => r.track.id as number)
  }, [workspaceTracks])

  const trackOrderDirty = useMemo(() => {
    if (!baselineTrackIds || !workspaceTracks) return false
    if (baselineTrackIds.length !== workspaceTracks.length) {
      return true
    }
    return currentTrackIds.some(
      (id, i) => id !== baselineTrackIds[i],
    )
  }, [baselineTrackIds, workspaceTracks, currentTrackIds])

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

  function moveTrackRow(from: number, dir: -1 | 1) {
    setWorkspaceTracks((prev) => {
      if (!prev) return prev
      const to = from + dir
      if (to < 0 || to >= prev.length) return prev
      return reorderWorkspaceRows(prev, from, to)
    })
  }

  function onTrackDragStart(e: DragEvent, idx: number) {
    e.dataTransfer.setData('text/plain', String(idx))
    e.dataTransfer.effectAllowed = 'move'
  }

  function onTrackDragOver(e: DragEvent) {
    e.preventDefault()
  }

  function onTrackDrop(e: DragEvent, toIdx: number) {
    e.preventDefault()
    const from = Number.parseInt(
      e.dataTransfer.getData('text/plain'),
      10,
    )
    if (Number.isNaN(from)) return
    setWorkspaceTracks((prev) => {
      if (!prev) return prev
      return reorderWorkspaceRows(prev, from, toIdx)
    })
  }

  function addTrackHit(hit: Record<string, unknown>) {
    const id = hit.id as number
    setWorkspaceTracks((prev) => {
      const base = prev ?? []
      if (base.some((r) => (r.track.id as number) === id)) {
        return base
      }
      return [...base, { position: base.length, track: hit }]
    })
  }

  function updateWorkspaceTrackField(
    index: number,
    field: 'title' | 'artist' | 'description',
    value: string,
  ) {
    setWorkspaceTracks((prev) => {
      if (!prev) return prev
      const next = [...prev]
      const row = next[index]
      next[index] = {
        ...row,
        track: { ...row.track, [field]: value },
      }
      return next
    })
  }

  function removeTrackAt(index: number) {
    setWorkspaceTracks((prev) => {
      if (!prev) return prev
      return prev.filter((_, i) => i !== index)
    })
  }

  const manualLocked = Boolean(detail?.manual_lock)
  const allTotal = allTracksByArtist.data?.total ?? 0
  const allPages = Math.max(
    1,
    Math.ceil(allTotal / 50),
  )

  return (
    <Sheet
      open={open}
      onClose={onClose}
      ariaLabel={t('admin.artists.catalog.sheetLabel')}
    >
      <div className="admin-catalog-editor admin-catalog-editor--wide">
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

        <details
          className="admin-catalog-details"
          open={artistSettingsOpen}
          onToggle={(e) =>
            setArtistSettingsOpen(
              (e.target as HTMLDetailsElement).open,
            )
          }
        >
          <summary>
            {t('admin.artists.catalog.artistSettingsToggle')}
          </summary>
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
            <MotionPress
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
            </MotionPress>
          </section>
          <section className="admin-catalog-section">
            <h3>{t('admin.artists.catalog.avatar')}</h3>
            <p className="admin-auth-hint">
              {t('admin.artists.catalog.avatarHint')}
            </p>
            <div className="admin-catalog-avatar-row">
              <CoverImage
                coverKey={overview.data?.image_key ?? null}
                size={72}
              />
              <input
                ref={avatarInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="admin-catalog-hidden-input"
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
              <MotionPress
                variant="ghost"
                disabled={uploadAvatar.isPending}
                onClick={() => avatarInputRef.current?.click()}
              >
                {uploadAvatar.isPending
                  ? t('admin.artists.catalog.avatarUploading')
                  : t('admin.artists.catalog.avatarUpload')}
              </MotionPress>
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
            <MotionPress
              variant="ghost"
              disabled={catalogSyncBusy}
              onClick={() => void onSyncFull()}
            >
              {t('admin.artists.catalog.syncFull')}
            </MotionPress>
          </section>
        </details>

        <section className="admin-catalog-section admin-catalog-section--primary">
          <h3>{t('admin.artists.catalog.releases')}</h3>
          <div className="admin-catalog-new">
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t(
                'admin.artists.catalog.newReleasePlaceholder',
              )}
            />
            <MotionPress
              variant="ghost"
              disabled={
                createRelease.isPending || !newTitle.trim()
              }
              onClick={() => createRelease.mutate()}
            >
              {t('admin.artists.catalog.addRelease')}
            </MotionPress>
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
                  <span className="admin-catalog-rel-cover">
                    <CoverImage
                      coverKey={rel.cover_key ?? null}
                      size={40}
                    />
                  </span>
                  <span className="admin-catalog-rel-text">
                    <span className="admin-mono">{rel.id}</span>{' '}
                    {rel.title}{' '}
                    <span className="admin-auth-hint">
                      ({rel.track_count})
                    </span>
                    {rel.soundcloud_album_id !== null && (
                      <span className="admin-tag">SC</span>
                    )}
                    {rel.manual_lock && (
                      <span className="admin-tag">LOCK</span>
                    )}
                  </span>
                </button>
                <div className="admin-catalog-rel-actions">
                  <MotionPress
                    variant="ghost"
                    aria-label={t(
                      'admin.artists.catalog.moveUp',
                    )}
                    onClick={() => moveRelease(idx, -1)}
                  >
                    <Icon name="chevron-up" size={18} />
                  </MotionPress>
                  <MotionPress
                    variant="ghost"
                    aria-label={t(
                      'admin.artists.catalog.moveDown',
                    )}
                    onClick={() => moveRelease(idx, 1)}
                  >
                    <Icon name="chevron-down" size={18} />
                  </MotionPress>
                  <MotionPress
                    variant="ghost"
                    disabled={catalogSyncBusy}
                    onClick={() => void onSyncRelease(rel.id)}
                  >
                    {t('admin.artists.catalog.syncRelease')}
                  </MotionPress>
                  <MotionPress
                    variant="ghost"
                    onClick={() =>
                      void confirmDeleteRelease(rel.id)
                    }
                  >
                    {t('admin.artists.catalog.deleteRelease')}
                  </MotionPress>
                </div>
              </li>
            ))}
          </ul>
        </section>

        {selectedReleaseId !== null && releaseDetail.isLoading && (
          <p className="admin-auth-hint">
            {t('admin.common.loading')}
          </p>
        )}

        {selectedReleaseId !== null &&
          releaseDetail.isSuccess &&
          detail &&
          workspaceTracks && (
            <section className="admin-catalog-section admin-catalog-workspace">
              <h3>
                {t('admin.artists.catalog.releaseEditor')}
              </h3>

              <div className="admin-catalog-release-meta">
                <div className="admin-catalog-release-cover-col">
                  <CoverImage
                    coverKey={detail.cover_key ?? null}
                    size={96}
                  />
                  <input
                    ref={releaseCoverInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="admin-catalog-hidden-input"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      e.target.value = ''
                      if (!f) return
                      uploadReleaseCover.mutate(f, {
                        onError: async (err) => {
                          await showAlert(
                            (err as Error).message ||
                              t('admin.common.unknownError'),
                          )
                        },
                      })
                    }}
                  />
                  <MotionPress
                    variant="ghost"
                    disabled={uploadReleaseCover.isPending}
                    onClick={() =>
                      releaseCoverInputRef.current?.click()
                    }
                  >
                    {uploadReleaseCover.isPending
                      ? t(
                          'admin.artists.catalog.coverUploading',
                        )
                      : t(
                          'admin.artists.catalog.releaseCoverUpload',
                        )}
                  </MotionPress>
                </div>
                <div className="admin-catalog-release-fields">
                  <label>
                    {t('admin.artists.catalog.fieldTitle')}
                    <input
                      value={releaseMeta.title}
                      onChange={(e) => {
                        setReleaseMeta((m) => ({
                          ...m,
                          title: e.target.value,
                        }))
                        setReleaseMetaDirty(true)
                      }}
                    />
                  </label>
                  <label>
                    {t('admin.artists.catalog.fieldKind')}
                    <input
                      value={releaseMeta.release_kind}
                      onChange={(e) => {
                        setReleaseMeta((m) => ({
                          ...m,
                          release_kind: e.target.value,
                        }))
                        setReleaseMetaDirty(true)
                      }}
                      placeholder={t(
                        'admin.artists.catalog.fieldKindPh',
                      )}
                    />
                  </label>
                  <label>
                    {t('admin.artists.catalog.fieldReleased')}
                    <input
                      type="date"
                      value={releaseMeta.released_at}
                      onChange={(e) => {
                        setReleaseMeta((m) => ({
                          ...m,
                          released_at: e.target.value,
                        }))
                        setReleaseMetaDirty(true)
                      }}
                    />
                  </label>
                  <MotionPress
                    variant="primary"
                    disabled={
                      !releaseMeta.title.trim() ||
                      !releaseMetaDirty ||
                      saveReleaseMeta.isPending
                    }
                    onClick={() =>
                      saveReleaseMeta.mutate(undefined, {
                        onError: async (err) => {
                          await showAlert(
                            (err as Error).message ||
                              t('admin.common.unknownError'),
                          )
                        },
                      })
                    }
                  >
                    {t('admin.artists.catalog.saveReleaseMeta')}
                  </MotionPress>
                </div>
              </div>

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

              <p className="admin-auth-hint admin-catalog-tracks-hint">
                {t('admin.artists.catalog.tracksHint')}
              </p>
              <ul className="admin-catalog-track-cards">
                {workspaceTracks.map((row, tidx) => {
                  const tr = row.track
                  const tid = tr.id as number
                  return (
                    <li
                      key={`${tid}-${tidx}`}
                      draggable
                      onDragStart={(ev) =>
                        onTrackDragStart(ev, tidx)
                      }
                      onDragOver={onTrackDragOver}
                      onDrop={(ev) => onTrackDrop(ev, tidx)}
                    >
                      <div className="admin-catalog-track-card-head">
                        <CoverImage
                          coverKey={
                            (tr.cover_key as string | null) ??
                            null
                          }
                          size={48}
                        />
                        <span className="admin-mono">
                          {tid}
                        </span>
                        <div className="admin-catalog-rel-actions">
                          <MotionPress
                            variant="ghost"
                            aria-label={t(
                              'admin.artists.catalog.moveUp',
                            )}
                            onClick={() =>
                              moveTrackRow(tidx, -1)
                            }
                          >
                            <Icon name="chevron-up" size={18} />
                          </MotionPress>
                          <MotionPress
                            variant="ghost"
                            aria-label={t(
                              'admin.artists.catalog.moveDown',
                            )}
                            onClick={() =>
                              moveTrackRow(tidx, 1)
                            }
                          >
                            <Icon
                              name="chevron-down"
                              size={18}
                            />
                          </MotionPress>
                          <MotionPress
                            variant="ghost"
                            onClick={() =>
                              removeTrackAt(tidx)
                            }
                          >
                            {t(
                              'admin.artists.catalog.removeTrack',
                            )}
                          </MotionPress>
                        </div>
                      </div>
                      <div className="admin-catalog-track-fields">
                        <label>
                          {t(
                            'admin.artists.catalog.trackTitle',
                          )}
                          <input
                            value={trackStr(tr, 'title')}
                            onChange={(e) =>
                              updateWorkspaceTrackField(
                                tidx,
                                'title',
                                e.target.value,
                              )
                            }
                          />
                        </label>
                        <label>
                          {t(
                            'admin.artists.catalog.trackArtist',
                          )}
                          <input
                            value={trackStr(tr, 'artist')}
                            onChange={(e) =>
                              updateWorkspaceTrackField(
                                tidx,
                                'artist',
                                e.target.value,
                              )
                            }
                          />
                        </label>
                        <label>
                          {t(
                            'admin.artists.catalog.trackDescription',
                          )}
                          <textarea
                            rows={2}
                            value={trackStr(
                              tr,
                              'description',
                            )}
                            onChange={(e) =>
                              updateWorkspaceTrackField(
                                tidx,
                                'description',
                                e.target.value,
                              )
                            }
                          />
                        </label>
                        <div className="admin-catalog-track-row-actions">
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            className="admin-catalog-hidden-input"
                            id={`track-cover-${tid}`}
                            onChange={(e) => {
                              const f = e.target.files?.[0]
                              e.target.value = ''
                              if (!f) return
                              uploadTrackCoverMut.mutate(
                                { trackId: tid, file: f },
                                {
                                  onError: async (err) => {
                                    await showAlert(
                                      (err as Error)
                                        .message ||
                                        t(
                                          'admin.common.unknownError',
                                        ),
                                    )
                                  },
                                },
                              )
                            }}
                          />
                          <MotionPress
                            variant="ghost"
                            disabled={
                              uploadTrackCoverMut.isPending
                            }
                            onClick={() =>
                              document
                                .getElementById(
                                  `track-cover-${tid}`,
                                )
                                ?.click()
                            }
                          >
                            {t(
                              'admin.artists.catalog.trackCoverUpload',
                            )}
                          </MotionPress>
                          <MotionPress
                            variant="primary"
                            disabled={
                              saveTrackRow.isPending
                            }
                            onClick={() =>
                              saveTrackRow.mutate(
                                {
                                  trackId: tid,
                                  title: trackStr(
                                    tr,
                                    'title',
                                  ),
                                  artist: trackStr(
                                    tr,
                                    'artist',
                                  ),
                                  description: trackStr(
                                    tr,
                                    'description',
                                  ),
                                },
                                {
                                  onError: async (err) => {
                                    await showAlert(
                                      (err as Error)
                                        .message ||
                                        t(
                                          'admin.common.unknownError',
                                        ),
                                    )
                                  },
                                },
                              )
                            }
                          >
                            {t(
                              'admin.artists.catalog.saveTrackMeta',
                            )}
                          </MotionPress>
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ul>
              <MotionPress
                variant="primary"
                disabled={
                  saveTracks.isPending ||
                  !trackOrderDirty ||
                  currentTrackIds.length === 0
                }
                onClick={() =>
                  saveTracks.mutate(currentTrackIds)
                }
              >
                {t('admin.artists.catalog.saveTrackOrder')}
              </MotionPress>

              <div className="admin-catalog-search">
                <h4 className="admin-catalog-subhead">
                  {t('admin.artists.catalog.addTracksTitle')}
                </h4>
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
                    {trackHits.data.items.map((hit) => {
                      const id = hit.id as number
                      const title = String(hit.title ?? '')
                      return (
                        <li key={id}>
                          <button
                            type="button"
                            className="admin-link"
                            onClick={() => addTrackHit(hit)}
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

        <section className="admin-catalog-section">
          <h3>{t('admin.artists.catalog.allTracksTitle')}</h3>
          <p className="admin-auth-hint">
            {t('admin.artists.catalog.allTracksHint')}
          </p>
          {allTracksByArtist.isLoading && (
            <p className="admin-auth-hint">
              {t('admin.common.loading')}
            </p>
          )}
          {allTracksByArtist.data && (
            <>
              <ul className="admin-catalog-all-tracks">
                {allTracksByArtist.data.items.map(
                  (tr) => {
                    const id = tr.id as number
                    const title = String(tr.title ?? '')
                    const ck = tr.cover_key as
                      | string
                      | null
                      | undefined
                    return (
                      <li key={id}>
                        <CoverImage
                          coverKey={ck ?? null}
                          size={36}
                        />
                        <span className="admin-mono">
                          {id}
                        </span>
                        <span>{title}</span>
                      </li>
                    )
                  },
                )}
              </ul>
              <div className="admin-catalog-pagination">
                <MotionPress
                  variant="ghost"
                  disabled={allTracksPage <= 1}
                  onClick={() =>
                    setAllTracksPage((p) =>
                      Math.max(1, p - 1),
                    )
                  }
                >
                  {t('admin.common.prev')}
                </MotionPress>
                <span>
                  {allTracksPage} / {allPages} ·{' '}
                  {t('admin.common.total', {
                    count: allTotal,
                  })}
                </span>
                <MotionPress
                  variant="ghost"
                  disabled={allTracksPage >= allPages}
                  onClick={() =>
                    setAllTracksPage((p) => p + 1)
                  }
                >
                  {t('admin.common.next')}
                </MotionPress>
              </div>
            </>
          )}
        </section>

        <section className="admin-catalog-section">
          <h3>{t('admin.artists.catalog.discographyTitle')}</h3>
          <p className="admin-auth-hint">
            {t('admin.artists.catalog.discographyHint')}
          </p>
          {discographyQuery.isLoading && (
            <p className="admin-auth-hint">
              {t('admin.common.loading')}
            </p>
          )}
          {!discographyQuery.isLoading && (
            <div className="admin-catalog-discography">
              <table>
                <thead>
                  <tr>
                    <th>
                      {t(
                        'admin.artists.catalog.discographyTitleCol',
                      )}
                    </th>
                    <th>
                      {t(
                        'admin.artists.catalog.discographyYearCol',
                      )}
                    </th>
                    <th>
                      {t(
                        'admin.artists.catalog.discographyTypeCol',
                      )}
                    </th>
                    <th>
                      {t(
                        'admin.artists.catalog.discographyUrlCol',
                      )}
                    </th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {discographyItems.map((row, idx) => (
                    <tr key={`${row.title}-${idx}`}>
                      <td>
                        <input
                          value={row.title}
                          onChange={(e) => {
                            const next = [...discographyItems]
                            next[idx] = {
                              ...next[idx],
                              title: e.target.value,
                            }
                            setDiscographyItems(next)
                            setDiscographyDirty(true)
                          }}
                        />
                      </td>
                      <td>
                        <input
                          value={
                            row.year === null
                              ? ''
                              : String(row.year)
                          }
                          onChange={(e) => {
                            const v = e.target.value.trim()
                            const next = [...discographyItems]
                            next[idx] = {
                              ...next[idx],
                              year:
                                v === ''
                                  ? null
                                  : Number.parseInt(
                                      v,
                                      10,
                                    ) || null,
                            }
                            setDiscographyItems(next)
                            setDiscographyDirty(true)
                          }}
                          inputMode="numeric"
                        />
                      </td>
                      <td>
                        <input
                          value={row.type ?? ''}
                          onChange={(e) => {
                            const next = [...discographyItems]
                            const v = e.target.value.trim()
                            next[idx] = {
                              ...next[idx],
                              type: v === '' ? null : v,
                            }
                            setDiscographyItems(next)
                            setDiscographyDirty(true)
                          }}
                        />
                      </td>
                      <td>
                        <input
                          value={row.url ?? ''}
                          onChange={(e) => {
                            const next = [...discographyItems]
                            const v = e.target.value.trim()
                            next[idx] = {
                              ...next[idx],
                              url: v === '' ? null : v,
                            }
                            setDiscographyItems(next)
                            setDiscographyDirty(true)
                          }}
                        />
                      </td>
                      <td>
                        <MotionPress
                          variant="ghost"
                          onClick={() => {
                            setDiscographyItems((prev) =>
                              prev.filter((_, i) => i !== idx),
                            )
                            setDiscographyDirty(true)
                          }}
                        >
                          {t(
                            'admin.artists.catalog.discographyRemoveRow',
                          )}
                        </MotionPress>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="admin-catalog-discography-actions">
                <MotionPress
                  variant="ghost"
                  onClick={() => {
                    setDiscographyItems((prev) => [
                      ...prev,
                      {
                        title: '',
                        year: null,
                        type: null,
                        url: null,
                      },
                    ])
                    setDiscographyDirty(true)
                  }}
                >
                  {t(
                    'admin.artists.catalog.discographyAddRow',
                  )}
                </MotionPress>
                <MotionPress
                  variant="primary"
                  disabled={
                    !discographyDirty ||
                    saveDiscography.isPending
                  }
                  onClick={() =>
                    saveDiscography.mutate(undefined, {
                      onError: async (err) => {
                        await showAlert(
                          (err as Error).message ||
                            t('admin.common.unknownError'),
                        )
                      },
                    })
                  }
                >
                  {t(
                    'admin.artists.catalog.discographySave',
                  )}
                </MotionPress>
              </div>
            </div>
          )}
        </section>

        <div className="admin-catalog-footer">
          <MotionPress variant="ghost" onClick={onClose}>
            {t('admin.common.cancel')}
          </MotionPress>
        </div>
      </div>
    </Sheet>
  )
}
