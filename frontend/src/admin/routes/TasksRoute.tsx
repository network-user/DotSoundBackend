import { useEffect, useMemo, useState } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { showIsland } from '@/lib/island'
import { lyricsTierAdminTitle } from '../lib/lyricsAdminLabels'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { DataTable } from '../components/widgets/DataTable'
import { JsonViewer } from '../components/widgets/JsonViewer'
import { LyricsJobDetail } from '../components/widgets/LyricsJobDetail'
import {
  PlaybackRepairSummaryPanel,
  playbackRepairStageLabel,
} from '../components/widgets/PlaybackRepairSummaryPanel'
import {
  StatusPill,
  type StatusKind,
} from '../components/widgets/StatusPill'
import { useSearchParams } from 'react-router-dom'

interface QueueRow {
  name: string
  length: number | null
}

interface BackgroundJobRow {
  id: string
  name: string
  queue: string
  status: string
  payload: Record<string, unknown> | null
  progress_id: string | null
  attempts: number
  max_attempts: number
  duration_ms: number | null
  scheduled_job_id: string | null
  parent_job_id: string | null
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  live?: LiveProgress | null
}

const CATALOG_SYNC_BG_FILTER = 'sync_artist_catalog'
const PLAYBACK_REPAIR_BG_FILTER = 'repair_track_playback_task'
const ACTIVE_BG_STATUSES = [
  'queued',
  'running',
  'cancelling',
] as const

const BG_STATUS_OPTIONS = [
  '',
  'active',
  'queued',
  'running',
  'done',
  'failed',
  'failed_terminal',
  'cancelled',
  'cancelling',
]

function bgJobKind(status: string): StatusKind {
  if (status === 'done') return 'ok'
  if (
    status === 'failed' ||
    status === 'failed_terminal'
  )
    return 'error'
  if (
    status === 'queued' ||
    status === 'running' ||
    status === 'cancelling'
  )
    return 'warn'
  if (status === 'cancelled') return 'unknown'
  return 'unknown'
}

function formatAdminDate(raw: unknown): string {
  if (typeof raw !== 'string' || !raw) return 'вЂ“'
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return raw
  return d.toLocaleString()
}

function readBgPayloadTarget(payload: unknown): string {
  if (!payload || typeof payload !== 'object') return 'вЂ“'
  const data = payload as Record<string, unknown>
  const artistId = data.artist_id
  const albumId = data.soundcloud_album_id
  const trackId = data.track_id
  if (artistId !== undefined && albumId !== undefined) {
    return `artist:${artistId} / album:${albumId}`
  }
  if (artistId !== undefined) return `artist:${artistId}`
  if (trackId !== undefined) return `track:${trackId}`
  return 'вЂ“'
}

function readBgPayloadTrackId(payload: unknown): number | null {
  if (!payload || typeof payload !== 'object') return null
  const data = payload as Record<string, unknown>
  const trackId = data.track_id
  return typeof trackId === 'number' ? trackId : null
}

function shortBgTaskName(name: string): string {
  const raw = name.split(':').pop() || name
  return raw.split('.').pop() || raw
}

function isActiveBgStatus(status: string): boolean {
  return (ACTIVE_BG_STATUSES as readonly string[]).includes(status)
}

interface LiveProgress {
  progress_id?: string
  track_id?: number
  stage?: string
  state?: string
  updated_at?: string
  logs?: string[]
  result?: Record<string, unknown>
}

function readLiveProgress(raw: unknown): LiveProgress | null {
  if (!raw || typeof raw !== 'object') return null
  const data = raw as Record<string, unknown>
  const live = data.live
  if (!live || typeof live !== 'object') return null
  const value = live as LiveProgress
  return value.stage || value.state ? value : null
}

interface JobRow {
  id: string
  track_id: number
  status: string
  profile: string
  routed_to_worker: string | null
  attempts: number
  duration_ms: number | null
  created_at: string
  error: string | null
  requested_by_user_id?: number | null
  current_tier?: string | null
  tiers_planned?: string[] | null
  request_with_sync?: boolean
  request_bypass_cache?: boolean
}

interface ComputeJobRow {
  id: string
  job_type: string
  job_label: string
  target_kind: string | null
  target_id: string | null
  status: string
  attempts: number
  last_error: string | null
  claimed_by: string | null
  created_at: string
}

const queueColumns: ColumnDef<QueueRow>[] = [
  {
    header: 'Queue',
    accessorKey: 'name',
    cell: (i) => (
      <span className="admin-mono">
        {i.getValue<string>()}
      </span>
    ),
  },
  { header: 'Length', accessorKey: 'length' },
]

function jobKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'done') return 'ok'
  if (status === 'error') return 'error'
  if (status === 'queued' || status === 'running')
    return 'warn'
  return 'unknown'
}

function lyricsProfileKind(profile: string): StatusKind {
  if (profile === 'gpu_full') return 'warn'
  if (profile === 'cpu_light') return 'unknown'
  if (profile === 'catalog_only') return 'ok'
  return 'unknown'
}

function computeJobKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'succeeded') return 'ok'
  if (status === 'failed') return 'error'
  if (status === 'pending' || status === 'claimed')
    return 'warn'
  return 'unknown'
}

function computeTypeUi(jobType: string): {
  icon: string
  pillKind: StatusKind
  cssMod: string
} {
  switch (jobType) {
    case 'track_audio_features':
      return {
        icon: 'eq',
        pillKind: 'warn',
        cssMod: 'audio',
      }
    case 'catalog_ingest_normalize':
      return {
        icon: 'list',
        pillKind: 'unknown',
        cssMod: 'catalog',
      }
    case 'artist_features_update':
      return {
        icon: 'user',
        pillKind: 'ok',
        cssMod: 'artist',
      }
    case 'artist_similarity_index':
      return {
        icon: 'share',
        pillKind: 'ok',
        cssMod: 'sim-artist',
      }
    case 'track_similarity_index':
      return {
        icon: 'link',
        pillKind: 'warn',
        cssMod: 'sim-track',
      }
    default:
      return {
        icon: 'queue',
        pillKind: 'unknown',
        cssMod: 'other',
      }
  }
}

