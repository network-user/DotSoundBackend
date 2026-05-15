import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { AdminRangeSwitch } from '../components/widgets/AdminRangeSwitch'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { trackProgressiveAudioUrl } from '@/lib/offlineCache'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { KpiCard } from '../components/widgets/KpiCard'
import { Sparkline } from '../components/charts/Sparkline'
import { LineChart } from '../components/charts/LineChart'
import { OverflowMenu } from '../components/widgets/OverflowMenu'
import { FormModal } from '../components/widgets/FormModal'
import { BulkPageSelector } from '../components/widgets/BulkPageSelector'

interface TrackRow {
  id: number
  title: string
  artist: string | null
  source: string | null
  genre?: string | null
  is_active: boolean
  uploaded_by_id: number | null
  created_at: string
  access_mode?: string
  source_platform?: string | null
  sc_url?: string | null
  source_url?: string | null
  canonical_source_url?: string | null
  playback_last_failure_at?: string | null
  playback_last_http_status?: number | null
  playback_last_failure_source?: string | null
  playback_last_error_code?: string | null
  playback_last_error_reason?: string | null
  playback_last_error_stage?: string | null
  playback_last_upstream_status?: number | null
  playback_last_attempted_protocols?: string[]
  playback_recovery_failed_at?: string | null
  playback_suppressed_until?: string | null
}

interface ContextState {
  trackId: number
  content: string | null
  status: string
}

interface PromptState {
  prompt: string
  lang: string
}

interface ModalsState {
  prompt: PromptState | null
  context: ContextState | null
  batchPrompt: string | null
  batchLyrics: string | null
  batchGenreMood: string | null
  import: boolean
  gmImport: boolean
  sourceEdit: TrackRow | null
}

const initialModals: ModalsState = {
  prompt: null,
  context: null,
  batchPrompt: null,
  batchLyrics: null,
  batchGenreMood: null,
  import: false,
  gmImport: false,
  sourceEdit: null,
}

const PAGE_SIZE = 25
const REPAIR_BULK_BATCH_SIZE = 5000

function playbackDiagnosticParts(row: TrackRow): string[] {
  const parts: string[] = []
  if (row.playback_last_error_code) {
    parts.push(row.playback_last_error_code)
  }
  if (
    row.playback_last_error_reason &&
    row.playback_last_error_reason !== row.playback_last_error_code
  ) {
    parts.push(row.playback_last_error_reason)
  }
  if (row.playback_last_error_stage) {
    parts.push(`stage ${row.playback_last_error_stage}`)
  }
  if (typeof row.playback_last_upstream_status === 'number') {
    parts.push(`upstream ${row.playback_last_upstream_status}`)
  }
  const protocols = row.playback_last_attempted_protocols ?? []
  if (protocols.length > 0) {
    parts.push(protocols.join('+'))
  }
  return parts
}

type ModalsAction =
  | { type: 'set'; key: keyof ModalsState; value: ModalsState[keyof ModalsState] }
  | { type: 'closeAll' }

type TrackIdScope =
  | 'all'
  | 'playback_failures'
  | 'playback_suppressed'
  | 'deleted'

type PlaybackRepairBulkResult = Awaited<
  ReturnType<typeof adminApi.repairTracksPlayback>
>

function modalsReducer(
  state: ModalsState,
  action: ModalsAction,
): ModalsState {
  if (action.type === 'closeAll') return initialModals
  return { ...state, [action.key]: action.value }
}

