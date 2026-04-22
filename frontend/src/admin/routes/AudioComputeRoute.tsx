import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminFetch } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

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
  track_id: number
  status: string
  profile: string
  current_tier: string | null
  tiers_planned: string[]
  tier_attempts: TierAttempt[]
  routed_to_worker: string | null
  attempts: number
  duration_ms: number | null
  error: string | null
  created_at: string
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
  if (status === 'done') return 'ok'
  if (status === 'failed' || status === 'error')
    return 'error'
  if (status === 'queued' || status === 'running')
    return 'warn'
  return 'unknown'
}

function workerKind(
  row: WorkerRow,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (row.revoked_at) return 'error'
  if (row.suspended_until) return 'warn'
  if (!row.active) return 'error'
  return 'ok'
}

function workerLabel(row: WorkerRow): string {
  if (row.revoked_at) return 'revoked'
  if (row.suspended_until)
    return `suspended ${row.suspended_reason || ''}`.trim()
  if (!row.active)
    return row.suspended_reason || 'inactive'
  return 'active'
}

function fmtCidrs(values: string[]): string {
  if (!values || values.length === 0) return '–'
  if (values.includes('0.0.0.0/0')) return 'ANY ⚠'
  return `${values.length}`
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

const workerColumns: ColumnDef<WorkerRow>[] = [
  {
    header: 'ID',
    accessorKey: 'id',
    cell: (i) => (
      <span className="admin-mono">
        {i.getValue<string>().slice(0, 12)}
      </span>
    ),
  },
  { header: 'Name', accessorKey: 'name' },
  { header: 'Profile', accessorKey: 'profile' },
  {
    header: 'Status',
    cell: (i) => (
      <StatusPill kind={workerKind(i.row.original)}>
        {workerLabel(i.row.original)}
      </StatusPill>
    ),
  },
  {
    header: 'Allow IPs',
    cell: (i) => (
      <span
        className="admin-mono"
        title={(
          i.row.original.allowed_ip_cidrs || []
        ).join('\n')}
      >
        {fmtCidrs(i.row.original.allowed_ip_cidrs)}
      </span>
    ),
  },
  {
    header: 'Concurrency',
    accessorKey: 'max_concurrent_jobs',
  },
  {
    header: 'Last seen',
    cell: (i) =>
      i.row.original.last_seen_at
        ? new Date(
            i.row.original.last_seen_at,
          ).toLocaleString()
        : '–',
  },
  { header: 'IP', accessorKey: 'last_ip' },
]

export function AudioComputeRoute() {
  const { t } = useTranslation()
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
  const jobs = useQuery({
    queryKey: ['admin', 'compute', 'jobs'],
    queryFn: () =>
      adminFetch<JobRow[]>('/audio-compute/jobs'),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
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

  const revokeWorker = useMutation({
    mutationFn: (id: string) =>
      adminFetch(
        `/audio-compute/workers/${id}/revoke`,
        { method: 'POST', body: {} },
      ),
    onSettled: () =>
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      }),
  })

  const rotateSecret = useMutation({
    mutationFn: (id: string) =>
      adminFetch<{ secret: string }>(
        `/audio-compute/workers/${id}/rotate_secret`,
        { method: 'POST', body: {} },
      ),
    onSuccess: (data) => setShowSecret(data.secret),
  })

  const updateAllowlist = useMutation({
    mutationFn: (payload: {
      id: string
      allowed_ip_cidrs: string[]
      accept_open_allowlist: boolean
    }) =>
      adminFetch(
        `/audio-compute/workers/${payload.id}/allowlist`,
        {
          method: 'PATCH',
          body: {
            allowed_ip_cidrs:
              payload.allowed_ip_cidrs,
            accept_open_allowlist:
              payload.accept_open_allowlist,
          },
        },
      ),
    onSettled: () =>
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
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

  const jobColumns: ColumnDef<JobRow>[] = [
    {
      header: 'ID',
      accessorKey: 'id',
      cell: (i) => (
        <span className="admin-mono">
          {String(i.getValue<string>()).slice(0, 8)}
        </span>
      ),
    },
    { header: 'Track', accessorKey: 'track_id' },
    {
      header: 'Status',
      cell: (i) => (
        <StatusPill kind={jobKind(i.row.original.status)}>
          {i.row.original.status}
        </StatusPill>
      ),
    },
    {
      header: 'Tier',
      cell: (i) => (
        <span className="admin-mono">
          {i.row.original.current_tier || '–'}
        </span>
      ),
    },
    {
      header: 'Attempts',
      cell: (i) => (
        <span title={(
          i.row.original.tier_attempts || []
        )
          .map(
            (a) =>
              `${a.tier}: ${a.status}${
                a.error ? ` (${a.error})` : ''
              }`,
          )
          .join('\n')}>
          {(
            i.row.original.tier_attempts || []
          ).length}
        </span>
      ),
    },
    {
      header: 'Worker',
      cell: (i) => (
        <span className="admin-mono">
          {(i.row.original.routed_to_worker || '–').slice(
            0,
            10,
          )}
        </span>
      ),
    },
    {
      header: 'Duration',
      cell: (i) =>
        i.row.original.duration_ms
          ? `${(
              i.row.original.duration_ms / 1000
            ).toFixed(1)}s`
          : '–',
    },
    {
      header: '',
      id: 'trace',
      cell: (i) => (
        <Press
          variant="ghost"
          onClick={() =>
            setTraceJobId(i.row.original.id)
          }
        >
          Trace
        </Press>
      ),
    },
  ]

  const auditColumns: ColumnDef<AuditRow>[] = [
    {
      header: 'When',
      cell: (i) =>
        new Date(
          i.row.original.created_at,
        ).toLocaleString(),
    },
    {
      header: 'Worker',
      accessorKey: 'worker_id',
      cell: (i) => (
        <span className="admin-mono">
          {(i.getValue<string | null>() || '')
            .toString()
            .slice(0, 8) || '–'}
        </span>
      ),
    },
    { header: 'Action', accessorKey: 'action' },
    {
      header: 'Job',
      accessorKey: 'job_id',
      cell: (i) => (
        <span className="admin-mono">
          {(i.getValue<string | null>() || '')
            .toString()
            .slice(0, 8) || '–'}
        </span>
      ),
    },
    { header: 'Status', accessorKey: 'status_code' },
    { header: 'IP', accessorKey: 'ip' },
    {
      header: 'Meta',
      cell: (i) => {
        const meta = i.row.original.meta
        if (!meta) return '–'
        const json = JSON.stringify(meta)
        return (
          <span
            className="admin-mono"
            title={json}
            style={{
              maxWidth: 240,
              display: 'inline-block',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {json}
          </span>
        )
      },
    },
  ]

  return (
    <div>
      <h1>{t('admin.audioCompute.title')}</h1>

      <section className="admin-card">
        <h2>Routing mode</h2>
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
            current:{' '}
            <code>
              {routing.data?.mode || '…'}
            </code>
          </span>
        </div>
      </section>

      <section className="admin-card">
        <h2>Cascade order</h2>
        <p className="admin-card__sub">
          Drag tiers up/down to change the order
          jobs try them. Toggle to add/remove a tier
          from the cascade.
        </p>
        <ol style={{ paddingLeft: 20 }}>
          {liveCascade.map((tier, idx) => (
            <li key={tier}>
              <code>{tier}</code>{' '}
              <Press
                variant="ghost"
                disabled={idx === 0}
                onClick={() => moveTier(tier, -1)}
              >
                ↑
              </Press>{' '}
              <Press
                variant="ghost"
                disabled={
                  idx === liveCascade.length - 1
                }
                onClick={() => moveTier(tier, 1)}
              >
                ↓
              </Press>{' '}
              <Press
                variant="ghost"
                onClick={() => toggleTier(tier)}
              >
                Remove
              </Press>
            </li>
          ))}
        </ol>
        <div className="admin-toolbar">
          {ALL_TIERS.filter(
            (t) => !liveCascade.includes(t),
          ).map((tier) => (
            <Press
              key={tier}
              variant="ghost"
              onClick={() => toggleTier(tier)}
            >
              + {tier}
            </Press>
          ))}
          <Press
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
            Save cascade
          </Press>
          {pendingCascade && (
            <Press
              variant="ghost"
              onClick={() =>
                setPendingCascade(null)
              }
            >
              Discard
            </Press>
          )}
        </div>
      </section>

      <section className="admin-card">
        <h2>SpeechKit (paid tier)</h2>
        {speechkit.isLoading || !speechkit.data ? (
          <p>Loading…</p>
        ) : (
          <div>
            <p>
              Status:{' '}
              <StatusPill
                kind={
                  speechkit.data.enabled
                    ? 'ok'
                    : 'unknown'
                }
              >
                {speechkit.data.enabled
                  ? 'enabled'
                  : 'disabled'}
              </StatusPill>{' '}
              {!speechkit.data.api_key_set && (
                <StatusPill kind="warn">
                  api key missing
                </StatusPill>
              )}
            </p>
            <p>
              Budget this month:{' '}
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
              (remaining{' '}
              <code>
                {speechkit.data.remaining_rub.toFixed(
                  2,
                )}{' '}
                ₽
              </code>
              )
            </p>
            <p>
              Rate:{' '}
              <code>
                {speechkit.data.rate_rub_per_minute.toFixed(
                  2,
                )}{' '}
                ₽/min
              </code>
              , per-job soft limit{' '}
              <code>
                {speechkit.data.soft_per_job_limit_rub.toFixed(
                  2,
                )}{' '}
                ₽
              </code>
            </p>
            <Press
              variant="ghost"
              onClick={() => resetSpend.mutate()}
              disabled={resetSpend.isPending}
            >
              Reset month spent counter
            </Press>
          </div>
        )}
      </section>

      <section className="admin-card">
        <h2>Workers</h2>
        <div
          className="admin-toolbar"
          style={{
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <input
            type="text"
            placeholder="worker name"
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
            title="max_concurrent_jobs"
          />
          <input
            type="text"
            placeholder="allowed_profiles (comma)"
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
              Allowed IP CIDRs (one per line, or
              comma-separated):
            </div>
            <textarea
              value={newCidrs}
              onChange={(e) =>
                setNewCidrs(e.target.value)
              }
              rows={3}
              cols={48}
              placeholder={
                '127.0.0.1/32\n10.0.0.0/8'
              }
            />
          </label>
          {cidrIsOpen && (
            <div className="admin-card admin-card--inline">
              <p>
                <StatusPill kind="error">
                  Wildcard
                </StatusPill>{' '}
                You are about to allow ALL IPs.
                A leaked secret will let anyone on
                the internet impersonate this
                worker.
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
                I accept the risk
              </label>
            </div>
          )}
          <Press
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
            Create worker
          </Press>
        </div>
        {showSecret && (
          <div className="admin-card admin-card--inline">
            <p>
              Save this secret — it will not be
              shown again:
            </p>
            <code className="admin-mono">
              {showSecret}
            </code>
            <Press
              variant="ghost"
              onClick={() =>
                setShowSecret(null)
              }
            >
              Dismiss
            </Press>
          </div>
        )}
        <DataTable
          columns={[
            ...workerColumns,
            {
              header: '',
              id: 'actions',
              cell: (i) => (
                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                  }}
                >
                  <Press
                    variant="ghost"
                    onClick={() =>
                      rotateSecret.mutate(
                        i.row.original.id,
                      )
                    }
                  >
                    Rotate
                  </Press>
                  <Press
                    variant="ghost"
                    onClick={() => {
                      const next = window.prompt(
                        'New allowed CIDRs (comma-separated)',
                        (
                          i.row.original
                            .allowed_ip_cidrs ||
                          []
                        ).join(', '),
                      )
                      if (next === null) return
                      const list =
                        parseCidrInput(next)
                      const open =
                        list.includes(
                          '0.0.0.0/0',
                        ) ||
                        list.includes('::/0')
                      const accept = open
                        ? window.confirm(
                            'Wildcard CIDR detected. Confirm to accept the risk.',
                          )
                        : true
                      if (open && !accept) return
                      updateAllowlist.mutate({
                        id: i.row.original.id,
                        allowed_ip_cidrs: list,
                        accept_open_allowlist:
                          open && accept,
                      })
                    }}
                  >
                    Edit IPs
                  </Press>
                  <Press
                    variant="ghost"
                    onClick={() =>
                      revokeWorker.mutate(
                        i.row.original.id,
                      )
                    }
                  >
                    Revoke
                  </Press>
                </div>
              ),
            },
          ]}
          rows={
            (workers.data as
              | WorkerRow[]
              | undefined) || []
          }
          emptyHint="No workers registered"
        />
      </section>

      <section className="admin-card">
        <h2>Jobs</h2>
        <DataTable
          columns={jobColumns}
          rows={
            (jobs.data as JobRow[] | undefined) ||
            []
          }
          emptyHint="No jobs in flight"
        />
      </section>

      {traceJob && (
        <section className="admin-card">
          <h2>
            Trace · <code>{traceJob.id}</code>{' '}
            <Press
              variant="ghost"
              onClick={() => setTraceJobId(null)}
            >
              Close
            </Press>
          </h2>
          <p>
            Status:{' '}
            <StatusPill kind={jobKind(traceJob.status)}>
              {traceJob.status}
            </StatusPill>{' '}
            current tier:{' '}
            <code>
              {traceJob.current_tier || '–'}
            </code>
          </p>
          {traceJob.error && (
            <p>
              <strong>Error:</strong>{' '}
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
        <h2>Worker audit (last 200)</h2>
        <div className="admin-toolbar">
          <label>Filter:</label>
          <select
            value={auditFilter}
            onChange={(e) =>
              setAuditFilter(e.target.value)
            }
          >
            {AUDIT_ACTION_FILTERS.map((a) => (
              <option key={a} value={a}>
                {a || '(all)'}
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
    </div>
  )
}