function computeTypeTexts(
  jobType: string,
  t: TFunction,
): { slug: string; hint: string } {
  const slugKey = `admin.tasks.computeTypes.${jobType}.slug`
  const hintKey = `admin.tasks.computeTypes.${jobType}.hint`
  const slugTry = t(slugKey)
  const hintTry = t(hintKey)
  return {
    slug:
      slugTry === slugKey
        ? t('admin.tasks.computeTypes._fallback.slug')
        : slugTry,
    hint:
      hintTry === hintKey
        ? t('admin.tasks.computeTypes._fallback.hint')
        : hintTry,
  }
}

function buildComputeColumns(
  t: TFunction,
): ColumnDef<ComputeJobRow>[] {
  return [
    {
      header: 'ID',
      accessorKey: 'id',
      cell: (i) => (
        <span
          className="admin-mono"
          title={i.getValue<string>()}
        >
          {String(i.getValue<string>()).slice(0, 10)}
        </span>
      ),
    },
    {
      header: t('admin.tasks.jobKind'),
      id: 'compute_job_kind',
      accessorFn: (row) => row.job_label,
      cell: (i) => {
        const row = i.row.original
        const ui = computeTypeUi(row.job_type)
        const texts = computeTypeTexts(row.job_type, t)
        return (
          <div
            className={`admin-compute-type admin-compute-type--${ui.cssMod}`}
            title={`${texts.hint}\n${row.job_type}`}
          >
            <Icon
              name={ui.icon}
              size={18}
              className="admin-compute-type__icon"
              aria-hidden
            />
            <div className="admin-compute-type__main">
              <StatusPill kind={ui.pillKind}>
                {texts.slug}
              </StatusPill>
              <div className="admin-compute-type__title">
                {row.job_label}
              </div>
            </div>
          </div>
        )
      },
    },
    {
      header: t('admin.tasks.computeTarget'),
      id: 'target',
      accessorFn: (row) =>
        `${row.target_kind || '–'} ${row.target_id || ''}`,
    },
    {
      header: t('admin.tasks.detail.status'),
      accessorKey: 'status',
      cell: (i) => (
        <StatusPill
          kind={computeJobKind(
            i.row.original.status,
          )}
        >
          {i.row.original.status}
        </StatusPill>
      ),
    },
    {
      header: t('admin.tasks.detail.attempts'),
      accessorKey: 'attempts',
    },
  ]
}

function buildJobColumns(
  t: TFunction,
  onOpen: (id: string) => void,
  onCancel: (id: string) => void,
  cancelLabel: string,
): ColumnDef<JobRow>[] {
  return [
  {
    header: 'ID',
    accessorKey: 'id',
    cell: (i) => {
      const id = i.getValue<string>()
      return (
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="admin-link admin-mono"
          onClick={() => onOpen(id)}
          title={id}
        >
          {String(id).slice(0, 8)}
        </MotionPress>
      )
    },
  },
  {
    header: t('admin.tasks.detail.track'),
    accessorKey: 'track_id',
  },
  {
    header: t('admin.tasks.lyricsPhase'),
    id: 'lyrics_goal',
    accessorFn: (row) =>
      [
        row.current_tier || '',
        ...(row.tiers_planned || []),
      ].join(' '),
    cell: (i) => {
      const row = i.row.original
      const title = lyricsTierAdminTitle(
        row.current_tier,
        t,
      )
      const planned = row.tiers_planned
      const planStr =
        Array.isArray(planned) && planned.length
          ? planned.join(' → ')
          : ''
      const tipLines = [title]
      if (planStr) {
        tipLines.push(
          `${t('admin.tasks.lyricsPipelineHint')}: ${planStr}`,
        )
      }
      return (
        <div
          className="admin-lyrics-goal"
          title={tipLines.join('\n\n')}
        >
          <div className="admin-lyrics-goal__title">
            {title}
          </div>
          {planStr ? (
            <div className="admin-lyrics-goal__plan admin-mono">
              {planStr}
            </div>
          ) : null}
          <div className="admin-lyrics-goal__flags">
            {row.request_with_sync ? (
              <span className="admin-lyrics-goal__flag">
                {t('admin.tasks.lyricsIntent.sync')}
              </span>
            ) : null}
            {row.request_bypass_cache ? (
              <span className="admin-lyrics-goal__flag">
                {t(
                  'admin.tasks.lyricsIntent.bypass',
                )}
              </span>
            ) : null}
            {!row.request_with_sync &&
            !row.request_bypass_cache ? (
              <span className="admin-lyrics-goal__flag admin-lyrics-goal__flag--muted">
                –
              </span>
            ) : null}
          </div>
        </div>
      )
    },
  },
  {
    header: t('admin.tasks.detail.status'),
    accessorKey: 'status',
    cell: (i) => (
      <StatusPill
        kind={jobKind(i.row.original.status)}
      >
        {i.row.original.status}
      </StatusPill>
    ),
  },
  {
    header: t('admin.tasks.detail.profile'),
    accessorKey: 'profile',
    cell: (i) => (
      <StatusPill
        kind={lyricsProfileKind(
          i.row.original.profile,
        )}
      >
        {i.row.original.profile}
      </StatusPill>
    ),
  },
  {
    header: t('admin.tasks.requestedByColumn'),
    id: 'requested_by',
    accessorKey: 'requested_by_user_id',
    cell: (i) => {
      const uid = i.row.original.requested_by_user_id
      if (uid == null) {
        return t('admin.tasks.requestedByAuto')
      }
      return String(uid)
    },
  },
  {
    header: t('admin.tasks.detail.worker'),
    accessorKey: 'routed_to_worker',
  },
  {
    header: t('admin.tasks.detail.attempts'),
    accessorKey: 'attempts',
  },
  {
    header: t('admin.tasks.detail.duration'),
    accessorKey: 'duration_ms',
    cell: (i) =>
      i.row.original.duration_ms
        ? `${(
            i.row.original.duration_ms / 1000
          ).toFixed(1)}s`
        : '–',
  },
  {
    id: 'actions',
    header: '',
    enableSorting: false,
    cell: (i) => {
      const { id, status } = i.row.original
      const cancellable =
        status === 'queued' || status === 'running'
      if (!cancellable) return null
      return (
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="admin-link"
          onClick={(e) => {
            e.stopPropagation()
            onCancel(id)
          }}
        >
          {cancelLabel}
        </MotionPress>
      )
    },
  },
  ]
}

