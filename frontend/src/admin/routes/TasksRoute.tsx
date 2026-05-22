import { useEffect, useMemo, useRef, useState } from 'react'
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
import { AdminWs } from '../lib/adminWs'
import { Sparkline } from '../components/charts/Sparkline'
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

function TaskTypeTimeseriesCell({
  name,
  periodHours,
}: {
  name: string
  periodHours: number
}) {
  const q = useQuery({
    queryKey: ['admin', 'tasks', 'ts', name, periodHours],
    queryFn: () =>
      adminApi.tasksTypeTimeseries(name, periodHours, 5),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })
  if (q.isLoading) {
    return <span className="admin-card__sub">…</span>
  }
  if (q.isError || !q.data) {
    return <span className="admin-card__sub">—</span>
  }
  const data = q.data
  const series = data.buckets.map(
    (b) => b.succeeded + b.failed,
  )
  const total = series.reduce((a, b) => a + b, 0)
  if (total === 0) {
    return <span className="admin-card__sub">0</span>
  }
  const p95 = data.p95_duration_ms
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        minWidth: 140,
      }}
    >
      <Sparkline
        data={series}
        height={28}
        ariaLabel={`throughput ${name}`}
      />
      <span className="admin-card__sub" style={{ fontSize: 11 }}>
        {total}
        {p95 != null ? ` · p95 ${Math.round(p95 / 100) / 10}s` : ''}
      </span>
    </div>
  )
}


interface TaskTypeRow {
  name: string
  kind: 'taskiq' | 'compute' | 'mixed'
  paused: boolean
  paused_meta: {
    paused_at: string | null
    by_admin_id: number | null
    reason: string | null
  } | null
  by_status: Record<string, number>
  done_period: number
  failed_period: number
  avg_duration_ms: number | null
  max_duration_ms: number | null
  schedules: Array<{
    id: string
    name: string
    cron: string
    enabled: boolean
    next_run_at: string | null
  }>
}

interface WorkerRow {
  id: string
  name: string
  profile: string
  active: boolean
  max_concurrent_jobs: number
  last_seen_at: string | null
  last_ip: string | null
  revoked_at: string | null
  suspended_until: string | null
  suspended_reason: string | null
  claims_paused_until: string | null
  claims_pause_reason: string | null
  worker_package_version: string | null
  current_claims: number
  recent_throughput_5m: number
  anomaly_flags_in_window: number
}

