import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  computeWorkerPillKind,
  computeWorkerPillLabel,
  WORKER_ONLINE_MAX_AGE_SEC,
} from '../lib/computeWorkerLiveness'
import { adminApi, adminFetch } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { WorkerDetailDrawer } from '../components/widgets/WorkerDetailDrawer'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { WorkerOnboarding } from '../components/widgets/WorkerOnboarding'

interface WorkerRow {
  id: string
  name: string
  profile: string
  active: boolean
  suspended_reason: string | null
  suspended_until: string | null
  revoked_at: string | null
  allowed_ip_cidrs: string[]
  allowed_profiles: string[]
  max_concurrent_jobs: number
  last_seen_at: string | null
  last_ip: string | null
  created_at: string | null
  worker_package_version?: string | null
  claims_paused_until?: string | null
  claims_pause_reason?: string | null
}

interface TierAttempt {
  tier: string
  started_at: string
  finished_at?: string | null
  status: string
  error?: string | null
}

interface JobRow {
  id: string
  progress_id?: string
  track_id: number
  status: string
  profile: string
  current_tier: string | null
  tiers_planned: string[]
  tier_attempts: TierAttempt[]
  routed_to_worker: string | null
  pinned_worker_id?: string | null
  queue_priority?: number
  attempts: number
  duration_ms: number | null
  error: string | null
  created_at: string
  deadline_at?: string | null
  started_at?: string | null
}

interface GenericComputeJobRow {
  id: string
  job_type: string
  target_kind: string | null
  target_id: string | null
  status: string
  priority: number
  pinned_worker_id: string | null
  claimed_by: string | null
  attempts: number
  last_error: string | null
  created_at: string | null
}

function LyricsJobRoutingControls({
  job,
  workers,
  disabled,
  isPending,
  onApply,
  t,
}: {
  job: JobRow
  workers: WorkerRow[]
  disabled: boolean
  isPending: boolean
  onApply: (payload: {
    pinned_worker_id: string | null
    queue_priority: number
  }) => void
  t: TFunction
}) {
  const [pri, setPri] = useState(
    () => job.queue_priority ?? 0,
  )
  const [pin, setPin] = useState(
    () => job.pinned_worker_id ?? '',
  )
  useEffect(() => {
    setPri(job.queue_priority ?? 0)
    setPin(job.pinned_worker_id ?? '')
  }, [
    job.id,
    job.queue_priority,
    job.pinned_worker_id,
  ])
  const eligible = workers.filter(
    (w) => w.active && !w.revoked_at,
  )
  return (
    <div
      className="admin-toolbar"
      style={{
        flexWrap: 'wrap',
        gap: 6,
        alignItems: 'center',
      }}
    >
      <input
        type="number"
        aria-label={t(
          'admin.audioCompute.jobTable.priorityInput',
        )}
        value={pri}
        onChange={(e) =>
          setPri(Number(e.target.value))
        }
        disabled={disabled}
        style={{ width: 72 }}
      />
      <select
        aria-label={t(
          'admin.audioCompute.jobTable.pinWorker',
        )}
        value={pin}
        onChange={(e) =>
          setPin(e.target.value)
        }
        disabled={disabled}
        style={{ minWidth: 140 }}
      >
        <option value="">
          {t(
            'admin.audioCompute.jobTable.anyWorker',
          )}
        </option>
        {eligible.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name} ({w.id.slice(0, 6)})
          </option>
        ))}
      </select>
      <MotionPress
        variant="ghost"
        disabled={disabled || isPending}
        onClick={() =>
          onApply({
            pinned_worker_id: pin || null,
            queue_priority: pri,
          })
        }
      >
        {t(
          'admin.audioCompute.jobTable.applyRouting',
        )}
      </MotionPress>
    </div>
  )
}

function GenericComputeJobRoutingControls({
  row,
  workers,
  disabled,
  isPending,
  onApply,
  t,
}: {
  row: GenericComputeJobRow
  workers: WorkerRow[]
  disabled: boolean
  isPending: boolean
  onApply: (payload: {
    pinned_worker_id: string | null
    priority: number
    release_claim: boolean
  }) => void
  t: TFunction
}) {
  const [pri, setPri] = useState(
    () => row.priority ?? 0,
  )
  const [pin, setPin] = useState(
    () => row.pinned_worker_id ?? '',
  )
  const [release, setRelease] = useState(false)
  useEffect(() => {
    setPri(row.priority ?? 0)
    setPin(row.pinned_worker_id ?? '')
    setRelease(false)
  }, [
    row.id,
    row.priority,
    row.pinned_worker_id,
  ])
  const eligible = workers.filter(
    (w) => w.active && !w.revoked_at,
  )
  return (
    <div
      className="admin-toolbar"
      style={{
        flexWrap: 'wrap',
        gap: 6,
        alignItems: 'center',
      }}
    >
      <input
        type="number"
        aria-label={t(
          'admin.audioCompute.genericJobs.priority',
        )}
        value={pri}
        onChange={(e) =>
          setPri(Number(e.target.value))
        }
        disabled={disabled}
        style={{ width: 72 }}
      />
      <select
        aria-label={t(
          'admin.audioCompute.genericJobs.pin',
        )}
        value={pin}
        onChange={(e) =>
          setPin(e.target.value)
        }
        disabled={disabled}
        style={{ minWidth: 140 }}
      >
        <option value="">
          {t(
            'admin.audioCompute.jobTable.anyWorker',
          )}
        </option>
        {eligible.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name} ({w.id.slice(0, 6)})
          </option>
        ))}
      </select>
      {row.status === 'claimed' && (
        <label
          style={{
            display: 'inline-flex',
            gap: 6,
            alignItems: 'center',
          }}
        >
          <input
            type="checkbox"
            checked={release}
            onChange={(e) =>
              setRelease(e.target.checked)
            }
            disabled={disabled}
          />
          {t(
            'admin.audioCompute.genericJobs.releaseLease',
          )}
        </label>
      )}
      <MotionPress
        variant="ghost"
        disabled={disabled || isPending}
        onClick={() =>
          onApply({
            pinned_worker_id: pin || null,
            priority: pri,
            release_claim: release,
          })
        }
      >
        {t(
          'admin.audioCompute.jobTable.applyRouting',
        )}
      </MotionPress>
    </div>
  )
}