export function TasksRoute() {
  const { t } = useTranslation()
  const { showConfirm } = useAdminPrompt()
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeJobId, setActiveJobId] = useState<
    string | null
  >(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bgFilter, setBgFilter] = useState<{
    name: string
    queue: string
    status: string
    scheduled_job_id: string
  }>(() => ({
    name: searchParams.get('bgName') ?? '',
    queue: searchParams.get('bgQueue') ?? '',
    status: searchParams.get('bgStatus') ?? '',
    scheduled_job_id: searchParams.get('schedule') ?? '',
  }))
  const [bgPage, setBgPage] = useState(1)
  const [bgDetailId, setBgDetailId] = useState<
    string | null
  >(null)

  useEffect(() => {
    const next = {
      name: searchParams.get('bgName') ?? '',
      queue: searchParams.get('bgQueue') ?? '',
      status: searchParams.get('bgStatus') ?? '',
      scheduled_job_id: searchParams.get('schedule') ?? '',
    }
    setBgFilter((cur) => {
      if (
        cur.name === next.name &&
        cur.queue === next.queue &&
        cur.status === next.status &&
        cur.scheduled_job_id === next.scheduled_job_id
      ) {
        return cur
      }
      setBgPage(1)
      return next
    })
  }, [searchParams])

  const overview = useQuery({
    queryKey: ['admin', 'tasks', 'overview'],
    queryFn: () => adminApi.tasksOverview(),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })
  const backgroundJobs = useQuery({
    queryKey: [
      'admin',
      'tasks',
      'background-jobs',
      bgFilter,
      bgPage,
    ],
    queryFn: () =>
      adminApi.listBackgroundJobs({
        page: bgPage,
        size: 50,
        name: bgFilter.name || undefined,
        queue: bgFilter.queue || undefined,
        status: bgFilter.status || undefined,
        scheduled_job_id: bgFilter.scheduled_job_id || undefined,
      }),
    refetchInterval: bgDetailId ? false : 10_000,
    refetchIntervalInBackground: false,
  })
  const activeBackgroundJobs = useQuery({
    queryKey: ['admin', 'tasks', 'background-jobs', 'active'],
    queryFn: () => adminApi.listActiveBackgroundJobs(),
    refetchInterval: 2500,
    refetchIntervalInBackground: false,
  })
  const bgDetail = useQuery({
    queryKey: ['admin', 'tasks', 'bg-job', bgDetailId],
    queryFn: () =>
      bgDetailId
        ? adminApi.getBackgroundJob(bgDetailId)
        : Promise.resolve(null),
    enabled: !!bgDetailId,
    refetchInterval: bgDetailId ? 2500 : false,
    refetchIntervalInBackground: false,
  })

  const invalidateBg = () => {
    qc.invalidateQueries({
      queryKey: ['admin', 'tasks', 'background-jobs'],
    })
    qc.invalidateQueries({
      queryKey: ['admin', 'tasks', 'background-jobs', 'active'],
    })
    qc.invalidateQueries({
      queryKey: ['admin', 'tasks', 'overview'],
    })
  }

  const cancelBg = useMutation({
    mutationFn: (id: string) =>
      adminApi.cancelBackgroundJob(id),
    onSuccess: () => invalidateBg(),
  })
  const bulkCancelBg = useMutation({
    mutationFn: (body: {
      name?: string
      queue?: string
      status?: string
      scheduled_job_id?: string
    }) => adminApi.cancelActiveBackgroundJobs(body),
    onSuccess: (data) => {
      invalidateBg()
      showIsland({
        kind: 'toast',
        title: t('admin.tasks.bg.cancelActiveDone', {
          count: data.matched,
        }),
        durationMs: 2400,
      })
    },
    onError: () => {
      showIsland({
        kind: 'error',
        title: t('admin.tasks.bg.cancelActiveFailed'),
        durationMs: 4000,
      })
    },
  })
  const retryBg = useMutation({
    mutationFn: (id: string) =>
      adminApi.retryBackgroundJob(id),
    onSuccess: () => invalidateBg(),
  })
  const retryUnresolvedPlayback = useMutation({
    mutationFn: (jobIds: string[]) =>
      adminApi.retryUnresolvedPlaybackRepairs(jobIds),
    onSuccess: (data) => {
      invalidateBg()
      showIsland({
        kind: 'toast',
        title: t('admin.tasks.bg.playbackRepair.retryQueued', {
          count: data.queued,
        }),
        durationMs: 2600,
      })
    },
    onError: () => {
      showIsland({
        kind: 'error',
        title: t('admin.tasks.bg.playbackRepair.retryFailed'),
        durationMs: 4000,
      })
    },
  })

  const queues = useQuery({
    queryKey: ['admin', 'tasks', 'queues'],
    queryFn: () => adminApi.listQueues(),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })
  const computeJobs = useQuery({
    queryKey: ['admin', 'tasks', 'compute-jobs'],
    queryFn: () =>
      adminApi.listComputeJobs({
        page: 1,
        size: 50,
      }),
    refetchInterval: activeJobId ? false : 15_000,
    refetchIntervalInBackground: false,
  })
  const jobs = useQuery({
    queryKey: ['admin', 'tasks', 'lyrics-jobs'],
    queryFn: () =>
      adminApi.listLyricsJobs({
        page: 1,
        size: 50,
      }),
    refetchInterval: activeJobId ? false : 15_000,
    refetchIntervalInBackground: false,
  })
  const computeRows =
    (computeJobs.data?.items as ComputeJobRow[] | undefined) ||
    []
  const rows = ((jobs.data?.items as JobRow[] | undefined) || [])
  const queuedCount = rows.filter(
    (r) => r.status === 'queued',
  ).length

  const handleCancelOne = async (id: string) => {
    try {
      await adminApi.cancelLyricsJob(id)
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'lyrics-jobs'],
      })
      showIsland({
        kind: 'toast',
        title: t('redesign.admin.tasks.cancelDone'),
        durationMs: 2000,
      })
    } catch {
      showIsland({
        kind: 'error',
        title: t('redesign.admin.tasks.cancelFailed'),
        durationMs: 4000,
      })
    }
  }

  const handleCancelAll = async () => {
    if (bulkBusy) return
    const ok = await showConfirm(
      t('admin.tasks.cancelAllConfirm', {
        count: queuedCount,
      }),
      { danger: true },
    )
    if (!ok) return
    setBulkBusy(true)
    try {
      await adminApi.cancelAllQueuedLyricsJobs()
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'lyrics-jobs'],
      })
      showIsland({
        kind: 'toast',
        title: t('redesign.admin.tasks.cancelAllDone', {
          count: queuedCount,
        }),
        durationMs: 2400,
      })
    } catch {
      showIsland({
        kind: 'error',
        title: t('redesign.admin.tasks.cancelFailed'),
        durationMs: 4000,
      })
    } finally {
      setBulkBusy(false)
    }
  }

  const computeColumns = buildComputeColumns(t)
  const jobColumns = buildJobColumns(
    t,
    (id) => setActiveJobId(id),
    handleCancelOne,
    t('admin.tasks.cancelRow'),
  )

  const bgRows =
    (backgroundJobs.data?.items as
      | BackgroundJobRow[]
      | undefined) || []
  const activeBgRows =
    (activeBackgroundJobs.data?.items as
      | BackgroundJobRow[]
      | undefined) || []
  const playbackRepairJobIds = useMemo(
    () =>
      bgRows
        .filter((row) =>
          row.name.includes(PLAYBACK_REPAIR_BG_FILTER),
        )
        .map((row) => row.id),
    [bgRows],
  )
  const playbackRepairSummary = useQuery({
    queryKey: [
      'admin',
      'tasks',
      'playback-repair-summary',
      playbackRepairJobIds.join(','),
    ],
    queryFn: () =>
      adminApi.playbackRepairSummary(playbackRepairJobIds),
    enabled:
      bgFilter.name.includes(PLAYBACK_REPAIR_BG_FILTER) &&
      playbackRepairJobIds.length > 0,
    refetchInterval: 2500,
    refetchIntervalInBackground: false,
  })
  const bgTotal = backgroundJobs.data?.total || 0
  const bgCounts =
    (overview.data?.background_jobs as
      | Record<string, number>
      | undefined) || {}
  const computeCounts =
    (overview.data?.compute_jobs as
      | Record<string, number>
      | undefined) || {}
  const lyricsCounts =
    (overview.data?.lyrics_jobs as
      | Record<string, number>
      | undefined) || {}
  const upcomingSchedules =
    (overview.data?.upcoming_schedules as
      | Array<{
          id: string
          name: string
          task_name: string
          cron: string
          next_run_at: string | null
        }>
      | undefined) || []

  const handleBgCancel = async (id: string) => {
    const ok = await showConfirm(
      t('admin.tasks.bg.confirmCancel'),
    )
    if (!ok) return
    cancelBg.mutate(id)
  }
  const handleBgBulkCancel = async () => {
    const activeCount =
      (bgCounts.queued || 0) +
      (bgCounts.running || 0) +
      (bgCounts.cancelling || 0)
    const ok = await showConfirm(
      t('admin.tasks.bg.confirmCancelActive', {
        count: activeCount,
      }),
      { danger: true },
    )
    if (!ok) return
    bulkCancelBg.mutate({
      name: bgFilter.name || undefined,
      queue: bgFilter.queue || undefined,
      status: isActiveBgStatus(bgFilter.status)
        ? bgFilter.status
        : undefined,
      scheduled_job_id:
        bgFilter.scheduled_job_id || undefined,
    })
  }
  const handleBgRetry = async (id: string) => {
    const ok = await showConfirm(
      t('admin.tasks.bg.confirmRetry'),
    )
    if (!ok) return
    retryBg.mutate(id)
  }
  const handleRetryUnresolvedPlayback = async (jobIds: string[]) => {
    const ok = await showConfirm(
      t('admin.tasks.bg.playbackRepair.confirmRetryUnresolved', {
        count: jobIds.length,
      }),
    )
    if (!ok) return
    retryUnresolvedPlayback.mutate(jobIds)
  }

  const setBgPreset = (
    patch: Partial<typeof bgFilter>,
  ) => {
    const next = { ...bgFilter, ...patch }
    setBgPage(1)
    setBgFilter(next)
    setSearchParams((params) => {
      const out = new URLSearchParams(params)
      const pairs: Array<[string, string]> = [
        ['bgName', next.name],
        ['bgQueue', next.queue],
        ['bgStatus', next.status],
        ['schedule', next.scheduled_job_id],
      ]
      for (const [key, value] of pairs) {
        if (value) out.set(key, value)
        else out.delete(key)
      }
      return out
    })
  }

  const clearBgFilters = () => {
    setBgPage(1)
    setBgFilter({
      name: '',
      queue: '',
      status: '',
      scheduled_job_id: '',
    })
    setSearchParams((params) => {
      const out = new URLSearchParams(params)
      for (const key of ['bgName', 'bgQueue', 'bgStatus', 'schedule']) {
        out.delete(key)
      }
      return out
    })
  }

  const bgColumns: ColumnDef<BackgroundJobRow>[] = [
    {
      header: 'ID',
      accessorKey: 'id',
      cell: (i) => (
        <MotionPress
          variant="ghost"
          haptic="selection"
          className="admin-link admin-mono"
          title={i.row.original.id}
          onClick={() => setBgDetailId(i.row.original.id)}
        >
          {String(i.row.original.id).slice(0, 8)}
        </MotionPress>
      ),
    },
    {
      header: t('admin.tasks.bg.cols.name') as string,
      accessorKey: 'name',
      cell: (i) => (
        <span className="admin-mono">
          {i.getValue<string>()}
        </span>
      ),
    },
    {
      header: t('admin.tasks.bg.cols.queue') as string,
      accessorKey: 'queue',
    },
    {
      header: t('admin.tasks.bg.cols.target') as string,
      id: 'target',
      accessorFn: (row) => readBgPayloadTarget(row.payload),
      cell: (i) => (
        <span className="admin-mono">
          {String(i.getValue<string>())}
        </span>
      ),
    },
    {
      header: t('admin.tasks.detail.status') as string,
      accessorKey: 'status',
      cell: (i) => (
        <StatusPill
          kind={bgJobKind(i.row.original.status)}
        >
          {i.row.original.status}
        </StatusPill>
      ),
    },
    {
      header: t('admin.tasks.detail.attempts') as string,
      id: 'attempts',
      accessorFn: (row) =>
        `${row.attempts}/${row.max_attempts}`,
    },
    {
      header: t('admin.tasks.detail.duration') as string,
      accessorKey: 'duration_ms',
      cell: (i) =>
        i.row.original.duration_ms
          ? `${(
              (i.row.original.duration_ms || 0) / 1000
            ).toFixed(1)}s`
          : '–',
    },
    {
      header: t('admin.tasks.bg.cols.created') as string,
      accessorKey: 'created_at',
      cell: (i) => {
        const v = i.getValue<string>()
        try {
          return new Date(v).toLocaleString()
        } catch {
          return v
        }
      },
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      cell: (i) => {
        const row = i.row.original
        const cancellable =
          row.status === 'queued' ||
          row.status === 'running'
        const retryable =
          row.status === 'failed' ||
          row.status === 'failed_terminal' ||
          row.status === 'cancelled'
        return (
          <div className="admin-toolbar admin-toolbar--compact">
            {cancellable && (
              <MotionPress
                variant="ghost"
                haptic="selection"
                className="admin-link"
                onClick={(e) => {
                  e.stopPropagation()
                  handleBgCancel(row.id)
                }}
              >
                {t('admin.tasks.bg.actions.cancel')}
              </MotionPress>
            )}
            {retryable && (
              <MotionPress
                variant="ghost"
                haptic="selection"
                className="admin-link"
                onClick={(e) => {
                  e.stopPropagation()
                  handleBgRetry(row.id)
                }}
              >
                {t('admin.tasks.bg.actions.retry')}
              </MotionPress>
            )}
          </div>
        )
      },
    },
  ]

  return (
    <div>
      <h1>{t('admin.tasks.title')}</h1>
      <section className="admin-card">
        <h2>{t('admin.tasks.overview.title')}</h2>
        <p className="admin-card__sub">
          {t('admin.tasks.overview.hint')}
        </p>
        <div className="admin-kpi-row">
          <div className="admin-kpi">
            <div className="admin-kpi__label">
              {t('admin.tasks.overview.queuesTotal')}
            </div>
            <div className="admin-kpi__value">
              {(overview.data?.queues || []).reduce(
                (a, q) => a + (q.length || 0),
                0,
              )}
            </div>
          </div>
          <div className="admin-kpi">
            <div className="admin-kpi__label">
              {t('admin.tasks.overview.bgRunning')}
            </div>
            <div className="admin-kpi__value">
              {(bgCounts.running || 0) +
                (bgCounts.queued || 0)}
            </div>
          </div>
          <div className="admin-kpi">
            <div className="admin-kpi__label">
              {t('admin.tasks.overview.bgFailed')}
            </div>
            <div className="admin-kpi__value">
              {(bgCounts.failed_terminal || 0) +
                (bgCounts.failed || 0)}
            </div>
          </div>
          <div className="admin-kpi">
            <div className="admin-kpi__label">
              {t('admin.tasks.overview.computeOpen')}
            </div>
            <div className="admin-kpi__value">
              {(computeCounts.pending || 0) +
                (computeCounts.claimed || 0)}
            </div>
          </div>
          <div className="admin-kpi">
            <div className="admin-kpi__label">
              {t('admin.tasks.overview.lyricsOpen')}
            </div>
            <div className="admin-kpi__value">
              {(lyricsCounts.queued || 0) +
                (lyricsCounts.running || 0)}
            </div>
          </div>
        </div>
        {upcomingSchedules.length > 0 && (
          <>
            <h3 style={{ marginTop: '1.2rem' }}>
              {t('admin.tasks.overview.upcoming')}
            </h3>
            <ul className="admin-list">
              {upcomingSchedules
                .slice(0, 5)
                .map((s) => (
                  <li key={s.name}>
                    <MotionPress
                      variant="ghost"
                      haptic="selection"
                      className="admin-link admin-mono"
                      title={t('admin.tasks.bg.filterBySchedule') as string}
                      onClick={() =>
                        setBgPreset({
                          scheduled_job_id:
                            bgFilter.scheduled_job_id === s.id
                              ? ''
                              : s.id,
                        })
                      }
                    >
                      {s.name}
                    </MotionPress>{' '}
                    →{' '}
                    <span className="admin-mono">
                      {s.task_name}
                    </span>{' '}
                    ({s.cron}) —{' '}
                    {s.next_run_at
                      ? new Date(
                          s.next_run_at,
                        ).toLocaleString()
                      : '–'}
                  </li>
                ))}
            </ul>
          </>
        )}
      </section>
      <section className="admin-card">
        <div className="admin-toolbar">
          <h2 style={{ flex: 1 }}>
            {t('admin.tasks.bg.active.title')}
          </h2>
          {activeBgRows.length > 0 && (
            <MotionPress
              variant="danger"
              haptic="medium"
              onClick={handleBgBulkCancel}
              disabled={bulkCancelBg.isPending}
            >
              {bulkCancelBg.isPending
                ? t('admin.tasks.bg.active.cancelling')
                : t('admin.tasks.bg.active.cancelAll', {
                    count: activeBgRows.length,
                  })}
            </MotionPress>
          )}
        </div>
        <p className="admin-card__sub">
          {t('admin.tasks.bg.active.hint')}
        </p>
        {activeBackgroundJobs.isError && (
          <p className="admin-error" role="alert">
            {t('admin.tasks.bg.active.loadFailed')}
          </p>
        )}
        {activeBgRows.length === 0 && !activeBackgroundJobs.isLoading ? (
          <p className="admin-card__sub">
            {t('admin.tasks.bg.active.empty')}
          </p>
        ) : (
          <div className="admin-active-jobs">
            {activeBgRows.map((row) => {
              const live = row.live || null
              const logs = Array.isArray(live?.logs)
                ? live.logs.slice(-1)
                : []
              const activeStage = live?.stage || row.status
              const activeStageLabel = row.name.includes(
                PLAYBACK_REPAIR_BG_FILTER,
              )
                ? playbackRepairStageLabel(t, activeStage)
                : activeStage
              return (
                <div
                  className="admin-active-job"
                  key={row.id}
                >
                  <div className="admin-active-job__main">
                    <div className="admin-active-job__title">
                      <span className="admin-mono">
                        {shortBgTaskName(row.name)}
                      </span>
                      <StatusPill kind={bgJobKind(row.status)}>
                        {row.status}
                      </StatusPill>
                    </div>
                    <div className="admin-active-job__meta">
                      <span className="admin-mono">
                        {readBgPayloadTarget(row.payload)}
                      </span>
                      <span>{formatAdminDate(row.created_at)}</span>
                    </div>
                    <div className="admin-active-job__stage">
                      <span>
                        {t('admin.tasks.bg.active.stage')}
                      </span>
                      <strong>
                        {activeStageLabel}
                      </strong>
                    </div>
                    {logs.length > 0 && (
                      <div className="admin-active-job__log">
                        {logs[0]}
                      </div>
                    )}
                  </div>
                  <div className="admin-active-job__actions">
                    <MotionPress
                      variant="ghost"
                      haptic="selection"
                      className="admin-link"
                      onClick={() => setBgDetailId(row.id)}
                    >
                      {t('admin.tasks.bg.active.open')}
                    </MotionPress>
                    <MotionPress
                      variant="ghost"
                      haptic="selection"
                      className="admin-link"
                      onClick={() => handleBgCancel(row.id)}
                      disabled={cancelBg.isPending}
                    >
                      {t('admin.tasks.bg.actions.cancel')}
                    </MotionPress>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
      <section className="admin-card">
        <div className="admin-toolbar">
          <h2 style={{ flex: 1 }}>
            {t('admin.tasks.bg.title')}
          </h2>
          <MotionPress
            variant="danger"
            haptic="medium"
            onClick={handleBgBulkCancel}
            disabled={bulkCancelBg.isPending}
            title={t('admin.tasks.bg.cancelActiveHint') as string}
          >
            {t('admin.tasks.bg.cancelActive')}
          </MotionPress>
          <input
            type="text"
            placeholder={
              t('admin.tasks.bg.filterName') as string
            }
            value={bgFilter.name}
            onChange={(e) => {
              setBgPage(1)
              setBgFilter((f) => ({
                ...f,
                name: e.target.value,
              }))
            }}
          />
          <input
            type="text"
            placeholder={
              t('admin.tasks.bg.filterQueue') as string
            }
            value={bgFilter.queue}
            onChange={(e) => {
              setBgPage(1)
              setBgFilter((f) => ({
                ...f,
                queue: e.target.value,
              }))
            }}
          />
          <select
            value={bgFilter.status}
            onChange={(e) => {
              setBgPage(1)
              setBgFilter((f) => ({
                ...f,
                status: e.target.value,
              }))
            }}
            aria-label={t('admin.tasks.bg.filterStatus') as string}
          >
            {BG_STATUS_OPTIONS.map((status) => (
              <option key={status || 'all'} value={status}>
                {status || (t('admin.tasks.bg.anyStatus') as string)}
              </option>
            ))}
          </select>
          {bgFilter.scheduled_job_id && (
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-filter-chip"
              onClick={() =>
                setBgPreset({
                  scheduled_job_id: '',
                })
              }
              title={t('admin.tasks.bg.clearScheduleFilter') as string}
            >
              schedule:{bgFilter.scheduled_job_id.slice(0, 16)}
              {bgFilter.scheduled_job_id.length > 16 ? '…' : ''}{' '}×
            </MotionPress>
          )}
          {(bgFilter.name ||
            bgFilter.queue ||
            bgFilter.status ||
            bgFilter.scheduled_job_id) && (
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              onClick={clearBgFilters}
            >
              {t('admin.tasks.bg.clearFilters')}
            </MotionPress>
          )}
        </div>
        <div className="admin-task-presets">
          <MotionPress
            variant="ghost"
            haptic="selection"
            onClick={() =>
              setBgPreset({
                name: CATALOG_SYNC_BG_FILTER,
                status: '',
              })
            }
          >
            {t('admin.tasks.bg.presets.catalogSync')}
          </MotionPress>
          <MotionPress
            variant="ghost"
            haptic="selection"
            onClick={() =>
              setBgPreset({
                name: PLAYBACK_REPAIR_BG_FILTER,
                status: '',
              })
            }
          >
            {t('admin.tasks.bg.presets.playbackRepair')}
          </MotionPress>
          <MotionPress
            variant="ghost"
            haptic="selection"
            onClick={() => setBgPreset({ status: 'queued' })}
          >
            {t('admin.tasks.bg.presets.queued')}
          </MotionPress>
          <MotionPress
            variant="ghost"
            haptic="selection"
            onClick={() => setBgPreset({ status: 'running' })}
          >
            {t('admin.tasks.bg.presets.running')}
          </MotionPress>
          <MotionPress
            variant="ghost"
            haptic="selection"
            onClick={() => setBgPreset({ status: 'failed_terminal' })}
          >
            {t('admin.tasks.bg.presets.failed')}
          </MotionPress>
        </div>
        {bgFilter.name.includes(PLAYBACK_REPAIR_BG_FILTER) &&
          playbackRepairSummary.data && (
          <PlaybackRepairSummaryPanel
            summary={playbackRepairSummary.data}
            onOpenTrack={(trackId) =>
              window.open(`/mini_app/track/${trackId}`, '_blank')
            }
            onRetryUnresolved={handleRetryUnresolvedPlayback}
            retryingUnresolved={retryUnresolvedPlayback.isPending}
          />
        )}
        <p className="admin-card__sub">
          {t('admin.tasks.bg.hint', { total: bgTotal })}
        </p>
        {backgroundJobs.isError && (
          <p className="admin-error" role="alert">
            {t('admin.tasks.bg.loadFailed')}
          </p>
        )}
        <DataTable
          columns={bgColumns}
          rows={bgRows}
          enableSorting
          emptyHint={t('admin.tasks.bg.empty') as string}
        />
        {bgTotal > 50 && (
          <div className="admin-pagination">
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              disabled={bgPage === 1}
              onClick={() => setBgPage((p) => Math.max(1, p - 1))}
            >
              ‹ {t('admin.tasks.bg.prev')}
            </MotionPress>
            <span>
              {t('admin.tasks.bg.pageOf', {
                page: bgPage,
                total: Math.ceil(bgTotal / 50),
              })}
            </span>
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="admin-link"
              disabled={bgPage * 50 >= bgTotal}
              onClick={() => setBgPage((p) => p + 1)}
            >
              {t('admin.tasks.bg.next')} ›
            </MotionPress>
          </div>
        )}
        {bgDetailId && (
          <div className="admin-detail-panel">
            <div className="admin-toolbar">
              <h3 style={{ flex: 1 }}>
                {t('admin.tasks.bg.detailTitle')}
              </h3>
              <MotionPress
                variant="ghost"
                haptic="selection"
                className="admin-link"
                onClick={() => setBgDetailId(null)}
              >
                {t('admin.tasks.bg.actions.close')}
              </MotionPress>
            </div>
            {bgDetail.isLoading && (
              <p>{t('admin.tasks.detail.loading')}</p>
            )}
            {bgDetail.data && (
              <div className="admin-bg-detail">
                <div className="admin-bg-detail__grid">
                  <div>
                    <span>{t('admin.tasks.bg.detail.task')}</span>
                    <strong className="admin-mono">
                      {String(bgDetail.data.name ?? 'вЂ“')}
                    </strong>
                  </div>
                  <div>
                    <span>{t('admin.tasks.detail.status')}</span>
                    <StatusPill
                      kind={bgJobKind(String(bgDetail.data.status ?? ''))}
                    >
                      {String(bgDetail.data.status ?? 'вЂ“')}
                    </StatusPill>
                  </div>
                  <div>
                    <span>{t('admin.tasks.bg.cols.queue')}</span>
                    <strong className="admin-mono">
                      {String(bgDetail.data.queue ?? 'вЂ“')}
                    </strong>
                  </div>
                  <div>
                    <span>{t('admin.tasks.bg.cols.target')}</span>
                    <strong className="admin-mono">
                      {readBgPayloadTarget(bgDetail.data.payload)}
                    </strong>
                    {(() => {
                      const trackId = readBgPayloadTrackId(
                        bgDetail.data.payload,
                      )
                      if (trackId == null) return null
                      return (
                        <MotionPress
                          variant="ghost"
                          haptic="selection"
                          className="admin-link"
                          onClick={() =>
                            window.open(
                              `/mini_app/track/${trackId}`,
                              '_blank',
                            )
                          }
                        >
                          {t(
                            'admin.tasks.bg.playbackRepair.openTrack',
                            { id: trackId },
                          )}
                        </MotionPress>
                      )
                    })()}
                  </div>
                  <div>
                    <span>{t('admin.tasks.detail.attempts')}</span>
                    <strong>
                      {String(bgDetail.data.attempts ?? 0)} /{' '}
                      {String(bgDetail.data.max_attempts ?? 0)}
                    </strong>
                  </div>
                  <div>
                    <span>{t('admin.tasks.bg.detail.created')}</span>
                    <strong>{formatAdminDate(bgDetail.data.created_at)}</strong>
                  </div>
                </div>
                {(() => {
                  const live = readLiveProgress(bgDetail.data)
                  if (!live) return null
                  const logs = Array.isArray(live.logs)
                    ? live.logs.slice(-8)
                    : []
                  const liveTrackId =
                    typeof live.track_id === 'number'
                      ? live.track_id
                      : null
                  return (
                    <div className="admin-bg-detail__block">
                      <span>{t('admin.tasks.bg.live.title')}</span>
                      <div className="admin-bg-detail__grid">
                        <div>
                          <span>
                            {t('admin.tasks.bg.live.stage')}
                          </span>
                          <StatusPill
                            kind={
                              live.state === 'finished'
                                ? bgJobKind('done')
                                : bgJobKind('running')
                            }
                          >
                            {playbackRepairStageLabel(
                              t,
                              live.stage ?? live.state ?? 'running',
                            )}
                          </StatusPill>
                        </div>
                        <div>
                          <span>
                            {t('admin.tasks.bg.live.track')}
                          </span>
                          <strong className="admin-mono">
                            {live.track_id ?? 'РІР‚вЂњ'}
                          </strong>
                          {liveTrackId != null && (
                            <MotionPress
                              variant="ghost"
                              haptic="selection"
                              className="admin-link"
                              onClick={() =>
                                window.open(
                                  `/mini_app/track/${liveTrackId}`,
                                  '_blank',
                                )
                              }
                            >
                              {t(
                                'admin.tasks.bg.playbackRepair.openTrack',
                                { id: liveTrackId },
                              )}
                            </MotionPress>
                          )}
                        </div>
                        <div>
                          <span>
                            {t('admin.tasks.bg.live.progressId')}
                          </span>
                          <strong className="admin-mono">
                            {live.progress_id ?? 'РІР‚вЂњ'}
                          </strong>
                        </div>
                        <div>
                          <span>
                            {t('admin.tasks.bg.live.updated')}
                          </span>
                          <strong>
                            {formatAdminDate(live.updated_at)}
                          </strong>
                        </div>
                      </div>
                      {logs.length > 0 && (
                        <pre>{logs.join('\n')}</pre>
                      )}
                      {live.result && (
                        <JsonViewer value={live.result} collapsed />
                      )}
                    </div>
                  )
                })()}
                {Boolean(bgDetail.data.error) && (
                  <div className="admin-bg-detail__block is-error">
                    <span>{t('admin.tasks.detail.errorTitle')}</span>
                    <pre>{String(bgDetail.data.error)}</pre>
                  </div>
                )}
                <div className="admin-bg-detail__block">
                  <span>{t('admin.tasks.bg.detail.payload')}</span>
                  <JsonViewer value={bgDetail.data.payload ?? {}} collapsed />
                </div>
                <div className="admin-bg-detail__block">
                  <span>{t('admin.tasks.bg.detail.result')}</span>
                  <JsonViewer
                    value={bgDetail.data.result_summary ?? {}}
                    collapsed
                  />
                </div>
                <details>
                  <summary>{t('admin.tasks.bg.detail.raw')}</summary>
                  <JsonViewer value={bgDetail.data} />
                </details>
              </div>
            )}
          </div>
        )}
      </section>
      <section className="admin-card">
        <h2>{t('admin.tasks.queues')}</h2>
        <DataTable
          columns={queueColumns}
          rows={
            (queues.data?.items as QueueRow[]) ||
            []
          }
          enableSorting
          emptyHint={t('admin.tasks.queuesEmpty')}
        />
      </section>
      <section className="admin-card">
        <h2>{t('admin.tasks.computeJobs')}</h2>
        <p className="admin-card__sub">
          {t('admin.tasks.computeJobsHint')}
        </p>
        {computeJobs.isError && (
          <p className="admin-error" role="alert">
            {t('admin.tasks.computeLoadFailed')}
          </p>
        )}
        <DataTable
          columns={computeColumns}
          rows={computeRows}
          enableSorting
          emptyHint={t('admin.tasks.computeQueueEmpty')}
        />
      </section>
      <section className="admin-card">
        <div className="admin-toolbar">
          <h2 style={{ flex: 1 }}>
            {t('admin.tasks.lyricsJobs')}
          </h2>
          {queuedCount > 0 && (
            <MotionPress
              variant="primary"
              onClick={handleCancelAll}
              disabled={bulkBusy}
            >
              {t('admin.tasks.cancelQueueButton', {
                count: queuedCount,
              })}
            </MotionPress>
          )}
        </div>
        <p className="admin-card__sub">
          {t('admin.tasks.lyricsJobsHint')}
        </p>
        <DataTable
          columns={jobColumns}
          rows={rows}
          enableSorting
        />
        <p className="admin-card__sub">
          {t('admin.tasks.detail.openHint')}
        </p>
      </section>
      {activeJobId && (
        <LyricsJobDetail
          jobId={activeJobId}
          onClose={() => setActiveJobId(null)}
        />
      )}
    </div>
  )
}