interface AuditRow {
  id: number
  user_id: number
  action: string
  target_type: string | null
  target_id: string | null
  ip: string | null
  meta: Record<string, unknown> | null
  created_at: string
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
  request_align_existing_text?: boolean
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
            {row.request_align_existing_text ? (
              <span className="admin-lyrics-goal__flag">
                {t(
                  'admin.tasks.lyricsIntent.alignExisting',
                )}
              </span>
            ) : null}
            {!row.request_with_sync &&
            !row.request_bypass_cache &&
            !row.request_align_existing_text ? (
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

  const [typesPeriodHours, setTypesPeriodHours] = useState(() => {
    const raw = searchParams.get('typePeriod')
    const n = raw ? Number(raw) : NaN
    return Number.isFinite(n) && n >= 1 && n <= 168 ? n : 24
  })
  const taskTypes = useQuery({
    queryKey: ['admin', 'tasks', 'types', typesPeriodHours],
    queryFn: () => adminApi.tasksListTypes(typesPeriodHours),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })
  const workers = useQuery({
    queryKey: ['admin', 'tasks', 'workers'],
    queryFn: () => adminApi.tasksListWorkers(),
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
  })
  const audit = useQuery({
    queryKey: ['admin', 'tasks', 'audit'],
    queryFn: () =>
      adminApi.tasksListAudit({
        page: 1,
        size: 50,
        action_prefix: 'tasks.',
      }),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })
  const allowedTasks = useQuery({
    queryKey: ['admin', 'tasks', 'allowed'],
    queryFn: () => adminApi.tasksListAllowed(),
    staleTime: 60_000,
  })

  const [typeFilter, setTypeFilter] = useState(
    () => searchParams.get('typeFilter') ?? '',
  )
  const [typeKindFilter, setTypeKindFilter] = useState<
    'all' | 'taskiq' | 'compute' | 'mixed' | 'paused'
  >(
    () =>
      (searchParams.get('typeKind') as
        | 'all'
        | 'taskiq'
        | 'compute'
        | 'mixed'
        | 'paused'
        | null) || 'all',
  )
  const [typeSort, setTypeSort] = useState<
    'volume' | 'name' | 'failed' | 'avg' | 'paused'
  >(
    () =>
      (searchParams.get('typeSort') as
        | 'volume'
        | 'name'
        | 'failed'
        | 'avg'
        | 'paused'
        | null) || 'volume',
  )

  useEffect(() => {
    setSearchParams((params) => {
      const out = new URLSearchParams(params)
      const pairs: Array<[string, string]> = [
        ['typeFilter', typeFilter],
        [
          'typeKind',
          typeKindFilter === 'all' ? '' : typeKindFilter,
        ],
        ['typeSort', typeSort === 'volume' ? '' : typeSort],
        [
          'typePeriod',
          typesPeriodHours === 24 ? '' : String(typesPeriodHours),
        ],
      ]
      for (const [k, v] of pairs) {
        if (v) out.set(k, v)
        else out.delete(k)
      }
      return out
    })
  }, [
    typeFilter,
    typeKindFilter,
    typeSort,
    typesPeriodHours,
    setSearchParams,
  ])

  const wsRef = useRef<AdminWs | null>(null)
  const lastInvalidateRef = useRef<number>(0)
  useEffect(() => {
    const ws = new AdminWs({
      onEvent: (msg) => {
        if (msg?.channel !== 'dispatcher') return
        const now = Date.now()
        if (now - lastInvalidateRef.current < 500) return
        lastInvalidateRef.current = now
        qc.invalidateQueries({
          queryKey: ['admin', 'tasks', 'types'],
        })
        qc.invalidateQueries({
          queryKey: ['admin', 'tasks', 'overview'],
        })
        qc.invalidateQueries({
          queryKey: ['admin', 'tasks', 'workers'],
        })
        qc.invalidateQueries({
          queryKey: ['admin', 'tasks', 'background-jobs'],
        })
      },
    })
    wsRef.current = ws
    ws.subscribe('dispatcher')
    ws.connect()
    return () => {
      ws.unsubscribe('dispatcher')
      ws.close()
      wsRef.current = null
    }
  }, [qc])

  const pauseTypeMutation = useMutation({
    mutationFn: (params: {
      name: string
      reason?: string
      drain?: boolean
    }) =>
      adminApi.tasksPauseType(params.name, {
        reason: params.reason,
        drain: params.drain,
      }),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'types'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'audit'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'background-jobs'],
      })
    },
  })
  const resumeTypeMutation = useMutation({
    mutationFn: (name: string) => adminApi.tasksResumeType(name),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'types'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'audit'],
      })
    },
  })

  const [pauseDialog, setPauseDialog] = useState<{
    name: string
  } | null>(null)
  const [pauseReason, setPauseReason] = useState('')
  const [pauseDrain, setPauseDrain] = useState(false)
  const affectedPreview = useQuery({
    queryKey: [
      'admin',
      'tasks',
      'affected',
      pauseDialog?.name ?? '',
    ],
    queryFn: () =>
      pauseDialog
        ? adminApi.tasksAffectedPreview(pauseDialog.name)
        : Promise.resolve({ background_jobs: 0, compute_jobs: 0 }),
    enabled: !!pauseDialog,
    staleTime: 1000,
  })
  const handlePauseType = (name: string) => {
    setPauseDialog({ name })
    setPauseReason('')
    setPauseDrain(false)
  }
  const submitPause = () => {
    if (!pauseDialog) return
    pauseTypeMutation.mutate(
      {
        name: pauseDialog.name,
        reason: pauseReason || undefined,
        drain: pauseDrain,
      },
      {
        onSuccess: (data) => {
          if (data.drained) {
            showIsland({
              kind: 'toast',
              title: t('admin.tasks.dispatcher.drainedToast', {
                bg: data.drained.background_jobs,
                compute: data.drained.compute_jobs,
                defaultValue:
                  'Отменено: bg={{bg}}, compute={{compute}}',
              }),
              durationMs: 3500,
            })
          }
          setPauseDialog(null)
        },
      },
    )
  }
  const handleResumeType = (name: string) => {
    resumeTypeMutation.mutate(name)
  }

  const [purgeBgOpen, setPurgeBgOpen] = useState(false)
  const [purgeBgHours, setPurgeBgHours] = useState(24)
  const [purgeBgStatuses, setPurgeBgStatuses] = useState<string[]>([
    'done',
    'failed',
    'failed_terminal',
    'cancelled',
  ])
  const [purgeBgName, setPurgeBgName] = useState('')
  const purgeBgMutation = useMutation({
    mutationFn: (params: {
      older_than_hours: number
      statuses: string[]
      name?: string
    }) => adminApi.tasksPurgeBackgroundJobs(params),
    onSuccess: (data) => {
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'background-jobs'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'overview'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'audit'],
      })
      showIsland({
        kind: 'toast',
        title: t('admin.tasks.dispatcher.purgeBgDone', {
          count: data.deleted,
          defaultValue: 'Удалено: {{count}} строк',
        }),
        durationMs: 3000,
      })
      setPurgeBgOpen(false)
    },
    onError: () => {
      showIsland({
        kind: 'error',
        title: t('admin.tasks.dispatcher.purgeBgFailed', {
          defaultValue: 'Не удалось очистить очередь',
        }),
        durationMs: 4000,
      })
    },
  })
  const handlePurgeBg = async () => {
    if (purgeBgStatuses.length === 0) return
    const ok = await showConfirm(
      t('admin.tasks.dispatcher.purgeBgConfirm', {
        defaultValue:
          'Жёстко удалить выбранные строки background_jobs старше ' +
          'выбранного возраста? Действие необратимо.',
      }),
      { danger: true },
    )
    if (!ok) return
    purgeBgMutation.mutate({
      older_than_hours: purgeBgHours,
      statuses: purgeBgStatuses,
      name: purgeBgName.trim() || undefined,
    })
  }
  const purgeComputeMutation = useMutation({
    mutationFn: (params: {
      older_than_hours: number
      status: string
    }) => adminApi.tasksPurgeComputeJobs(params),
    onSuccess: (data) => {
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'overview'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'audit'],
      })
      showIsland({
        kind: 'toast',
        title: t('admin.tasks.dispatcher.purgeComputeDone', {
          count: data.deleted,
          defaultValue: 'Compute jobs удалено: {{count}}',
        }),
        durationMs: 3000,
      })
    },
  })

  const [runOpen, setRunOpen] = useState(false)
  const [runName, setRunName] = useState<string>('')
  const [runPayload, setRunPayload] = useState<string>('{}')
  const runMutation = useMutation({
    mutationFn: (params: {
      name: string
      payload: Record<string, unknown>
    }) =>
      adminApi.tasksManualEnqueue({
        task_name: params.name,
        payload: params.payload,
      }),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'background-jobs'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'types'],
      })
      qc.invalidateQueries({
        queryKey: ['admin', 'tasks', 'audit'],
      })
      showIsland({
        kind: 'toast',
        title: t('admin.tasks.dispatcher.runDone', {
          defaultValue: 'Задача поставлена в очередь',
        }),
        durationMs: 3000,
      })
      setRunOpen(false)
    },
    onError: (err: Error) => {
      showIsland({
        kind: 'error',
        title: t('admin.tasks.dispatcher.runFailed', {
          message: err.message,
          defaultValue: 'Не удалось запустить: {{message}}',
        }),
        durationMs: 5000,
      })
    },
  })
  const handleRunManual = () => {
    if (!runName) {
      showIsland({
        kind: 'error',
        title: t('admin.tasks.dispatcher.runNoTask', {
          defaultValue: 'Выберите задачу',
        }),
        durationMs: 2500,
      })
      return
    }
    let parsed: Record<string, unknown> = {}
    try {
      const trimmed = runPayload.trim()
      parsed = trimmed ? JSON.parse(trimmed) : {}
      if (typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('payload must be a JSON object')
      }
    } catch (e) {
      showIsland({
        kind: 'error',
        title: t('admin.tasks.dispatcher.runBadJson', {
          message: (e as Error).message,
          defaultValue: 'Некорректный JSON: {{message}}',
        }),
        durationMs: 4500,
      })
      return
    }
    runMutation.mutate({ name: runName, payload: parsed })
  }

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
      <nav
        className="admin-toolbar admin-dispatcher-nav"
        aria-label={
          t('admin.tasks.dispatcher.navAria', {
            defaultValue: 'Разделы диспетчера',
          }) as string
        }
      >
        <a className="admin-link" href="#dispatcher-overview">
          {t('admin.tasks.overview.title')}
        </a>
        <a className="admin-link" href="#dispatcher-types">
          {t('admin.tasks.dispatcher.navTypes', {
            defaultValue: 'Типы',
          })}
        </a>
        <a className="admin-link" href="#dispatcher-bg">
          {t('admin.tasks.dispatcher.navBg', {
            defaultValue: 'Background jobs',
          })}
        </a>
        <a className="admin-link" href="#dispatcher-compute">
          {t('admin.tasks.dispatcher.navCompute', {
            defaultValue: 'Compute',
          })}
        </a>
        <a className="admin-link" href="#dispatcher-schedules">
          {t('admin.tasks.dispatcher.navSchedules', {
            defaultValue: 'Schedules',
          })}
        </a>
        <a className="admin-link" href="#dispatcher-workers">
          {t('admin.tasks.dispatcher.navWorkers', {
            defaultValue: 'Воркеры',
          })}
        </a>
        <a className="admin-link" href="#dispatcher-audit">
          {t('admin.tasks.dispatcher.navAudit', {
            defaultValue: 'Аудит',
          })}
        </a>
      </nav>
      <section className="admin-card" id="dispatcher-overview">
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
      <section className="admin-card" id="dispatcher-types">
        <div className="admin-toolbar">
          <h2 style={{ flex: 1 }}>
            {t('admin.tasks.dispatcher.title', {
              defaultValue:
                'Диспетчер: типы задач, пауза, ручной запуск',
            })}
          </h2>
          <MotionPress
            variant="primary"
            haptic="light"
            onClick={() => setRunOpen(true)}
          >
            {t('admin.tasks.dispatcher.runButton', {
              defaultValue: 'Запустить задачу…',
            })}
          </MotionPress>
          <MotionPress
            variant="danger"
            haptic="medium"
            onClick={() => setPurgeBgOpen(true)}
          >
            {t('admin.tasks.dispatcher.purgeButton', {
              defaultValue: 'Очистить background_jobs…',
            })}
          </MotionPress>
        </div>
        <p className="admin-card__sub">
          {t('admin.tasks.dispatcher.hint', {
            defaultValue:
              'Сводка по типу задач за окно. Пауза останавливает ' +
              'только новые планирования: запущенные задачи ' +
              'завершатся сами. Все действия логируются в audit.',
          })}
        </p>
        <div className="admin-toolbar">
          <label className="admin-field">
            <span>
              {t('admin.tasks.dispatcher.periodLabel', {
                defaultValue: 'Окно, ч',
              })}
            </span>
            <select
              value={typesPeriodHours}
              onChange={(e) =>
                setTypesPeriodHours(Number(e.target.value))
              }
            >
              <option value={1}>1</option>
              <option value={6}>6</option>
              <option value={24}>24</option>
              <option value={72}>72</option>
              <option value={168}>168</option>
            </select>
          </label>
          <label className="admin-field">
            <span>
              {t('admin.tasks.dispatcher.kindLabel', {
                defaultValue: 'Слой',
              })}
            </span>
            <select
              value={typeKindFilter}
              onChange={(e) =>
                setTypeKindFilter(
                  e.target.value as typeof typeKindFilter,
                )
              }
            >
              <option value="all">all</option>
              <option value="taskiq">taskiq</option>
              <option value="compute">compute</option>
              <option value="mixed">mixed</option>
              <option value="paused">paused</option>
            </select>
          </label>
          <label className="admin-field">
            <span>
              {t('admin.tasks.dispatcher.sortLabel', {
                defaultValue: 'Сорт.',
              })}
            </span>
            <select
              value={typeSort}
              onChange={(e) =>
                setTypeSort(e.target.value as typeof typeSort)
              }
            >
              <option value="volume">volume</option>
              <option value="failed">failed</option>
              <option value="avg">avg duration</option>
              <option value="name">name</option>
              <option value="paused">paused first</option>
            </select>
          </label>
          <label className="admin-field" style={{ flex: 1 }}>
            <span>
              {t('admin.tasks.dispatcher.filterLabel', {
                defaultValue: 'Имя содержит',
              })}
            </span>
            <input
              type="text"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              placeholder="repair_track_playback"
            />
          </label>
        </div>
        {taskTypes.isError && (
          <p className="admin-error" role="alert">
            {t('admin.tasks.dispatcher.loadFailed', {
              defaultValue: 'Не удалось загрузить статистику типов',
            })}
          </p>
        )}
        <DataTable<TaskTypeRow>
          enableSorting
          columns={[
            {
              header: t('admin.tasks.dispatcher.cols.name', {
                defaultValue: 'Имя',
              }) as string,
              accessorKey: 'name',
              cell: (i) => (
                <span className="admin-mono">
                  {i.row.original.name}
                </span>
              ),
            },
            {
              header: t('admin.tasks.dispatcher.cols.kind', {
                defaultValue: 'Слой',
              }) as string,
              accessorKey: 'kind',
            },
            {
              header: t('admin.tasks.dispatcher.cols.paused', {
                defaultValue: 'Пауза',
              }) as string,
              id: 'paused',
              accessorFn: (row) => (row.paused ? 'paused' : ''),
              cell: (i) =>
                i.row.original.paused ? (
                  <StatusPill kind="warn">paused</StatusPill>
                ) : (
                  <span className="admin-card__sub">—</span>
                ),
            },
            {
              header: t('admin.tasks.dispatcher.cols.total', {
                defaultValue: 'Всего',
              }) as string,
              id: 'total',
              accessorFn: (row) =>
                Object.values(row.by_status).reduce(
                  (a, b) => a + (b || 0),
                  0,
                ),
            },
            {
              header: t('admin.tasks.dispatcher.cols.flight', {
                defaultValue: 'В работе',
              }) as string,
              id: 'flight',
              accessorFn: (row) =>
                (row.by_status.running || 0) +
                (row.by_status.queued || 0) +
                (row.by_status.claimed || 0) +
                (row.by_status.cancelling || 0),
              cell: (i) => {
                const s = i.row.original.by_status
                const chips: Array<[string, number, StatusKind]> = [
                  ['queued', s.queued || 0, 'unknown'],
                  ['running', s.running || 0, 'ok'],
                  ['claimed', s.claimed || 0, 'ok'],
                  ['cancelling', s.cancelling || 0, 'warn'],
                ]
                const visible = chips.filter(([, n]) => n > 0)
                if (!visible.length)
                  return (
                    <span className="admin-card__sub">—</span>
                  )
                return (
                  <div className="admin-toolbar admin-toolbar--compact">
                    {visible.map(([label, n, kind]) => (
                      <StatusPill key={label} kind={kind}>
                        {label}: {n}
                      </StatusPill>
                    ))}
                  </div>
                )
              },
            },
            {
              header: t('admin.tasks.dispatcher.cols.schedules', {
                defaultValue: 'Расп.',
              }) as string,
              id: 'schedules',
              accessorFn: (row) =>
                (row.schedules || [])
                  .map((s) =>
                    s.enabled ? s.cron : `(${s.cron})`,
                  )
                  .join(' '),
              cell: (i) => {
                const items = i.row.original.schedules || []
                if (!items.length)
                  return (
                    <span className="admin-card__sub">—</span>
                  )
                return (
                  <div className="admin-toolbar admin-toolbar--compact">
                    {items.map((s) => (
                      <StatusPill
                        key={s.id}
                        kind={s.enabled ? 'ok' : 'warn'}
                      >
                        {s.cron}
                      </StatusPill>
                    ))}
                  </div>
                )
              },
            },
            {
              header: t('admin.tasks.dispatcher.cols.trend', {
                defaultValue: 'Тренд',
              }) as string,
              id: 'trend',
              enableSorting: false,
              cell: (i) => (
                <TaskTypeTimeseriesCell
                  name={i.row.original.name}
                  periodHours={typesPeriodHours}
                />
              ),
            },
            {
              header: t('admin.tasks.dispatcher.cols.donePeriod', {
                defaultValue: 'Готово (окно)',
              }) as string,
              accessorKey: 'done_period',
            },
            {
              header: t('admin.tasks.dispatcher.cols.failedPeriod', {
                defaultValue: 'Ошибок (окно)',
              }) as string,
              accessorKey: 'failed_period',
            },
            {
              header: t('admin.tasks.dispatcher.cols.avg', {
                defaultValue: 'Avg, мс',
              }) as string,
              accessorKey: 'avg_duration_ms',
              cell: (i) =>
                i.row.original.avg_duration_ms ?? '–',
            },
            {
              header: '',
              id: 'actions',
              enableSorting: false,
              cell: (i) => (
                <div className="admin-toolbar admin-toolbar--compact">
                  {i.row.original.paused ? (
                    <MotionPress
                      variant="primary"
                      haptic="light"
                      onClick={() =>
                        handleResumeType(i.row.original.name)
                      }
                      disabled={resumeTypeMutation.isPending}
                    >
                      {t('admin.tasks.dispatcher.actions.resume', {
                        defaultValue: 'Возобновить',
                      })}
                    </MotionPress>
                  ) : (
                    <MotionPress
                      variant="danger"
                      haptic="medium"
                      onClick={() =>
                        handlePauseType(i.row.original.name)
                      }
                      disabled={pauseTypeMutation.isPending}
                    >
                      {t('admin.tasks.dispatcher.actions.pause', {
                        defaultValue: 'Пауза',
                      })}
                    </MotionPress>
                  )}
                  <MotionPress
                    variant="ghost"
                    haptic="selection"
                    className="admin-link"
                    onClick={() => {
                      setRunName(i.row.original.name)
                      setRunPayload('{}')
                      setRunOpen(true)
                    }}
                  >
                    {t('admin.tasks.dispatcher.actions.run', {
                      defaultValue: 'Запустить',
                    })}
                  </MotionPress>
                  <MotionPress
                    variant="ghost"
                    haptic="selection"
                    className="admin-link"
                    onClick={() =>
                      setBgPreset({ name: i.row.original.name })
                    }
                  >
                    {t('admin.tasks.dispatcher.actions.filterBg', {
                      defaultValue: 'В Jobs',
                    })}
                  </MotionPress>
                </div>
              ),
            },
          ]}
          rows={(
            (taskTypes.data?.items || []) as TaskTypeRow[]
          )
            .filter((row) => {
              if (typeKindFilter === 'paused' && !row.paused)
                return false
              if (
                typeKindFilter !== 'all' &&
                typeKindFilter !== 'paused' &&
                row.kind !== typeKindFilter
              )
                return false
              if (
                typeFilter &&
                !row.name
                  .toLowerCase()
                  .includes(typeFilter.toLowerCase())
              )
                return false
              return true
            })
            .sort((a, b) => {
              if (typeSort === 'name')
                return a.name.localeCompare(b.name)
              if (typeSort === 'failed')
                return b.failed_period - a.failed_period
              if (typeSort === 'avg')
                return (
                  (b.avg_duration_ms || 0) -
                  (a.avg_duration_ms || 0)
                )
              if (typeSort === 'paused')
                return Number(b.paused) - Number(a.paused)
              const aT = Object.values(a.by_status).reduce(
                (x, y) => x + (y || 0),
                0,
              )
              const bT = Object.values(b.by_status).reduce(
                (x, y) => x + (y || 0),
                0,
              )
              return bT - aT
            })}
        />
      </section>
      <section className="admin-card" id="dispatcher-bg">
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
                            {live.track_id ?? '—'}
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
                            {live.progress_id ?? '—'}
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
      <section className="admin-card" id="dispatcher-compute">
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
      <section className="admin-card" id="dispatcher-schedules">
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
      <section className="admin-card" id="dispatcher-workers">
        <div className="admin-toolbar">
          <h2 style={{ flex: 1 }}>
            {t('admin.tasks.dispatcher.workers.title', {
              defaultValue: 'Воркеры',
            })}
          </h2>
          {workers.data?.scheduler_leader.owner && (
            <span className="admin-card__sub admin-mono">
              {t('admin.tasks.dispatcher.workers.leader', {
                defaultValue: 'Scheduler leader:',
              })}{' '}
              {workers.data.scheduler_leader.owner.slice(0, 12)} (
              {workers.data.scheduler_leader.ttl_seconds ?? '–'}s)
            </span>
          )}
        </div>
        <p className="admin-card__sub">
          {t('admin.tasks.dispatcher.workers.hint', {
            defaultValue:
              'Compute-воркеры из таблицы compute_workers + лидер ' +
              'scheduler-а из Redis. last_seen старше нескольких ' +
              'минут означает что воркер скорее всего мёртв.',
          })}
        </p>
        {workers.isError && (
          <p className="admin-error" role="alert">
            {t('admin.tasks.dispatcher.workers.loadFailed', {
              defaultValue: 'Не удалось получить список воркеров',
            })}
          </p>
        )}
        <DataTable<WorkerRow>
          enableSorting
          columns={[
            {
              header: 'ID',
              accessorKey: 'id',
              cell: (i) => (
                <span className="admin-mono">
                  {i.row.original.id}
                </span>
              ),
            },
            { header: 'name', accessorKey: 'name' },
            { header: 'profile', accessorKey: 'profile' },
            {
              header: 'active',
              accessorKey: 'active',
              cell: (i) =>
                i.row.original.active ? (
                  <StatusPill kind="ok">on</StatusPill>
                ) : (
                  <StatusPill kind="warn">off</StatusPill>
                ),
            },
            {
              header: 'max',
              accessorKey: 'max_concurrent_jobs',
            },
            {
              header: t(
                'admin.tasks.dispatcher.workers.cols.claims',
                { defaultValue: 'В работе' },
              ) as string,
              accessorKey: 'current_claims',
              cell: (i) => {
                const n = i.row.original.current_claims
                const max = i.row.original.max_concurrent_jobs
                if (!n)
                  return (
                    <span className="admin-card__sub">0</span>
                  )
                return (
                  <StatusPill
                    kind={n >= max ? 'warn' : 'ok'}
                  >
                    {n}/{max}
                  </StatusPill>
                )
              },
            },
            {
              header: t(
                'admin.tasks.dispatcher.workers.cols.throughput',
                { defaultValue: '5м, OK' },
              ) as string,
              accessorKey: 'recent_throughput_5m',
            },
            {
              header: t(
                'admin.tasks.dispatcher.workers.cols.anomaly',
                { defaultValue: 'Anomaly' },
              ) as string,
              accessorKey: 'anomaly_flags_in_window',
              cell: (i) => {
                const n = i.row.original.anomaly_flags_in_window
                if (!n)
                  return (
                    <span className="admin-card__sub">0</span>
                  )
                return (
                  <StatusPill
                    kind={n >= 3 ? 'error' : 'warn'}
                  >
                    {n}
                  </StatusPill>
                )
              },
            },
            {
              header: 'last_seen',
              accessorKey: 'last_seen_at',
              cell: (i) =>
                i.row.original.last_seen_at
                  ? new Date(
                      i.row.original.last_seen_at,
                    ).toLocaleString()
                  : '–',
            },
            {
              header: 'last_ip',
              accessorKey: 'last_ip',
              cell: (i) => i.row.original.last_ip || '–',
            },
            {
              header: 'state',
              id: 'state',
              accessorFn: (row) =>
                row.revoked_at
                  ? 'revoked'
                  : row.suspended_until
                    ? 'suspended'
                    : row.claims_paused_until
                      ? 'claims_paused'
                      : 'ok',
              cell: (i) => {
                const v = String(i.getValue())
                if (v === 'ok')
                  return <StatusPill kind="ok">ok</StatusPill>
                return (
                  <StatusPill kind="warn">{v}</StatusPill>
                )
              },
            },
            {
              header: 'version',
              accessorKey: 'worker_package_version',
              cell: (i) =>
                i.row.original.worker_package_version || '–',
            },
          ]}
          rows={(workers.data?.workers || []) as WorkerRow[]}
        />
      </section>
      <section className="admin-card" id="dispatcher-audit">
        <h2>
          {t('admin.tasks.dispatcher.audit.title', {
            defaultValue: 'Аудит: действия админов по задачам',
          })}
        </h2>
        <p className="admin-card__sub">
          {t('admin.tasks.dispatcher.audit.hint', {
            defaultValue:
              'Последние 50 записей admin_actions_log с префиксом ' +
              'tasks.* (отмены, retry, pause/resume, purge, ' +
              'manual run).',
          })}
        </p>
        {audit.isError && (
          <p className="admin-error" role="alert">
            {t('admin.tasks.dispatcher.audit.loadFailed', {
              defaultValue: 'Не удалось загрузить аудит',
            })}
          </p>
        )}
        <DataTable<AuditRow>
          enableSorting
          columns={[
            {
              header: 'when',
              accessorKey: 'created_at',
              cell: (i) => {
                try {
                  return new Date(
                    i.row.original.created_at,
                  ).toLocaleString()
                } catch {
                  return String(i.row.original.created_at)
                }
              },
            },
            { header: 'user', accessorKey: 'user_id' },
            {
              header: 'action',
              accessorKey: 'action',
              cell: (i) => (
                <span className="admin-mono">
                  {i.row.original.action}
                </span>
              ),
            },
            {
              header: 'target',
              id: 'target',
              accessorFn: (row) =>
                `${row.target_type ?? '–'}:${row.target_id ?? '–'}`,
            },
            {
              header: 'ip',
              accessorKey: 'ip',
              cell: (i) => i.row.original.ip || '–',
            },
            {
              header: 'meta',
              id: 'meta',
              accessorFn: (row) =>
                row.meta ? JSON.stringify(row.meta) : '',
              cell: (i) => {
                const v = String(i.getValue())
                return v.length > 80 ? v.slice(0, 80) + '…' : v
              },
            },
          ]}
          rows={(audit.data?.items || []) as AuditRow[]}
        />
      </section>
      {pauseDialog && (
        <div
          className="admin-modal-overlay"
          role="dialog"
          aria-modal="true"
          onClick={() => setPauseDialog(null)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="admin-toolbar">
              <h3>
                {t('admin.tasks.dispatcher.pauseDialog.title', {
                  name: pauseDialog.name,
                  defaultValue:
                    'Пауза типа: {{name}}',
                })}
              </h3>
              <MotionPress
                variant="ghost"
                className="admin-link"
                onClick={() => setPauseDialog(null)}
              >
                <Icon name="close" />
              </MotionPress>
            </div>
            <p className="admin-card__sub">
              {t('admin.tasks.dispatcher.pauseDialog.hint', {
                defaultValue:
                  'Пауза останавливает новые планирования. ' +
                  'Включи «drain», чтобы дополнительно отменить ' +
                  'уже поставленные и текущие задачи этого типа ' +
                  '(только background_jobs и compute_jobs).',
              })}
            </p>
            <div className="admin-kpi-row">
              <div className="admin-kpi">
                <div className="admin-kpi__label">
                  {t(
                    'admin.tasks.dispatcher.pauseDialog.bgInflight',
                    { defaultValue: 'BG активные' },
                  )}
                </div>
                <div className="admin-kpi__value">
                  {affectedPreview.data?.background_jobs ?? '…'}
                </div>
              </div>
              <div className="admin-kpi">
                <div className="admin-kpi__label">
                  {t(
                    'admin.tasks.dispatcher.pauseDialog.computeInflight',
                    { defaultValue: 'Compute активные' },
                  )}
                </div>
                <div className="admin-kpi__value">
                  {affectedPreview.data?.compute_jobs ?? '…'}
                </div>
              </div>
            </div>
            <label className="admin-field">
              <span>
                {t(
                  'admin.tasks.dispatcher.pauseDialog.reasonLabel',
                  { defaultValue: 'Причина (опц.)' },
                )}
              </span>
              <input
                type="text"
                value={pauseReason}
                onChange={(e) => setPauseReason(e.target.value)}
                placeholder="перегрузка / hotfix / ..."
                maxLength={200}
              />
            </label>
            <label className="admin-checkbox">
              <input
                type="checkbox"
                checked={pauseDrain}
                onChange={(e) =>
                  setPauseDrain(e.target.checked)
                }
              />
              <span>
                {t(
                  'admin.tasks.dispatcher.pauseDialog.drainLabel',
                  {
                    bg:
                      affectedPreview.data?.background_jobs ?? 0,
                    compute:
                      affectedPreview.data?.compute_jobs ?? 0,
                    defaultValue:
                      'Drain: также отменить уже активные ' +
                      '({{bg}} + {{compute}})',
                  },
                )}
              </span>
            </label>
            <div className="admin-toolbar">
              <MotionPress
                variant="ghost"
                className="admin-link"
                onClick={() => setPauseDialog(null)}
              >
                {t(
                  'admin.tasks.dispatcher.pauseDialog.cancel',
                  { defaultValue: 'Отмена' },
                )}
              </MotionPress>
              <MotionPress
                variant="danger"
                onClick={submitPause}
                disabled={pauseTypeMutation.isPending}
              >
                {pauseDrain
                  ? t(
                      'admin.tasks.dispatcher.pauseDialog.submitDrain',
                      {
                        defaultValue:
                          'Пауза + drain',
                      },
                    )
                  : t(
                      'admin.tasks.dispatcher.pauseDialog.submit',
                      { defaultValue: 'Только пауза' },
                    )}
              </MotionPress>
            </div>
          </div>
        </div>
      )}
      {runOpen && (
        <div
          className="admin-modal-overlay"
          role="dialog"
          aria-modal="true"
          onClick={() => setRunOpen(false)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="admin-toolbar">
              <h3>
                {t('admin.tasks.dispatcher.run.title', {
                  defaultValue: 'Запуск задачи вручную',
                })}
              </h3>
              <MotionPress
                variant="ghost"
                className="admin-link"
                onClick={() => setRunOpen(false)}
              >
                <Icon name="close" />
              </MotionPress>
            </div>
            <p className="admin-card__sub">
              {t('admin.tasks.dispatcher.run.hint', {
                defaultValue:
                  'Доступен только белый список (см. ' +
                  '/tasks/allowed). Payload — JSON-объект, ' +
                  'будет передан как **kwargs.',
              })}
            </p>
            <label className="admin-field">
              <span>
                {t('admin.tasks.dispatcher.run.taskLabel', {
                  defaultValue: 'Задача',
                })}
              </span>
              <select
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
              >
                <option value="">—</option>
                {(allowedTasks.data?.tasks || []).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="admin-field">
              <span>
                {t('admin.tasks.dispatcher.run.payloadLabel', {
                  defaultValue: 'Payload (JSON)',
                })}
              </span>
              <textarea
                rows={8}
                className="admin-mono"
                value={runPayload}
                onChange={(e) => setRunPayload(e.target.value)}
              />
            </label>
            <div className="admin-toolbar">
              <MotionPress
                variant="ghost"
                className="admin-link"
                onClick={() => setRunOpen(false)}
              >
                {t('admin.tasks.dispatcher.run.cancel', {
                  defaultValue: 'Отмена',
                })}
              </MotionPress>
              <MotionPress
                variant="primary"
                onClick={handleRunManual}
                disabled={runMutation.isPending || !runName}
              >
                {t('admin.tasks.dispatcher.run.submit', {
                  defaultValue: 'Запустить',
                })}
              </MotionPress>
            </div>
          </div>
        </div>
      )}
      {purgeBgOpen && (
        <div
          className="admin-modal-overlay"
          role="dialog"
          aria-modal="true"
          onClick={() => setPurgeBgOpen(false)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="admin-toolbar">
              <h3>
                {t('admin.tasks.dispatcher.purge.title', {
                  defaultValue: 'Очистка background_jobs',
                })}
              </h3>
              <MotionPress
                variant="ghost"
                className="admin-link"
                onClick={() => setPurgeBgOpen(false)}
              >
                <Icon name="close" />
              </MotionPress>
            </div>
            <p className="admin-card__sub">
              {t('admin.tasks.dispatcher.purge.hint', {
                defaultValue:
                  'Удаление затрагивает только терминальные ' +
                  'статусы (done/failed/failed_terminal/cancelled). ' +
                  'Активные задачи защищены и не удаляются.',
              })}
            </p>
            <label className="admin-field">
              <span>
                {t('admin.tasks.dispatcher.purge.ageLabel', {
                  defaultValue: 'Старше, часов',
                })}
              </span>
              <input
                type="number"
                min={1}
                max={2160}
                value={purgeBgHours}
                onChange={(e) =>
                  setPurgeBgHours(Number(e.target.value) || 1)
                }
              />
            </label>
            <label className="admin-field">
              <span>
                {t('admin.tasks.dispatcher.purge.nameLabel', {
                  defaultValue: 'Имя (опционально)',
                })}
              </span>
              <input
                type="text"
                value={purgeBgName}
                onChange={(e) => setPurgeBgName(e.target.value)}
                placeholder="repair_track_playback_task"
              />
            </label>
            <fieldset className="admin-field">
              <legend>
                {t('admin.tasks.dispatcher.purge.statusesLabel', {
                  defaultValue: 'Статусы',
                })}
              </legend>
              {[
                'done',
                'failed',
                'failed_terminal',
                'cancelled',
              ].map((s) => (
                <label key={s} className="admin-checkbox">
                  <input
                    type="checkbox"
                    checked={purgeBgStatuses.includes(s)}
                    onChange={(e) =>
                      setPurgeBgStatuses((cur) =>
                        e.target.checked
                          ? [...cur, s]
                          : cur.filter((x) => x !== s),
                      )
                    }
                  />
                  <span className="admin-mono">{s}</span>
                </label>
              ))}
            </fieldset>
            <div className="admin-toolbar">
              <MotionPress
                variant="ghost"
                className="admin-link"
                onClick={() => setPurgeBgOpen(false)}
              >
                {t('admin.tasks.dispatcher.purge.cancel', {
                  defaultValue: 'Отмена',
                })}
              </MotionPress>
              <MotionPress
                variant="danger"
                onClick={handlePurgeBg}
                disabled={
                  purgeBgMutation.isPending ||
                  purgeBgStatuses.length === 0
                }
              >
                {t('admin.tasks.dispatcher.purge.submit', {
                  defaultValue: 'Удалить',
                })}
              </MotionPress>
            </div>
            <p className="admin-card__sub">
              {t('admin.tasks.dispatcher.purge.computeHint', {
                defaultValue:
                  'Compute-jobs (pending) очищаются отдельной ' +
                  'кнопкой на дашборде или через POST ' +
                  '/dashboard/compute-jobs/purge-pending.',
              })}
            </p>
            <div className="admin-toolbar">
              <MotionPress
                variant="ghost"
                className="admin-link"
                onClick={() =>
                  purgeComputeMutation.mutate({
                    older_than_hours: purgeBgHours,
                    status: 'pending',
                  })
                }
                disabled={purgeComputeMutation.isPending}
              >
                {t('admin.tasks.dispatcher.purge.computePending', {
                  hours: purgeBgHours,
                  defaultValue:
                    'Удалить compute_jobs(pending) старше {{hours}} ч',
                })}
              </MotionPress>
            </div>
          </div>
        </div>
      )}
      {activeJobId && (
        <LyricsJobDetail
          jobId={activeJobId}
          onClose={() => setActiveJobId(null)}
        />
      )}
    </div>
  )
}