interface AuditRow {
  id: number
  worker_id: string | null
  ip: string | null
  action: string
  job_id: string | null
  status_code: number | null
  meta?: Record<string, unknown> | null
  created_at: string
}

interface SpeechKitStatus {
  enabled: boolean
  monthly_budget_rub: number
  monthly_spent_rub: number
  remaining_rub: number
  rate_rub_per_minute: number
  soft_per_job_limit_rub: number
  api_key_set: boolean
}

const ROUTING_MODES = [
  'auto',
  'force_local_cpu',
  'force_remote_gpu',
  'disabled',
]

const PROFILE_OPTIONS = [
  'cpu_light',
  'gpu_full',
  'catalog_only',
  'remote_whisper',
  'speechkit_paid',
]

const ALL_TIERS = [
  'catalog_only',
  'remote_whisper',
  'speechkit_paid',
]

const AUDIT_ACTION_FILTERS = [
  '',
  'auth_fail',
  'rate_limit_exceeded',
  'auto_suspend',
  'anomaly',
  'audio_sha_mismatch',
  'result_invalid',
  'result_ok',
  'result_fail',
]

function jobKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'done' || status === 'succeeded')
    return 'ok'
  if (
    status === 'failed' ||
    status === 'error' ||
    status === 'cancelled'
  )
    return 'error'
  if (
    status === 'queued' ||
    status === 'running' ||
    status === 'pending' ||
    status === 'claimed'
  )
    return 'warn'
  return 'unknown'
}

function fmtCidrs(
  values: string[],
  t: TFunction,
): string {
  if (!values || values.length === 0) {
    return '–'
  }
  if (values.includes('0.0.0.0/0')) {
    return t('admin.audioCompute.workerState.anyCidr')
  }
  return String(values.length)
}

function parseCidrInput(input: string): string[] {
  return input
    .split(/[\n,]+/)
    .map((piece) => piece.trim())
    .filter(Boolean)
}

function tierBadgeKind(
  status: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (status === 'success') return 'ok'
  if (status === 'fail' || status === 'gated')
    return 'error'
  if (status === 'queued' || status === 'running')
    return 'warn'
  if (status === 'miss') return 'warn'
  return 'unknown'
}