export function TracksRoute() {
  const { t } = useTranslation()
  const { showConfirm, showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [withoutLyricsOnly, setWithoutLyricsOnly] = useState(false)
  const [listView, setListView] = useState<
    'all' | 'playback_failures' | 'playback_suppressed' | 'deleted'
  >('all')
  const [playingId, setPlayingId] = useState<number | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [bulkRepairBusy, setBulkRepairBusy] = useState(false)
  const [statsPeriod, setStatsPeriod] = useState<
    'today' | '7d' | '30d' | 'all'
  >('7d')

  // context feature state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [modals, modalsDispatch] = useReducer(
    modalsReducer,
    initialModals,
  )
  const promptModal = modals.prompt
  const contextModal = modals.context
  const batchPromptModal = modals.batchPrompt
  const batchLyricsPromptModal = modals.batchLyrics
  const batchGenreMoodPromptModal = modals.batchGenreMood
  const importModal = modals.import
  const gmImportModal = modals.gmImport
  const sourceEditModal = modals.sourceEdit
  const setPromptModal = useCallback(
    (v: PromptState | null) =>
      modalsDispatch({ type: 'set', key: 'prompt', value: v }),
    [],
  )
  const setContextModal = useCallback(
    (v: ContextState | null) =>
      modalsDispatch({ type: 'set', key: 'context', value: v }),
    [],
  )
  const setBatchPromptModal = useCallback(
    (v: string | null) =>
      modalsDispatch({ type: 'set', key: 'batchPrompt', value: v }),
    [],
  )
  const setBatchLyricsPromptModal = useCallback(
    (v: string | null) =>
      modalsDispatch({ type: 'set', key: 'batchLyrics', value: v }),
    [],
  )
  const setBatchGenreMoodPromptModal = useCallback(
    (v: string | null) =>
      modalsDispatch({ type: 'set', key: 'batchGenreMood', value: v }),
    [],
  )
  const setImportModal = useCallback(
    (v: boolean) =>
      modalsDispatch({ type: 'set', key: 'import', value: v }),
    [],
  )
  const setGmImportModal = useCallback(
    (v: boolean) =>
      modalsDispatch({ type: 'set', key: 'gmImport', value: v }),
    [],
  )
  const setSourceEditModal = useCallback(
    (v: TrackRow | null) =>
      modalsDispatch({ type: 'set', key: 'sourceEdit', value: v }),
    [],
  )
  const [contextEditValue, setContextEditValue] = useState('')
  const [busyContext, setBusyContext] = useState(false)
  const [importText, setImportText] = useState('')
  const [importResult, setImportResult] = useState<{
    imported: number
    errors: string[]
  } | null>(null)
  const [gmImportText, setGmImportText] = useState('')
  const [gmOverwriteGenre, setGmOverwriteGenre] = useState(false)
  const [gmImportResult, setGmImportResult] = useState<{
    imported: number
    errors: string[]
  } | null>(null)
  const [sourceForm, setSourceForm] = useState({
    sc: '',
    src: '',
    can: '',
  })
  const [sourceBusy, setSourceBusy] = useState(false)

  const contextTextareaRef = useRef<HTMLTextAreaElement>(null)

  const fetchTrackPage = (targetPage: number) => {
    const base = {
      page: targetPage,
      size: PAGE_SIZE,
      search: search || undefined,
    }
    if (listView === 'playback_failures') {
      return adminApi.listTracksPlaybackUnavailable(base)
    }
    if (listView === 'playback_suppressed') {
      return adminApi.listTracksPlaybackSuppressed(base)
    }
    if (listView === 'deleted') {
      return adminApi.listDeletedTracks(base)
    }
    return adminApi.listTracks({
      ...base,
      without_lyrics: withoutLyricsOnly || undefined,
    })
  }

  const { data, isFetching } = useQuery({
    queryKey: [
      'admin',
      'tracks',
      page,
      search,
      withoutLyricsOnly,
      listView,
    ],
    queryFn: () => fetchTrackPage(page),
    placeholderData: keepPreviousData,
  })
  const trackStats = useQuery({
    queryKey: ['admin', 'tracks', 'stats', statsPeriod],
    queryFn: () => adminApi.dashboardTrackStats(statsPeriod),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const total = data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rows = (data?.items || []) as unknown as TrackRow[]
  const visibleCount = rows.filter((r) => r.is_active).length
  const withGenreCount = rows.filter((r) => !!r.genre).length
  const sparkline = useMemo(() => {
    const buckets = new Map<string, number>()
    for (const row of rows) {
      const day = new Date(row.created_at)
        .toISOString()
        .slice(0, 10)
      buckets.set(day, (buckets.get(day) || 0) + 1)
    }
    return Array.from(buckets.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, value]) => value)
  }, [rows])

  useEffect(() => {
    setSelectedIds(new Set())
  }, [search, withoutLyricsOnly, listView])

  useEffect(() => {
    if (!sourceEditModal) return
    setSourceForm({
      sc: sourceEditModal.sc_url ?? '',
      src: sourceEditModal.source_url ?? '',
      can: sourceEditModal.canonical_source_url ?? '',
    })
  }, [sourceEditModal])

  const refresh = () =>
    qc.invalidateQueries({ queryKey: ['admin', 'tracks'] })

  const handleDelete = async (id: number, title: string) => {
    const ok = await showConfirm(
      t('admin.tracks.confirmDelete', { id, title }),
      { danger: true },
    )
    if (!ok) return
    setBusyId(id)
    try {
      await adminApi.deleteTrack(id)
      refresh()
    } catch (err) {
      await showAlert(
        t('admin.tracks.deleteFailed', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusyId(null)
    }
  }

  const handleRestoreDeleted = async (id: number) => {
    setBusyId(id)
    try {
      await adminApi.restoreTrack(id)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleHardDeleteForever = async (
    id: number,
    title: string,
  ) => {
    const ok = await showConfirm(
      t(
        'admin.tracks.confirmHardDelete',
        t('admin.tracks.confirmDeleteHard'),
        { id, title },
      ),
      { danger: true },
    )
    if (!ok) return
    setBusyId(id)
    try {
      await adminApi.hardDeleteTrackForever(id)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleClearPlaybackSuppression = async (id: number) => {
    setBusyId(id)
    try {
      await adminApi.clearTrackPlaybackSuppression(id)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleVerifyPlayback = async (id: number) => {
    setBusyId(id)
    try {
      const r = await adminApi.verifyTrackPlayback(id)
      const lines = [
        r.ok ? 'OK' : 'FAIL',
        r.detail || '',
        r.http_status != null ? `HTTP ${r.http_status}` : '',
        r.effective_track_id != null
          ? `effective_track_id=${r.effective_track_id}`
          : '',
        r.stream_protocol
          ? `protocol=${r.stream_protocol}`
          : '',
      ].filter(Boolean)
      await showAlert(lines.join('\n'))
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleRepairPlayback = async (id: number) => {
    setBusyId(id)
    try {
      const r = await adminApi.repairTrackPlayback(id)
      const lines = [
        r.queued ? t('admin.tracks.repairQueued') : r.detail,
        r.job_id ? `job_id=${r.job_id}` : '',
      ].filter(Boolean)
      await showAlert(lines.join('\n'))
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const repairTrackIds = async (
    trackIds: number[],
  ): Promise<PlaybackRepairBulkResult> => {
    const aggregate: PlaybackRepairBulkResult = {
      requested: 0,
      queued: 0,
      skipped: 0,
      missing: 0,
      job_ids: [],
      detail: '',
    }
    for (
      let offset = 0;
      offset < trackIds.length;
      offset += REPAIR_BULK_BATCH_SIZE
    ) {
      const batch = trackIds.slice(offset, offset + REPAIR_BULK_BATCH_SIZE)
      const result = await adminApi.repairTracksPlayback(batch)
      aggregate.requested += result.requested
      aggregate.queued += result.queued
      aggregate.skipped += result.skipped
      aggregate.missing += result.missing
      aggregate.job_ids.push(...result.job_ids)
    }
    aggregate.detail = (
      `queued=${aggregate.queued}, skipped=${aggregate.skipped}, ` +
      `missing=${aggregate.missing}`
    )
    return aggregate
  }

  const showRepairBulkResult = async (
    result: PlaybackRepairBulkResult,
  ) => {
    await showAlert(
      t('admin.tracks.repairBulkQueued', {
        queued: result.queued,
        skipped: result.skipped,
        missing: result.missing,
      }),
    )
  }

  const handleRepairSelectedPlayback = async () => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0 || bulkRepairBusy) return
    setBulkRepairBusy(true)
    try {
      const r = await repairTrackIds(ids)
      await showRepairBulkResult(r)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBulkRepairBusy(false)
    }
  }

  const handleRepairAllPlaybackIssues = async () => {
    if (bulkRepairBusy) return
    setBulkRepairBusy(true)
    try {
      const searchFilter = search || undefined
      const [failures, suppressed] = await Promise.all([
        adminApi.listTrackIds({
          scope: 'playback_failures',
          search: searchFilter,
        }),
        adminApi.listTrackIds({
          scope: 'playback_suppressed',
          search: searchFilter,
        }),
      ])
      const ids = Array.from(
        new Set([...failures.ids, ...suppressed.ids]),
      )
      if (ids.length === 0) {
        await showAlert(t('admin.tracks.repairAllNoIssues'))
        return
      }
      const r = await repairTrackIds(ids)
      await showRepairBulkResult(r)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBulkRepairBusy(false)
    }
  }

  const handleClearPlaybackDiagnostics = async (id: number) => {
    setBusyId(id)
    try {
      await adminApi.clearTrackPlaybackDiagnostics(id)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleFullRestorePlayback = async (id: number) => {
    const ok = await showConfirm(
      t('admin.tracks.confirmFullRecovery'),
    )
    if (!ok) return
    setBusyId(id)
    try {
      await adminApi.fullRestoreTrackPlayback(id)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleSavePlaybackSources = async () => {
    if (!sourceEditModal) return
    setSourceBusy(true)
    try {
      await adminApi.updateTrackMetadata(sourceEditModal.id, {
        sc_url: sourceForm.sc.trim() || null,
        source_url: sourceForm.src.trim() || null,
        canonical_source_url: sourceForm.can.trim() || null,
      })
      setSourceEditModal(null)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setSourceBusy(false)
    }
  }

  const handleToggleVisibility = async (id: number, isActive: boolean) => {
    setBusyId(id)
    try {
      await adminApi.setTrackVisibility(id, !isActive)
      refresh()
    } catch {}
    finally {
      setBusyId(null)
    }
  }

  const handleGenreChange = async (id: number, genre: string) => {
    setBusyId(id)
    try {
      await adminApi.updateTrackGenre(id, genre || null)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleOpen = (id: number) => {
    window.open(`/mini_app/track/${id}`, '_blank')
  }

  const handleTogglePlay = (id: number) => {
    setPlayingId((prev) => (prev === id ? null : id))
  }

  const handlePrompt = async (id: number) => {
    setBusyId(id)
    try {
      const res = await adminApi.getTrackPrompt(id)
      setPromptModal({ prompt: res.prompt, lang: res.language })
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleContext = async (id: number) => {
    setBusyId(id)
    try {
      const res = await adminApi.getTrackContext(id)
      setContextEditValue(res.content ?? '')
      setContextModal({ trackId: id, content: res.content, status: res.status })
      setTimeout(() => contextTextareaRef.current?.focus(), 50)
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleSaveContext = async () => {
    if (!contextModal) return
    setBusyContext(true)
    try {
      await adminApi.setTrackContext(contextModal.trackId, contextEditValue)
      setContextModal(null)
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyContext(false)
    }
  }

  const handleClearContext = async () => {
    if (!contextModal) return
    const ok = await showConfirm(
      t('admin.tracks.confirmClearContext'),
      { danger: true },
    )
    if (!ok) return
    setBusyContext(true)
    try {
      await adminApi.clearTrackContext(contextModal.trackId)
      setContextModal(null)
    } catch (err) {
      await showAlert((err as Error).message)
    } finally {
      setBusyContext(false)
    }
  }

  const handleBatchPrompt = async () => {
    const ids = Array.from(selectedIds)
    try {
      const res = await adminApi.batchPrompt(ids)
      setBatchPromptModal(res.prompt)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleBatchLyricsPromptSelected = async () => {
    const ids = Array.from(selectedIds)
    try {
      const res = await adminApi.batchLyricsPrompt({
        track_ids: ids,
        only_without_lyrics: true,
      })
      setBatchLyricsPromptModal(res.prompt)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleBatchLyricsPromptFiltered = async () => {
    try {
      const res = await adminApi.batchLyricsPrompt({
        search: search || undefined,
        only_without_lyrics: true,
        limit: 300,
      })
      setBatchLyricsPromptModal(res.prompt)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleLyricsImport = async () => {
    try {
      const res = await adminApi.batchLyricsImport(importText, true)
      setImportResult(res)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleBatchGenreMoodPromptSelected = async () => {
    const ids = Array.from(selectedIds)
    try {
      const res = await adminApi.batchGenreMoodPrompt({ track_ids: ids })
      setBatchGenreMoodPromptModal(res.prompt)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleBatchGenreMoodPromptFiltered = async () => {
    try {
      const res = await adminApi.batchGenreMoodPrompt({
        search: search || undefined,
        only_without_genre: true,
        limit: 300,
      })
      setBatchGenreMoodPromptModal(res.prompt)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleGenreMoodImport = async () => {
    try {
      const res = await adminApi.batchGenreMoodImport(
        gmImportText,
        gmOverwriteGenre,
      )
      setGmImportResult(res)
      refresh()
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selectedIds.has(r.id))

  const addSelectedIds = (ids: number[]) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      ids.forEach((id) => next.add(id))
      return next
    })
  }

  const fetchTrackPageIds = async (
    targetPage: number,
  ): Promise<number[]> => {
    const result = await fetchTrackPage(targetPage)
    return (result.items as unknown as TrackRow[]).map((track) => track.id)
  }

  const fetchTrackAllIds = async (): Promise<number[]> => {
    const scope: TrackIdScope =
      listView === 'all' ? 'all' : listView
    const result = await adminApi.listTrackIds({
      scope,
      search: search || undefined,
      without_lyrics:
        listView === 'all' ? withoutLyricsOnly || undefined : undefined,
    })
    return result.ids
  }

  const toggleSelectAll = (checked: boolean) => {
    const pageIds = rows.map((r) => r.id)
    if (checked) {
      addSelectedIds(pageIds)
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        pageIds.forEach((id) => next.delete(id))
        return next
      })
    }
  }

  const toggleSelectOne = (id: number, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      checked ? next.add(id) : next.delete(id)
      return next
    })
  }

  const columns: ColumnDef<TrackRow>[] = [
    {
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          checked={allOnPageSelected}
          onChange={(e) => toggleSelectAll(e.target.checked)}
          aria-label={t('admin.tracks.selectAllAria')}
        />
      ),
      cell: (i) => (
        <input
          type="checkbox"
          checked={selectedIds.has(i.row.original.id)}
          onChange={(e) => toggleSelectOne(i.row.original.id, e.target.checked)}
          aria-label={t('admin.tracks.selectOneAria', {
            id: i.row.original.id,
          })}
        />
      ),
      enableSorting: false,
    },
    {
      header: t('admin.tracks.colId'),
      accessorKey: 'id',
      cell: (i) => (
        <span className="admin-mono">{i.getValue<number>()}</span>
      ),
    },
    {
      header: t('admin.tracks.colTitle'),
      accessorKey: 'title',
      cell: (i) => (
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="admin-link"
          onClick={() => handleOpen(i.row.original.id)}
        >
          {i.row.original.title}
        </MotionPress>
      ),
    },
    {
      header: t('admin.tracks.colArtist'),
      accessorKey: 'artist',
    },
    {
      header: t('admin.tracks.colSource'),
      accessorKey: 'source',
    },
    {
      header: t('admin.tracks.colGenre'),
      accessorKey: 'genre',
      cell: (i) => (
        <input
          type="text"
          defaultValue={i.row.original.genre || ''}
          placeholder={t('admin.tracks.noGenrePlaceholder')}
          onBlur={(e) => {
            if (e.target.value !== (i.row.original.genre || '')) {
              handleGenreChange(i.row.original.id, e.target.value)
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.currentTarget.blur()
            }
          }}
          style={{ width: 120, padding: '4px 8px', fontSize: 13, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--surface-1)', color: 'var(--text)' }}
          disabled={busyId === i.row.original.id}
        />
      ),
    },
    {
      header: 'Playback',
      id: 'playback_health',
      cell: (i) => {
        const r = i.row.original
        const parts: string[] = []
        const diagnostics = playbackDiagnosticParts(r)
        if (r.playback_last_failure_source) {
          parts.push(r.playback_last_failure_source)
        }
        if (
          typeof r.playback_last_http_status === 'number'
        ) {
          parts.push(`HTTP ${r.playback_last_http_status}`)
        }
        if (r.playback_last_failure_at) {
          parts.push(
            new Date(
              r.playback_last_failure_at,
            ).toLocaleString(),
          )
        }
        if (r.playback_suppressed_until) {
          parts.push(
            `hidden until ${new Date(
              r.playback_suppressed_until,
            ).toLocaleDateString()}`,
          )
        }
        if (diagnostics.length > 0) {
          parts.push(diagnostics.join(' / '))
        }
        return parts.length ? (
          <span style={{ fontSize: 12, lineHeight: 1.35 }}>
            {parts.join(' / ')}
          </span>
        ) : (
          '—'
        )
      },
    },
    {
      header: t('admin.tracks.colStatus'),
      accessorKey: 'is_active',
      cell: (i) =>
        i.row.original.is_active ? (
          <StatusPill kind="ok">{t('admin.tracks.visible')}</StatusPill>
        ) : (
          <StatusPill kind="warn">{t('admin.tracks.hidden')}</StatusPill>
        ),
    },
    {
      header: t('admin.tracks.colUploaded'),
      accessorKey: 'created_at',
      cell: (i) =>
        new Date(i.row.original.created_at).toLocaleDateString(),
    },
    {
      header: '',
      id: 'actions',
      enableSorting: false,
      cell: (i) => {
        const { id, title, is_active } = i.row.original
        const busy = busyId === id
        const isPlaying = playingId === id
        const pbRow =
          listView !== 'all' ||
          !!i.row.original.playback_last_failure_at ||
          !!i.row.original.playback_suppressed_until
        return (
          <div
            style={{
              display: 'flex',
              gap: 6,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <MotionPress
              variant="ghost"
              onClick={() => setSourceEditModal(i.row.original)}
              disabled={busy}
            >
              {t('admin.tracks.actionSources')}
            </MotionPress>
            {pbRow && (
              <>
                <MotionPress
                  variant="ghost"
                  onClick={() => handleVerifyPlayback(id)}
                  disabled={busy}
                >
                  {t('admin.tracks.actionCheck')}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  onClick={() => handleRepairPlayback(id)}
                  disabled={busy}
                >
                  {t('admin.tracks.actionRepair')}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  onClick={() =>
                    handleClearPlaybackDiagnostics(id)
                  }
                  disabled={busy}
                >
                  {t('admin.tracks.actionResetMarks')}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  onClick={() =>
                    handleFullRestorePlayback(id)
                  }
                  disabled={busy}
                >
                  {t('admin.tracks.actionFullRecovery')}
                </MotionPress>
              </>
            )}
            {i.row.original.playback_suppressed_until && (
              <MotionPress
                variant="ghost"
                onClick={() =>
                  handleClearPlaybackSuppression(id)
                }
                disabled={busy}
              >
                {t('admin.tracks.actionUnsuppress')}
              </MotionPress>
            )}
            <MotionPress
              variant="ghost"
              onClick={() => handleTogglePlay(id)}
              disabled={busy}
            >
              {isPlaying
                ? t('admin.tracks.actionPause')
                : t('admin.tracks.actionPlay')}
            </MotionPress>
            {isPlaying && (
              <audio
                src={trackProgressiveAudioUrl(id)}
                controls
                autoPlay
                style={{ height: 28, maxWidth: 180 }}
              />
            )}
            <MotionPress
              variant="ghost"
              onClick={() => handleToggleVisibility(id, is_active)}
              disabled={busy}
            >
              {is_active
                ? t('admin.tracks.actionHide')
                : t('admin.tracks.actionShow')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              onClick={() => handleOpen(id)}
              disabled={busy}
            >
              {t('admin.tracks.actionOpen')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              onClick={() => handlePrompt(id)}
              disabled={busy}
            >
              {t('admin.tracks.actionPrompt')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              onClick={() => handleContext(id)}
              disabled={busy}
            >
              {t('admin.tracks.actionContext')}
            </MotionPress>
            {listView === 'deleted' ? (
              <>
                <MotionPress
                  variant="ghost"
                  onClick={() => handleRestoreDeleted(id)}
                  disabled={busy}
                >
                  {t('admin.tracks.actionRestore')}
                </MotionPress>
                <MotionPress
                  variant="danger"
                  onClick={() =>
                    handleHardDeleteForever(id, title)
                  }
                  disabled={busy}
                >
                  {t('admin.tracks.actionHardDelete')}
                </MotionPress>
              </>
            ) : (
              <MotionPress
                variant="ghost"
                onClick={() => handleDelete(id, title)}
                disabled={busy}
              >
                {t('admin.tracks.actionDelete')}
              </MotionPress>
            )}
          </div>
        )
      },
    },
  ]

  return (
    <div>
      <h1>{t('admin.tracks.title')}</h1>
      <section className="kpi-grid">
        <KpiCard
          label={t('admin.tracks.title')}
          value={total}
          hint={t('admin.common.total', { count: total })}
        />
        <KpiCard
          label={t('admin.tracks.visible')}
          value={visibleCount}
          hint={t('admin.tracks.hidden')}
        />
        <KpiCard
          label="With genre"
          value={withGenreCount}
          hint={
            sparkline.length > 1 ? (
              <Sparkline
                data={sparkline}
                ariaLabel="Tracks growth sparkline"
              />
            ) : undefined
          }
        />
      </section>
      <section className="admin-card">
        <div className="admin-dashboard__toplist-head">
          <h2>{t('admin.tracks.analyticsTitle', 'Track analytics')}</h2>
          <AdminRangeSwitch
            groupId="tracks-stats-period"
            value={statsPeriod}
            onChange={setStatsPeriod}
            options={[
              {
                value: 'today',
                label: t('redesign.admin.dashboard.periodToday'),
              },
              {
                value: '7d',
                label: t('redesign.admin.dashboard.period7d'),
              },
              {
                value: '30d',
                label: t('redesign.admin.dashboard.period30d'),
              },
              {
                value: 'all',
                label: t('redesign.admin.dashboard.periodAll'),
              },
            ]}
          />
        </div>
        {trackStats.isLoading || !trackStats.data ? (
          <div className="admin-skeleton admin-skeleton--card" />
        ) : (
          <>
            <h3>Uploads timeline</h3>
            <LineChart
              data={trackStats.data.uploads_series}
              ariaLabel="Track uploads timeline"
            />
            <h3>Top popular tracks</h3>
            {trackStats.data.top_tracks.length === 0 ? (
              <div className="admin-log-empty">No data</div>
            ) : (
              <div className="admin-dashboard__toplist-rows">
                {trackStats.data.top_tracks.map((item) => (
                  <div
                    key={item.track_id}
                    className="admin-dashboard__toplist-row"
                  >
                    <div className="admin-dashboard__toplist-title">
                      {item.title}
                    </div>
                    <div className="admin-dashboard__toplist-meta">
                      {item.plays} plays · {item.unique_listeners} listeners
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t('admin.tracks.searchPlaceholder')}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
            setSelectedIds(new Set())
          }}
        />
        <AdminRangeSwitch
          groupId="admin-tracks-list-scope"
          value={listView}
          onChange={(v) => {
            setListView(
              v as
                | 'all'
                | 'playback_failures'
                | 'playback_suppressed'
                | 'deleted',
            )
            setPage(1)
            setSelectedIds(new Set())
          }}
          options={[
            { value: 'all', label: 'All' },
            {
              value: 'playback_failures',
              label: 'Playback issues',
            },
            {
              value: 'playback_suppressed',
              label: 'Auto-hidden',
            },
            { value: 'deleted', label: 'Deleted' },
          ]}
        />
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: 'var(--text-secondary)',
          }}
        >
          <input
            type="checkbox"
            checked={withoutLyricsOnly}
            disabled={listView !== 'all'}
            onChange={(e) => {
              setWithoutLyricsOnly(e.target.checked)
              setPage(1)
              setSelectedIds(new Set())
            }}
          />
          {t('admin.tracks.filterWithoutLyrics')}
        </label>
        <BulkPageSelector
          currentPage={page}
          totalPages={totalPages}
          totalItems={total}
          selectedCount={selectedIds.size}
          disabled={isFetching}
          fetchPageIds={fetchTrackPageIds}
          fetchAllIds={fetchTrackAllIds}
          onAddIds={addSelectedIds}
          onClear={() => setSelectedIds(new Set())}
          onError={(err) => showAlert(err.message)}
        />
        <MotionPress
          variant="primary"
          disabled={selectedIds.size === 0}
          title={
            selectedIds.size === 0
              ? t('admin.tracks.batchSelectHint')
              : undefined
          }
          onClick={handleBatchPrompt}
        >
          {t('admin.tracks.batchContextPromptBtn', {
            count: selectedIds.size,
          })}
        </MotionPress>
        <MotionPress
          variant="ghost"
          disabled={selectedIds.size === 0}
          title={
            selectedIds.size === 0
              ? t('admin.tracks.batchSelectHint')
              : undefined
          }
          onClick={handleBatchLyricsPromptSelected}
        >
          {t('admin.tracks.batchLyricsPromptBtn', {
            count: selectedIds.size,
          })}
        </MotionPress>
        <MotionPress
          variant="ghost"
          disabled={selectedIds.size === 0}
          title={
            selectedIds.size === 0
              ? t('admin.tracks.batchSelectHint')
              : undefined
          }
          onClick={handleBatchGenreMoodPromptSelected}
        >
          {t('admin.tracks.batchGenreMoodPromptBtn', {
            count: selectedIds.size,
          })}
        </MotionPress>
        <MotionPress
          variant="ghost"
          disabled={selectedIds.size === 0 || bulkRepairBusy}
          title={
            selectedIds.size === 0
              ? t('admin.tracks.batchSelectHint')
              : undefined
          }
          onClick={handleRepairSelectedPlayback}
        >
          {t('admin.tracks.repairSelectedBtn', {
            count: selectedIds.size,
          })}
        </MotionPress>
        <MotionPress
          variant="ghost"
          disabled={bulkRepairBusy}
          onClick={handleRepairAllPlaybackIssues}
        >
          {t('admin.tracks.repairAllIssuesBtn')}
        </MotionPress>
        <MotionPress
          variant="ghost"
          onClick={() => {
            setImportText('')
            setImportResult(null)
            setImportModal(true)
          }}
        >
          {t('admin.tracks.importLyricsOpenBtn')}
        </MotionPress>
        <OverflowMenu
          label={t('admin.tracks.moreBatchActions')}
          items={[
            {
              id: 'lyrics-prompt-filt',
              label: t('admin.tracks.lyricsPromptFiltered'),
              onSelect: handleBatchLyricsPromptFiltered,
            },
            {
              id: 'gm-prompt-filt',
              label: t('admin.tracks.genreMoodPromptFiltered'),
              onSelect: handleBatchGenreMoodPromptFiltered,
            },
            {
              id: 'gm-import',
              label: t('admin.tracks.importGmOpenBtn'),
              onSelect: () => {
                setGmImportText('')
                setGmImportResult(null)
                setGmOverwriteGenre(false)
                setGmImportModal(true)
              },
            },
          ]}
        />
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        enableSorting
      />
      <div className="admin-pagination">
        <MotionPress
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          {t('admin.common.prev')}
        </MotionPress>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <MotionPress
          variant="ghost"
          disabled={page >= totalPages || isFetching}
          onClick={() => setPage((p) => p + 1)}
        >
          {t('admin.common.next')}
        </MotionPress>
      </div>

      <FormModal
        open={!!promptModal}
        size="lg"
        title={
          <>
            {t('admin.tracks.promptModalTitle')}{' '}
            <span style={{ fontSize: 12, fontWeight: 400 }}>
              [{promptModal?.lang.toUpperCase()}]
            </span>
          </>
        }
        onClose={() => setPromptModal(null)}
        footer={
          <>
            <MotionPress
              variant="ghost"
              onClick={() => setPromptModal(null)}
            >
              {t('admin.common.close')}
            </MotionPress>
            <MotionPress
              variant="primary"
              onClick={() =>
                promptModal &&
                navigator.clipboard.writeText(promptModal.prompt)
              }
            >
              {t('admin.common.copy')}
            </MotionPress>
          </>
        }
      >
        <textarea
          readOnly
          value={promptModal?.prompt ?? ''}
          rows={18}
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 13,
            resize: 'vertical',
          }}
        />
      </FormModal>

      <FormModal
        open={!!contextModal}
        size="md"
        title={t('admin.tracks.contextModalTitle', {
          id: contextModal?.trackId ?? '',
        })}
        subtitle={
          contextModal
            ? t('admin.tracks.contextStatus', {
                status: contextModal.status,
              })
            : undefined
        }
        submitting={busyContext}
        closeOnOverlayClick={!busyContext}
        onClose={() => setContextModal(null)}
        footer={
          <>
            <MotionPress
              variant="ghost"
              onClick={() => setContextModal(null)}
              disabled={busyContext}
            >
              {t('admin.common.cancel')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              onClick={handleClearContext}
              disabled={busyContext}
            >
              {t('admin.common.clear')}
            </MotionPress>
            <MotionPress
              variant="primary"
              onClick={handleSaveContext}
              disabled={busyContext || !contextEditValue.trim()}
            >
              {t('admin.common.save')}
            </MotionPress>
          </>
        }
      >
        <textarea
          ref={contextTextareaRef}
          value={contextEditValue}
          onChange={(e) => setContextEditValue(e.target.value)}
          rows={10}
          maxLength={5000}
          style={{ width: '100%', resize: 'vertical' }}
          disabled={busyContext}
          placeholder={t('admin.tracks.contextEditPlaceholder')}
        />
        <p
          style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            margin: 0,
            textAlign: 'right',
          }}
        >
          {contextEditValue.length} / 5000
        </p>
      </FormModal>

      <FormModal
        open={!!batchPromptModal}
        size="lg"
        title={t('admin.tracks.batchPromptTitle', {
          count: selectedIds.size,
        })}
        subtitle={t('admin.tracks.batchPromptSubtitle')}
        onClose={() => setBatchPromptModal(null)}
        footer={
          <>
            <MotionPress
              variant="ghost"
              onClick={() => setBatchPromptModal(null)}
            >
              {t('admin.common.close')}
            </MotionPress>
            <MotionPress
              variant="primary"
              onClick={() =>
                batchPromptModal &&
                navigator.clipboard.writeText(batchPromptModal)
              }
            >
              {t('admin.common.copy')}
            </MotionPress>
          </>
        }
      >
        <textarea
          readOnly
          value={batchPromptModal ?? ''}
          rows={22}
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
            resize: 'vertical',
          }}
        />
      </FormModal>

      <FormModal
        open={!!batchGenreMoodPromptModal}
        size="lg"
        title={t('admin.tracks.batchGenreMoodPromptTitle')}
        subtitle={t('admin.tracks.batchGenreMoodSubtitle')}
        onClose={() => setBatchGenreMoodPromptModal(null)}
        footer={
          <>
            <MotionPress
              variant="ghost"
              onClick={() => setBatchGenreMoodPromptModal(null)}
            >
              {t('admin.common.close')}
            </MotionPress>
            <MotionPress
              variant="primary"
              onClick={() =>
                batchGenreMoodPromptModal &&
                navigator.clipboard.writeText(
                  batchGenreMoodPromptModal,
                )
              }
            >
              {t('admin.common.copy')}
            </MotionPress>
          </>
        }
      >
        <textarea
          readOnly
          value={batchGenreMoodPromptModal ?? ''}
          rows={22}
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
            resize: 'vertical',
          }}
        />
      </FormModal>

      <FormModal
        open={!!batchLyricsPromptModal}
        size="lg"
        title={t('admin.tracks.batchLyricsPromptTitle')}
        subtitle={t('admin.tracks.batchLyricsSubtitle')}
        onClose={() => setBatchLyricsPromptModal(null)}
        footer={
          <>
            <MotionPress
              variant="ghost"
              onClick={() => setBatchLyricsPromptModal(null)}
            >
              {t('admin.common.close')}
            </MotionPress>
            <MotionPress
              variant="primary"
              onClick={() =>
                batchLyricsPromptModal &&
                navigator.clipboard.writeText(batchLyricsPromptModal)
              }
            >
              {t('admin.common.copy')}
            </MotionPress>
          </>
        }
      >
        <textarea
          readOnly
          value={batchLyricsPromptModal ?? ''}
          rows={22}
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
            resize: 'vertical',
          }}
        />
      </FormModal>

      <FormModal
        open={!!sourceEditModal}
        size="md"
        title={t('admin.tracks.sourceEditTitle', {
          id: sourceEditModal?.id ?? '',
        })}
        subtitle={
          sourceEditModal
            ? `${sourceEditModal.title} · ${
                sourceEditModal.access_mode ?? '—'
              }${
                sourceEditModal.source_platform
                  ? ` · ${sourceEditModal.source_platform}`
                  : ''
              }`
            : undefined
        }
        submitting={sourceBusy}
        submitText={t('admin.common.save')}
        cancelText={t('admin.common.cancel')}
        closeOnOverlayClick={!sourceBusy}
        onClose={() => setSourceEditModal(null)}
        onSubmit={() => handleSavePlaybackSources()}
      >
        <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>
          SoundCloud URL (sc_url)
        </label>
        <textarea
          value={sourceForm.sc}
          onChange={(e) =>
            setSourceForm((p) => ({ ...p, sc: e.target.value }))
          }
          rows={3}
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
          }}
          disabled={sourceBusy}
        />
        <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>
          YouTube / Bandcamp (source_url)
        </label>
        <textarea
          value={sourceForm.src}
          onChange={(e) =>
            setSourceForm((p) => ({ ...p, src: e.target.value }))
          }
          rows={3}
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
          }}
          disabled={sourceBusy}
        />
        <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>
          {t('admin.tracks.sourceEditCanonical')}
        </label>
        <textarea
          value={sourceForm.can}
          onChange={(e) =>
            setSourceForm((p) => ({ ...p, can: e.target.value }))
          }
          rows={2}
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
          }}
          disabled={sourceBusy}
        />
        <p
          style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            margin: 0,
          }}
        >
          {t('admin.tracks.sourceEditClearHint')}
        </p>
      </FormModal>

      <FormModal
        open={importModal}
        size="md"
        title={t('admin.tracks.importLyricsTitle')}
        subtitle={t('admin.tracks.importLyricsSubtitle')}
        submitText={t('admin.common.import')}
        cancelText={t('admin.common.close')}
        submitDisabled={!importText.trim()}
        onClose={() => setImportModal(false)}
        onSubmit={() => handleLyricsImport()}
      >
        <textarea
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
          rows={14}
          placeholder={
            '{"tracks":[{"id":1,"lyrics":"line 1\\nline 2"},{"id":2,"lyrics":"..."}]}'
          }
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
            resize: 'vertical',
          }}
        />
        {importResult && (
          <div>
            <p style={{ fontWeight: 600, margin: 0 }}>
              {t('admin.tracks.importedCount', {
                count: importResult.imported,
              })}
            </p>
            {importResult.errors.length > 0 && (
              <ul
                style={{
                  fontSize: 12,
                  color: 'var(--state-error)',
                  paddingLeft: 16,
                  margin: '4px 0 0',
                }}
              >
                {importResult.errors.map((e, idx) => (
                  <li key={idx}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </FormModal>

      <FormModal
        open={gmImportModal}
        size="md"
        title={t('admin.tracks.importGmTitle')}
        subtitle={t('admin.tracks.importGmSubtitle')}
        submitText={t('admin.common.import')}
        cancelText={t('admin.common.close')}
        submitDisabled={!gmImportText.trim()}
        onClose={() => setGmImportModal(false)}
        onSubmit={() => handleGenreMoodImport()}
      >
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
            checked={gmOverwriteGenre}
            onChange={(e) => setGmOverwriteGenre(e.target.checked)}
          />
          {t('admin.tracks.gmOverwriteLabel')}
        </label>
        <textarea
          value={gmImportText}
          onChange={(e) => setGmImportText(e.target.value)}
          rows={14}
          placeholder={
            '{"tracks":[{"id":1,"genre":"Pop","moods":["bright"]}]}'
          }
          style={{
            width: '100%',
            fontFamily: 'monospace',
            fontSize: 12,
            resize: 'vertical',
          }}
        />
        {gmImportResult && (
          <div>
            <p style={{ fontWeight: 600, margin: 0 }}>
              {t('admin.tracks.importedCount', {
                count: gmImportResult.imported,
              })}
            </p>
            {gmImportResult.errors.length > 0 && (
              <ul
                style={{
                  fontSize: 12,
                  color: 'var(--state-error)',
                  paddingLeft: 16,
                  margin: '4px 0 0',
                }}
              >
                {gmImportResult.errors.map((e, idx) => (
                  <li key={idx}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </FormModal>
    </div>
  )
}