export function AudioComputeRoute() {
  const { t } = useTranslation()
  const { showConfirm } = useAdminPrompt()
  const qc = useQueryClient()

  const workers = useQuery({
    queryKey: ['admin', 'compute', 'workers'],
    queryFn: () =>
      adminFetch<WorkerRow[]>(
        '/audio-compute/workers',
      ),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })
  const [jobsSort, setJobsSort] = useState<
    'queue' | 'recent'
  >('queue')
  const jobs = useQuery({
    queryKey: ['admin', 'compute', 'jobs', jobsSort],
    queryFn: () =>
      adminFetch<JobRow[]>(
        `/audio-compute/jobs?sort=${jobsSort}`,
      ),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })
  const cancelJobMutation = useMutation({
    mutationFn: (id: string) =>
      adminApi.cancelComputeJob(id),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'jobs'],
      })
    },
  })
  const reapLeasesMutation = useMutation({
    mutationFn: () => adminApi.reapExpiredLyricsLeases(),
    onSuccess: (data) => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'jobs'],
      })
      setReapNotice(
        String(
          data.expired_leases_handled ?? 0,
        ),
      )
    },
    onError: () => {
      setReapNotice(null)
    },
  })
  const [progressToCancel, setProgressToCancel] = useState('')
  const [reapNotice, setReapNotice] = useState<
    string | null
  >(null)
  const cancelByProgressMutation = useMutation({
    mutationFn: (pid: string) =>
      adminApi.cancelComputeJobByProgress(
        pid.trim(),
      ),
    onSuccess: () => {
      setProgressToCancel('')
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'jobs'],
      })
    },
  })
  const patchLyricsRoutingMutation = useMutation({
    mutationFn: (args: {
      id: string
      pinned_worker_id: string | null
      queue_priority: number
    }) =>
      adminApi.patchLyricsJobRouting(args.id, {
        pinned_worker_id: args.pinned_worker_id,
        queue_priority: args.queue_priority,
      }),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'jobs'],
      })
    },
  })
  const genericJobs = useQuery({
    queryKey: ['admin', 'compute', 'generic-jobs'],
    queryFn: () =>
      adminApi.listGenericComputeJobs({
        limit: 100,
      }),
    refetchInterval: 20_000,
    refetchIntervalInBackground: false,
  })
  const patchGenericRoutingMutation = useMutation({
    mutationFn: (args: {
      id: string
      pinned_worker_id: string | null
      priority: number
      release_claim: boolean
    }) =>
      adminApi.patchGenericComputeJobRouting(
        args.id,
        {
          pinned_worker_id: args.pinned_worker_id,
          priority: args.priority,
          release_claim: args.release_claim,
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'generic-jobs'],
      })
    },
  })
  const [auditFilter, setAuditFilter] = useState('')
  const audit = useQuery({
    queryKey: [
      'admin',
      'compute',
      'audit',
      auditFilter,
    ],
    queryFn: () =>
      adminFetch<AuditRow[]>(
        auditFilter
          ? `/audio-compute/audit?action_filter=${encodeURIComponent(
              auditFilter,
            )}`
          : '/audio-compute/audit',
      ),
  })
  const routing = useQuery({
    queryKey: ['admin', 'compute', 'routing'],
    queryFn: () =>
      adminFetch<{ mode: string }>(
        '/audio-compute/routing',
      ),
  })
  const cascade = useQuery({
    queryKey: ['admin', 'compute', 'cascade'],
    queryFn: () =>
      adminFetch<{ cascade: string[] }>(
        '/audio-compute/cascade',
      ),
  })
  const speechkit = useQuery({
    queryKey: ['admin', 'compute', 'speechkit'],
    queryFn: () =>
      adminFetch<SpeechKitStatus>(
        '/audio-compute/speechkit',
      ),
    refetchInterval: 60_000,
  })

  const [newName, setNewName] = useState('')
  const [newProfile, setNewProfile] =
    useState('gpu_full')
  const [newCidrs, setNewCidrs] = useState(
    '127.0.0.1/32',
  )
  const [newAllowedProfiles, setNewAllowedProfiles] =
    useState('gpu_full')
  const [newConcurrency, setNewConcurrency] = useState(1)
  const [acceptOpen, setAcceptOpen] = useState(false)
  const [showSecret, setShowSecret] = useState<
    string | null
  >(null)
  const [traceJobId, setTraceJobId] = useState<
    string | null
  >(null)
  const [pendingCascade, setPendingCascade] = useState<
    string[] | null
  >(null)
  const [drawerWorkerId, setDrawerWorkerId] = useState<
    string | null
  >(null)
  const workersList = useMemo(
    () =>
      (workers.data as WorkerRow[] | undefined) || [],
    [workers.data],
  )
  const drawerWorker = useMemo(
    () =>
      drawerWorkerId
        ? workersList.find(
            (w) => w.id === drawerWorkerId,
          ) || null
        : null,
    [drawerWorkerId, workersList],
  )
  const backendBaseUrl = useMemo(() => {
    if (typeof window === 'undefined')
      return 'http://localhost:8000'
    const { protocol, host } = window.location
    return `${protocol}//${host}`
  }, [])

  const cidrParsed = useMemo(
    () => parseCidrInput(newCidrs),
    [newCidrs],
  )
  const cidrIsOpen =
    cidrParsed.includes('0.0.0.0/0') ||
    cidrParsed.includes('::/0')

  const traceJob = useMemo(() => {
    if (!traceJobId) return null
    const list = (jobs.data as JobRow[] | undefined) || []
    return (
      list.find((row) => row.id === traceJobId) || null
    )
  }, [jobs.data, traceJobId])

  const createWorker = useMutation({
    mutationFn: (payload: {
      name: string
      profile: string
      allowed_ip_cidrs: string[]
      allowed_profiles: string[]
      max_concurrent_jobs: number
      accept_open_allowlist: boolean
    }) =>
      adminFetch<{
        id: string
        secret: string
      }>('/audio-compute/workers', {
        method: 'POST',
        body: payload,
      }),
    onSuccess: (data) => {
      setShowSecret(data.secret)
      setNewName('')
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
    },
  })

  const deleteRevokedWorker = useMutation({
    mutationFn: (workerId: string) =>
      adminFetch(
        `/audio-compute/workers/${encodeURIComponent(
          workerId,
        )}`,
        { method: 'DELETE' },
      ),
    onSuccess: (_d, workerId) => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
      setDrawerWorkerId((cur) =>
        cur === workerId ? null : cur,
      )
    },
  })

  const setMode = useMutation({
    mutationFn: (mode: string) =>
      adminFetch<{ mode: string }>(
        '/audio-compute/routing',
        { method: 'PATCH', body: { mode } },
      ),
    onSettled: () =>
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'routing'],
      }),
  })

  const setCascade = useMutation({
    mutationFn: (next: string[]) =>
      adminFetch<{ cascade: string[] }>(
        '/audio-compute/cascade',
        {
          method: 'PATCH',
          body: { cascade: next },
        },
      ),
    onSettled: () => {
      setPendingCascade(null)
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'cascade'],
      })
    },
  })

  const resetSpend = useMutation({
    mutationFn: () =>
      adminFetch<SpeechKitStatus>(
        '/audio-compute/speechkit/reset_spent',
        { method: 'POST', body: {} },
      ),
    onSettled: () =>
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'speechkit'],
      }),
  })

  const liveCascade =
    pendingCascade ??
    cascade.data?.cascade ??
    ALL_TIERS

  const moveTier = (
    tier: string,
    direction: -1 | 1,
  ) => {
    const current = [...liveCascade]
    const idx = current.indexOf(tier)
    if (idx < 0) return
    const next = idx + direction
    if (next < 0 || next >= current.length) return
    ;[current[idx], current[next]] = [
      current[next],
      current[idx],
    ]
    setPendingCascade(current)
  }

  const toggleTier = (tier: string) => {
    const current = [...liveCascade]
    const idx = current.indexOf(tier)
    if (idx >= 0) {
      current.splice(idx, 1)
    } else {
      current.push(tier)
    }
    setPendingCascade(current)
  }

  const cidrPresets = useMemo(
    () => [
      {
        label: t('admin.audioCompute.cidr.localhostLabel'),
        value: '127.0.0.1/32, ::1/128',
        hint: t('admin.audioCompute.cidr.localhostHint'),
      },
      {
        label: t('admin.audioCompute.cidr.privateLabel'),
        value:
          '10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16',
        hint: t('admin.audioCompute.cidr.privateHint'),
      },
      {
        label: t('admin.audioCompute.cidr.vpsLabel'),
        value: '203.0.113.10/32',
        hint: t('admin.audioCompute.cidr.vpsHint'),
      },
      {
        label: t('admin.audioCompute.cidr.anyLabel'),
        value: '0.0.0.0/0',
        hint: t('admin.audioCompute.cidr.anyHint'),
      },
    ],
    [t],
  )

  const workerColumns: ColumnDef<WorkerRow>[] =
    useMemo(
      () => [
        {
          header: t('admin.audioCompute.table.id'),
          accessorKey: 'id',
          cell: (i) => {
            const id = i.getValue<string>()
            return (
              <span
                className="admin-mono"
                title={id}
                style={{
                  wordBreak: 'break-all',
                  maxWidth: 220,
                  display: 'inline-block',
                }}
              >
                {id}
              </span>
            )
          },
        },
        {
          header: t('admin.audioCompute.table.name'),
          accessorKey: 'name',
        },
        {
          header: t('admin.audioCompute.table.profile'),
          accessorKey: 'profile',
        },
        {
          header: t('admin.audioCompute.table.status'),
          cell: (i) => (
            <StatusPill
              kind={computeWorkerPillKind(
                i.row.original,
              )}
              title={
                i.row.original
                  .last_seen_at
                  ? new Date(
                      i.row.original
                        .last_seen_at,
                    ).toLocaleString()
                  : undefined
              }
            >
              {computeWorkerPillLabel(
                i.row.original,
                t,
              )}
            </StatusPill>
          ),
        },
        {
          header: t('admin.audioCompute.table.allowIps'),
          cell: (i) => (
            <span
              className="admin-mono"
              title={(
                i.row.original
                  .allowed_ip_cidrs || []
              ).join('\n')}
            >
              {fmtCidrs(
                i.row.original
                  .allowed_ip_cidrs,
                t,
              )}
            </span>
          ),
        },
        {
          header: t(
            'admin.audioCompute.table.concurrency',
          ),
          accessorKey: 'max_concurrent_jobs',
        },
        {
          header: t(
            'admin.audioCompute.table.lastSeen',
          ),
          cell: (i) =>
            i.row.original
              .last_seen_at
              ? new Date(
                  i.row.original
                    .last_seen_at,
                ).toLocaleString()
              : '–',
        },
        {
          header: t('admin.audioCompute.table.ip'),
          accessorKey: 'last_ip',
        },
      ],
      [t],
    )

  const jobColumns: ColumnDef<JobRow>[] = useMemo(
    () => [
      {
        header: t('admin.audioCompute.table.id'),
        accessorKey: 'id',
        cell: (i) => (
          <span className="admin-mono">
            {String(
              i.getValue<string>(),
            ).slice(0, 8)}
          </span>
        ),
      },
      {
        header: t(
          'admin.audioCompute.table.progress',
        ),
        cell: (i) => {
          const p = i.row.original
            .progress_id
          if (!p) {
            return '–'
          }
          return (
            <span
              className="admin-mono"
              title={p}
            >
              {p.slice(0, 8)}
            </span>
          )
        },
      },
      {
        header: t('admin.audioCompute.table.track'),
        accessorKey: 'track_id',
      },
      {
        header: t(
          'admin.audioCompute.table.status',
        ),
        cell: (i) => (
          <StatusPill
            kind={jobKind(
              i.row.original
                .status,
            )}
          >
            {i.row.original
              .status}
          </StatusPill>
        ),
      },
      {
        header: t('admin.audioCompute.table.tier'),
        cell: (i) => (
          <span className="admin-mono">
            {i.row.original
              .current_tier || '–'}
          </span>
        ),
      },
      {
        header: t(
          'admin.audioCompute.table.attempts',
        ),
        cell: (i) => (
          <span
            title={(
              i.row.original
                .tier_attempts || []
            )
              .map(
                (a) =>
                  `${a.tier}: ${a.status}${
                    a.error
                      ? ` (${a.error})`
                      : ''
                  }`,
              )
              .join('\n')}
          >
            {(
              i.row.original
                .tier_attempts || []
            ).length}
          </span>
        ),
      },
        {
          header: t(
            'admin.audioCompute.table.worker',
          ),
          cell: (i) => {
            const w =
              i.row.original.routed_to_worker
            if (!w) {
              return '–'
            }
            return (
              <span
                className="admin-mono"
                title={w}
                style={{
                  wordBreak: 'break-all',
                  maxWidth: 160,
                  display: 'inline-block',
                }}
              >
                {w}
              </span>
            )
          },
        },
      {
        header: t(
          'admin.audioCompute.table.deadline',
        ),
        cell: (i) => {
          const d = i.row.original
            .deadline_at
          if (!d) {
            return '–'
          }
          return new Date(
            d,
          ).toLocaleString()
        },
      },
      {
        header: t(
          'admin.audioCompute.table.duration',
        ),
        cell: (i) =>
          i.row.original
            .duration_ms
            ? `${(
                i.row.original
                  .duration_ms / 1000
              ).toFixed(1)}s`
            : '–',
      },
      {
        header: t(
          'admin.audioCompute.jobTable.queueRouting',
        ),
        id: 'routing',
        cell: (i) => {
          const row = i.row.original
          const can =
            row.status === 'queued' ||
            row.status === 'running'
          if (!can) {
            return '–'
          }
          return (
            <LyricsJobRoutingControls
              job={row}
              workers={workersList}
              disabled={!can}
              isPending={
                patchLyricsRoutingMutation.isPending
              }
              t={t}
              onApply={(payload) =>
                patchLyricsRoutingMutation.mutate({
                  id: row.id,
                  ...payload,
                })
              }
            />
          )
        },
      },
      {
        header: '',
        id: 'cancel',
        cell: (i) => {
          const st = i.row.original.status
          if (st !== 'queued' && st !== 'running') {
            return null
          }
          return (
            <MotionPress
              variant="ghost"
              onClick={async () => {
                const ok = await showConfirm(
                  t(
                    'admin.audioCompute.jobTable.cancelConfirm',
                  ),
                  { danger: true },
                )
                if (!ok) return
                cancelJobMutation.mutate(
                  i.row.original.id,
                )
              }}
              disabled={cancelJobMutation.isPending}
            >
              {t(
                'admin.audioCompute.jobTable.cancel',
              )}
            </MotionPress>
          )
        },
      },
      {
        header: '',
        id: 'trace',
        cell: (i) => (
          <MotionPress
            variant="ghost"
            onClick={() =>
              setTraceJobId(
                i.row.original.id,
              )
            }
          >
            {t(
              'admin.audioCompute.jobTable.trace',
            )}
          </MotionPress>
        ),
      },
    ],
    [
      t,
      cancelJobMutation,
      showConfirm,
      workersList,
      patchLyricsRoutingMutation,
    ],
  )

  const genericJobColumns: ColumnDef<GenericComputeJobRow>[] =
    useMemo(
      () => [
        {
          header: t(
            'admin.audioCompute.table.id',
          ),
          accessorKey: 'id',
          cell: (i) => (
            <span className="admin-mono">
              {String(
                i.getValue<string>(),
              ).slice(0, 10)}
            </span>
          ),
        },
        {
          header: t(
            'admin.audioCompute.genericJobs.type',
          ),
          accessorKey: 'job_type',
        },
        {
          header: t(
            'admin.audioCompute.table.status',
          ),
          cell: (i) => (
            <StatusPill
              kind={jobKind(
                i.row.original.status,
              )}
            >
              {i.row.original.status}
            </StatusPill>
          ),
        },
        {
          header: t(
            'admin.audioCompute.table.worker',
          ),
          accessorKey: 'claimed_by',
          cell: (i) => {
            const v =
              i.getValue<string | null>()
            return v ? (
              <span className="admin-mono">
                {v.slice(0, 10)}
              </span>
            ) : (
              '–'
            )
          },
        },
        {
          header: t(
            'admin.audioCompute.jobTable.queueRouting',
          ),
          id: 'groute',
          cell: (i) => {
            const row = i.row.original
            const can =
              row.status === 'pending' ||
              row.status === 'claimed'
            if (!can) {
              return '–'
            }
            return (
              <GenericComputeJobRoutingControls
                row={row}
                workers={workersList}
                disabled={!can}
                isPending={
                  patchGenericRoutingMutation.isPending
                }
                t={t}
                onApply={(payload) =>
                  patchGenericRoutingMutation.mutate(
                    {
                      id: row.id,
                      ...payload,
                    },
                  )
                }
              />
            )
          },
        },
      ],
      [
        t,
        workersList,
        patchGenericRoutingMutation,
      ],
    )

  const auditColumns: ColumnDef<AuditRow>[] =
    useMemo(
      () => [
        {
          header: t(
            'admin.audioCompute.table.when',
          ),
          cell: (i) =>
            new Date(
              i.row.original
                .created_at,
            ).toLocaleString(),
        },
        {
          header: t(
            'admin.audioCompute.table.worker',
          ),
          accessorKey: 'worker_id',
          cell: (i) => (
            <span className="admin-mono">
              {(i
                .getValue<string | null>() ||
                '')
                .toString()
                .slice(0, 8) || '–'}
            </span>
          ),
        },
        {
          header: t(
            'admin.audioCompute.table.action',
          ),
          accessorKey: 'action',
        },
        {
          header: t('admin.audioCompute.table.job'),
          accessorKey: 'job_id',
          cell: (i) => (
            <span className="admin-mono">
              {(i
                .getValue<string | null>() ||
                '')
                .toString()
                .slice(0, 8) || '–'}
            </span>
          ),
        },
        {
          header: t(
            'admin.audioCompute.table.status',
          ),
          accessorKey: 'status_code',
        },
        {
          header: t('admin.audioCompute.table.ip'),
          accessorKey: 'ip',
        },
        {
          header: t('admin.audioCompute.table.meta'),
          cell: (i) => {
            const meta = i
              .row.original
              .meta
            if (!meta) {
              return '–'
            }
            const json = JSON.stringify(
              meta,
            )
            return (
              <span
                className="admin-mono"
                title={json}
                style={{
                  maxWidth: 240,
                  display:
                    'inline-block',
                  overflow:
                    'hidden',
                  textOverflow:
                    'ellipsis',
                  whiteSpace:
                    'nowrap',
                }}
              >
                {json}
              </span>
            )
          },
        },
      ],
      [t],
    )

  return (
    <div>
      <h1>{t('admin.audioCompute.title')}</h1>

      <WorkerOnboarding
        hasWorkers={workersList.length > 0}
      />

      <section className="admin-card">
        <h2>
          {t('admin.audioCompute.routing.title')}
        </h2>
        <div className="admin-toolbar">
          <select
            value={routing.data?.mode || 'auto'}
            onChange={(e) =>
              setMode.mutate(e.target.value)
            }
          >
            {ROUTING_MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <span className="admin-card__sub">
            {t('admin.audioCompute.routing.current')}
            {': '}
            <code>
              {routing.data?.mode || '…'}
            </code>
          </span>
        </div>
      </section>

      <section className="admin-card">
        <h2>
          {t('admin.audioCompute.cascade.title')}
        </h2>
        <p className="admin-card__sub">
          {t('admin.audioCompute.cascade.hint')}
        </p>
        <ol style={{ paddingLeft: 20 }}>
          {liveCascade.map((tier, idx) => (
            <li key={tier}>
              <code>{tier}</code>{' '}
              <MotionPress
                variant="ghost"
                disabled={idx === 0}
                onClick={() => moveTier(tier, -1)}
              >
                ↑
              </MotionPress>{' '}
              <MotionPress
                variant="ghost"
                disabled={
                  idx === liveCascade.length - 1
                }
                onClick={() => moveTier(tier, 1)}
              >
                ↓
              </MotionPress>{' '}
              <MotionPress
                variant="ghost"
                onClick={() => toggleTier(tier)}
              >
                {t(
                  'admin.audioCompute.cascade.remove',
                )}
              </MotionPress>
            </li>
          ))}
        </ol>
        <div className="admin-toolbar">
          {ALL_TIERS.filter(
            (x) => !liveCascade.includes(x),
          ).map((tier) => (
            <MotionPress
              key={tier}
              variant="ghost"
              onClick={() => toggleTier(tier)}
            >
              + {tier}
            </MotionPress>
          ))}
          <MotionPress
            variant="ghost"
            disabled={
              !pendingCascade ||
              setCascade.isPending
            }
            onClick={() =>
              pendingCascade &&
              setCascade.mutate(pendingCascade)
            }
          >
            {t('admin.audioCompute.cascade.save')}
          </MotionPress>
          {pendingCascade && (
            <MotionPress
              variant="ghost"
              onClick={() =>
                setPendingCascade(null)
              }
            >
              {t(
                'admin.audioCompute.cascade.discard',
              )}
            </MotionPress>
          )}
        </div>
      </section>

      <section className="admin-card">
        <h2>
          {t('admin.audioCompute.speechkit.title')}
        </h2>
        {speechkit.isLoading || !speechkit.data ? (
          <p>
            {t('admin.audioCompute.speechkit.loading')}
          </p>
        ) : (
          <div>
            <p>
              {t('admin.audioCompute.speechkit.status')}:{' '}
              <StatusPill
                kind={
                  speechkit.data.enabled
                    ? 'ok'
                    : 'unknown'
                }
              >
                {speechkit.data.enabled
                  ? t(
                      'admin.audioCompute.speechkit.enabled',
                    )
                  : t(
                      'admin.audioCompute.speechkit.disabled',
                    )}
              </StatusPill>{' '}
              {!speechkit.data.api_key_set && (
                <StatusPill kind="warn">
                  {t(
                    'admin.audioCompute.speechkit.apiKeyMissing',
                  )}
                </StatusPill>
              )}
            </p>
            <p>
              {t('admin.audioCompute.speechkit.budget')}:{' '}
              <code>
                {speechkit.data.monthly_spent_rub.toFixed(
                  2,
                )}{' '}
                /{' '}
                {speechkit.data.monthly_budget_rub.toFixed(
                  2,
                )}{' '}
                ₽
              </code>{' '}
              ({t('admin.audioCompute.speechkit.remaining')}{' '}
              <code>
                {speechkit.data.remaining_rub.toFixed(
                  2,
                )}{' '}
                ₽
              </code>
              )
            </p>
            <p>
              {t('admin.audioCompute.speechkit.rate')}:{' '}
              <code>
                {speechkit.data.rate_rub_per_minute.toFixed(
                  2,
                )}{' '}
                {t('admin.audioCompute.speechkit.perMin')}
              </code>
              , {t('admin.audioCompute.speechkit.softLimit')}{' '}
              <code>
                {speechkit.data.soft_per_job_limit_rub.toFixed(
                  2,
                )}{' '}
                ₽
              </code>
            </p>
            <MotionPress
              variant="ghost"
              onClick={() => resetSpend.mutate()}
              disabled={resetSpend.isPending}
            >
              {t(
                'admin.audioCompute.speechkit.resetSpend',
              )}
            </MotionPress>
          </div>
        )}
      </section>

      <section className="admin-card">
        <h2>
          {t('admin.audioCompute.workers')}
        </h2>
        <p className="admin-card__sub">
          {t(
            'admin.audioCompute.workersSectionHint',
            {
              sec: WORKER_ONLINE_MAX_AGE_SEC,
            },
          )}
        </p>
        <div
          className="admin-toolbar"
          style={{
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <input
            type="text"
            placeholder={t(
              'admin.audioCompute.workerForm.namePlaceholder',
            )}
            value={newName}
            onChange={(e) =>
              setNewName(e.target.value)
            }
            maxLength={64}
          />
          <select
            value={newProfile}
            onChange={(e) =>
              setNewProfile(e.target.value)
            }
          >
            {PROFILE_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={1}
            max={32}
            value={newConcurrency}
            onChange={(e) =>
              setNewConcurrency(
                Math.max(
                  1,
                  Number(e.target.value) || 1,
                ),
              )
            }
            style={{ width: 80 }}
            title={t(
              'admin.audioCompute.workerForm.concurrencyTitle',
            )}
          />
          <input
            type="text"
            placeholder={t(
              'admin.audioCompute.workerForm.allowedProfilesPlaceholder',
            )}
            value={newAllowedProfiles}
            onChange={(e) =>
              setNewAllowedProfiles(
                e.target.value,
              )
            }
            style={{ width: 220 }}
          />
        </div>
        <div style={{ marginTop: 8 }}>
          <label>
            <div>
              {t(
                'admin.audioCompute.workerForm.cidrLabel',
              )}
            </div>
            <textarea
              value={newCidrs}
              onChange={(e) =>
                setNewCidrs(e.target.value)
              }
              rows={3}
              cols={48}
              placeholder={t(
                'admin.audioCompute.workerForm.cidrPlaceholder',
              )}
            />
          </label>
          <div
            className="admin-toolbar"
            style={{
              flexWrap: 'wrap',
              gap: 6,
              marginTop: 4,
            }}
          >
            <span className="admin-card__sub">
              {t(
                'admin.audioCompute.workerForm.presets',
              )}
            </span>
            {cidrPresets.map((preset) => (
              <MotionPress
                key={preset.label}
                variant="ghost"
                title={preset.hint}
                onClick={() =>
                  setNewCidrs(preset.value)
                }
              >
                {preset.label}
              </MotionPress>
            ))}
          </div>
          {cidrParsed.length > 0 && (
            <p className="admin-card__sub">
              {cidrParsed.length === 1
                ? t(
                    'admin.audioCompute.workerForm.parsedOne',
                    {
                      count: cidrParsed.length,
                    },
                  )
                : t(
                    'admin.audioCompute.workerForm.parsedMany',
                    {
                      count: cidrParsed.length,
                    },
                  )}
              {cidrIsOpen &&
                t(
                  'admin.audioCompute.workerForm.wildcardDetected',
                )}
            </p>
          )}
          {cidrIsOpen && (
            <div className="admin-card admin-card--inline">
              <p>
                <StatusPill kind="error">
                  {t(
                    'admin.audioCompute.workerForm.wildcardPill',
                  )}
                </StatusPill>{' '}
                {t(
                  'admin.audioCompute.workerForm.wildcardBody',
                )}
              </p>
              <label>
                <input
                  type="checkbox"
                  checked={acceptOpen}
                  onChange={(e) =>
                    setAcceptOpen(
                      e.target.checked,
                    )
                  }
                />{' '}
                {t(
                  'admin.audioCompute.workerForm.acceptRisk',
                )}
              </label>
            </div>
          )}
          <MotionPress
            variant="ghost"
            disabled={
              !newName ||
              cidrParsed.length === 0 ||
              (cidrIsOpen && !acceptOpen) ||
              createWorker.isPending
            }
            onClick={() =>
              createWorker.mutate({
                name: newName,
                profile: newProfile,
                allowed_ip_cidrs: cidrParsed,
                allowed_profiles:
                  parseCidrInput(
                    newAllowedProfiles,
                  ),
                max_concurrent_jobs:
                  newConcurrency,
                accept_open_allowlist:
                  acceptOpen,
              })
            }
          >
            {t('admin.audioCompute.workerForm.create')}
          </MotionPress>
        </div>
        {showSecret && (
          <div className="admin-card admin-card--inline">
            <p>
              {t(
                'admin.audioCompute.workerForm.secretOnce',
              )}
            </p>
            <code className="admin-mono">
              {showSecret}
            </code>
            <MotionPress
              variant="ghost"
              onClick={() =>
                setShowSecret(null)
              }
            >
              {t(
                'admin.audioCompute.workerForm.dismiss',
              )}
            </MotionPress>
          </div>
        )}
        <DataTable
          columns={[
            ...workerColumns,
            {
              header: '',
              id: 'actions',
              cell: (i) => {
                const row = i.row.original
                return (
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 4,
                    }}
                  >
                    <MotionPress
                      variant="ghost"
                      onClick={() =>
                        setDrawerWorkerId(row.id)
                      }
                    >
                      {t(
                        'admin.audioCompute.workerForm.open',
                      )}
                    </MotionPress>
                    {row.revoked_at && (
                      <MotionPress
                        variant="ghost"
                        onClick={async () => {
                          const ok = await showConfirm(
                            t(
                              'admin.audioCompute.workerForm.deleteFromListConfirm',
                              {
                                name: row.name,
                              },
                            ),
                            { danger: true },
                          )
                          if (!ok) return
                          deleteRevokedWorker.mutate(
                            row.id,
                          )
                        }}
                        disabled={
                          deleteRevokedWorker.isPending
                        }
                        style={{ color: 'var(--admin-dim)' }}
                      >
                        {t(
                          'admin.audioCompute.workerForm.deleteFromList',
                        )}
                      </MotionPress>
                    )}
                  </div>
                )
              },
            },
          ]}
          rows={workersList}
          emptyHint={t(
            'admin.audioCompute.workerForm.tableEmpty',
          )}
        />
      </section>

      <section className="admin-card">
        <div
          className="admin-toolbar"
          style={{
            marginBottom: '0.5rem',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <h2 style={{ margin: 0 }}>
            {t('admin.audioCompute.jobs')}
          </h2>
          <label
            htmlFor="ac-jobs-sort"
            className="admin-card__sub"
            style={{ margin: 0 }}
          >
            {t(
              'admin.audioCompute.jobTable.sortLabel',
            )}
          </label>
          <select
            id="ac-jobs-sort"
            value={jobsSort}
            onChange={(e) =>
              setJobsSort(
                e.target.value as
                  | 'queue'
                  | 'recent',
              )
            }
          >
            <option value="queue">
              {t(
                'admin.audioCompute.jobTable.sortQueue',
              )}
            </option>
            <option value="recent">
              {t(
                'admin.audioCompute.jobTable.sortRecent',
              )}
            </option>
          </select>
        </div>
        <p className="admin-card__sub">
          {t(
            'admin.audioCompute.jobTable.toolbarHint',
          )}
        </p>
        <div
          className="admin-toolbar"
          style={{
            marginBottom: '1rem',
            flexWrap: 'wrap',
            gap: '0.75rem',
          }}
        >
          <MotionPress
            variant="ghost"
            onClick={async () => {
              const ok = await showConfirm(
                t(
                  'admin.audioCompute.jobTable.reapLeasesConfirm',
                ),
                { danger: true },
              )
              if (!ok) return
              reapLeasesMutation.mutate()
            }}
            disabled={reapLeasesMutation.isPending}
          >
            {t(
              'admin.audioCompute.jobTable.reapLeases',
            )}
          </MotionPress>
          {reapNotice !== null && (
            <span className="admin-card__sub">
              {t(
                'admin.audioCompute.jobTable.reapLeasesResult',
                {
                  count: Number(reapNotice),
                },
              )}
            </span>
          )}
        </div>
        <div
          className="admin-toolbar"
          style={{
            marginBottom: '1.25rem',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <label
            htmlFor="ac-progress-cancel"
            style={{ margin: 0 }}
          >
            {t(
              'admin.audioCompute.jobTable.cancelByProgressLabel',
            )}
          </label>
          <input
            id="ac-progress-cancel"
            type="text"
            value={progressToCancel}
            onChange={(e) =>
              setProgressToCancel(
                e.target.value,
              )
            }
            placeholder={t(
              'admin.audioCompute.jobTable.progressPlaceholder',
            )}
            style={{ minWidth: 220 }}
          />
          <MotionPress
            variant="ghost"
            onClick={() => {
              const p = progressToCancel.trim()
              if (p.length < 16) return
              cancelByProgressMutation.mutate(p)
            }}
            disabled={
              cancelByProgressMutation.isPending ||
              progressToCancel.trim().length < 16
            }
          >
            {t(
              'admin.audioCompute.jobTable.cancelByProgress',
            )}
          </MotionPress>
        </div>
        <DataTable
          columns={jobColumns}
          rows={
            (jobs.data as JobRow[] | undefined) ||
            []
          }
          emptyHint={t(
            'admin.audioCompute.jobTable.empty',
          )}
        />
      </section>

      <section className="admin-card">
        <h2>
          {t('admin.audioCompute.genericJobs.title')}
        </h2>
        <p className="admin-card__sub">
          {t(
            'admin.audioCompute.genericJobs.hint',
          )}
        </p>
        <DataTable
          columns={genericJobColumns}
          rows={
            (genericJobs.data as
              | GenericComputeJobRow[]
              | undefined) || []
          }
          emptyHint={t(
            'admin.audioCompute.genericJobs.empty',
          )}
        />
      </section>

      {traceJob && (
        <section className="admin-card">
          <h2>
            {t('admin.audioCompute.jobTable.trace')} ·{' '}
            <code>{traceJob.id}</code>{' '}
            <MotionPress
              variant="ghost"
              onClick={() => setTraceJobId(null)}
            >
              {t(
                'admin.audioCompute.jobTable.close',
              )}
            </MotionPress>
          </h2>
          <p>
            {t(
              'admin.audioCompute.jobTable.status',
            )}
            :{' '}
            <StatusPill kind={jobKind(traceJob.status)}>
              {traceJob.status}
            </StatusPill>{' '}
            {t('admin.audioCompute.jobTable.currentTier')}:{' '}
            <code>
              {traceJob.current_tier || '–'}
            </code>
          </p>
          {traceJob.progress_id && (
            <p>
              {t(
                'admin.audioCompute.jobTable.traceProgressId',
              )}
              :{' '}
              <code
                className="admin-mono"
                style={{
                  wordBreak: 'break-all',
                }}
              >
                {traceJob.progress_id}
              </code>
            </p>
          )}
          {(traceJob.deadline_at ||
            traceJob.started_at) && (
            <p className="admin-card__sub">
              {traceJob.started_at && (
                <>
                  {t(
                    'admin.audioCompute.jobTable.traceStarted',
                  )}
                  :{' '}
                  {new Date(
                    traceJob.started_at,
                  ).toLocaleString()}{' '}
                </>
              )}
              {traceJob.deadline_at && (
                <>
                  {t(
                    'admin.audioCompute.jobTable.traceDeadline',
                  )}
                  :{' '}
                  {new Date(
                    traceJob.deadline_at,
                  ).toLocaleString()}
                </>
              )}
            </p>
          )}
          {traceJob.error && (
            <p>
              <strong>
                {t('admin.audioCompute.jobTable.error')}
                :
              </strong>{' '}
              <code>{traceJob.error}</code>
            </p>
          )}
          <ol>
            {(traceJob.tier_attempts || []).map(
              (att, idx) => (
                <li key={idx}>
                  <code>{att.tier}</code> →{' '}
                  <StatusPill
                    kind={tierBadgeKind(
                      att.status,
                    )}
                  >
                    {att.status}
                  </StatusPill>
                  {att.started_at && (
                    <>
                      {' '}
                      ·{' '}
                      <span className="admin-card__sub">
                        {new Date(
                          att.started_at,
                        ).toLocaleString()}
                      </span>
                    </>
                  )}
                  {att.error && (
                    <>
                      {' '}
                      ·{' '}
                      <code>{att.error}</code>
                    </>
                  )}
                </li>
              ),
            )}
          </ol>
        </section>
      )}

      <section className="admin-card">
        <h2>
          {t('admin.audioCompute.auditSection.title')}
        </h2>
        <div className="admin-toolbar">
          <label>
            {t('admin.audioCompute.auditSection.filter')}:{' '}
          </label>
          <select
            value={auditFilter}
            onChange={(e) =>
              setAuditFilter(e.target.value)
            }
          >
            {AUDIT_ACTION_FILTERS.map((a) => (
              <option key={a} value={a}>
                {a ||
                  t(
                    'admin.audioCompute.auditSection.all',
                  )}
              </option>
            ))}
          </select>
        </div>
        <DataTable
          columns={auditColumns}
          rows={
            (audit.data as
              | AuditRow[]
              | undefined) || []
          }
        />
      </section>

      {drawerWorker && (
        <WorkerDetailDrawer
          worker={drawerWorker}
          backendBaseUrl={backendBaseUrl}
          onClose={() => setDrawerWorkerId(null)}
          onSecretShown={(secret) =>
            setShowSecret(secret)
          }
          onRequestDeleteRevoked={() =>
            deleteRevokedWorker.mutate(
              drawerWorker.id,
            )
          }
          deleteFromListPending={
            deleteRevokedWorker.isPending
          }
        />
      )}
    </div>
  )
}
