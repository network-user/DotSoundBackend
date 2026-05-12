import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  computeWorkerPillKind,
  computeWorkerPillLabel,
} from '../../lib/computeWorkerLiveness'
import { adminFetch } from '../../lib/adminApi'
import { AdminWs } from '../../lib/adminWs'
import { StatusPill } from './StatusPill'
import { AdminPageNav } from '../layout/AdminPageNav'

const WD = 'admin.audioCompute.workerDrawer' as const
const AC = 'admin.audioCompute' as const

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

interface WorkerEvent {
  id: string
  ts: string
  action: string
  job_id?: string
  status_code?: string
  ip?: string
  meta?: unknown
}

interface WorkerJobRow {
  id: string
  track_id: number
  status: string
  current_tier: string | null
  progress_id: string
  lyrics_progress: {
    stage?: string
    percent?: number
    logs?: string[]
  } | null
}

interface Props {
  worker: WorkerRow
  backendBaseUrl: string
  onClose: () => void
  onSecretShown: (secret: string) => void
  onRequestDeleteRevoked?: () => void
  deleteFromListPending?: boolean
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '–'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function actionKind(
  action: string,
  status?: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (
    action === 'auth_fail' ||
    action === 'rate_limit_exceeded' ||
    action === 'audio_sha_mismatch' ||
    action === 'auto_suspend' ||
    action === 'anomaly' ||
    action === 'result_invalid' ||
    action === 'result_fail'
  ) {
    return 'error'
  }
  if (
    action === 'claim_empty' ||
    action === 'progress'
  ) {
    return 'warn'
  }
  if (
    action === 'heartbeat' ||
    action === 'claim_ok' ||
    action === 'result_ok'
  ) {
    return 'ok'
  }
  if (status && status.startsWith('4')) return 'error'
  if (status && status.startsWith('5')) return 'error'
  return 'unknown'
}

function wsPayloadToWorkerEvent(
  raw: Record<string, unknown>,
): WorkerEvent {
  const jobRaw = raw.job_id
  return {
    id: String(raw.id ?? ''),
    ts: String(raw.ts ?? ''),
    action: String(raw.action ?? ''),
    job_id:
      typeof jobRaw === 'string' && jobRaw
        ? jobRaw
        : undefined,
    status_code:
      typeof raw.status_code === 'string' &&
      raw.status_code
        ? raw.status_code
        : undefined,
    ip:
      typeof raw.ip === 'string' && raw.ip
        ? raw.ip
        : undefined,
    meta: raw.meta,
  }
}

function progressSummary(
  p: WorkerJobRow['lyrics_progress'],
): {
  stage: string
  percent: string
  logs: string[] | undefined
} {
  if (!p) {
    return { stage: '—', percent: '—', logs: undefined }
  }
  const st =
    typeof p.stage === 'string' && p.stage
      ? p.stage
      : '—'
  const pct =
    typeof p.percent === 'number' &&
    Number.isFinite(p.percent)
      ? String(p.percent)
      : '—'
  return { stage: st, percent: pct, logs: p.logs }
}

export function WorkerDetailDrawer({
  worker,
  backendBaseUrl,
  onClose,
  onSecretShown,
  onRequestDeleteRevoked,
  deleteFromListPending = false,
}: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [confirmRevoke, setConfirmRevoke] =
    useState(false)
  const [confirmRotate, setConfirmRotate] =
    useState(false)
  const [confirmDeleteFromList, setConfirmDeleteFromList] =
    useState(false)
  const [editCidrs, setEditCidrs] = useState<
    string | null
  >(null)
  const [acceptOpen, setAcceptOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [wsEvents, setWsEvents] = useState<
    WorkerEvent[]
  >([])
  const [wsOnline, setWsOnline] =
    useState(false)
  const [pauseMinutes, setPauseMinutes] =
    useState(60)
  const drawerRootRef = useRef<HTMLDivElement>(null)

  const events = useQuery({
    queryKey: [
      'admin',
      'compute',
      'worker_events',
      worker.id,
    ],
    queryFn: () =>
      adminFetch<{ events: WorkerEvent[] }>(
        `/audio-compute/workers/${worker.id}/events?limit=100`,
      ),
    refetchInterval: wsOnline ? false : 5_000,
    refetchIntervalInBackground: false,
  })

  const workerJobs = useQuery({
    queryKey: [
      'admin',
      'compute',
      'worker_jobs',
      worker.id,
    ],
    queryFn: () =>
      adminFetch<WorkerJobRow[]>(
        `/audio-compute/workers/${worker.id}/jobs?limit=40`,
      ),
    refetchInterval: 3_000,
    refetchIntervalInBackground: false,
  })

  const revokeWorker = useMutation({
    mutationFn: () =>
      adminFetch(
        `/audio-compute/workers/${worker.id}/revoke`,
        { method: 'POST', body: {} },
      ),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
      qc.invalidateQueries({
        queryKey: [
          'admin',
          'compute',
          'worker_jobs',
          worker.id,
        ],
      })
      setConfirmRevoke(false)
    },
  })

  const rotateSecret = useMutation({
    mutationFn: () =>
      adminFetch<{ secret: string }>(
        `/audio-compute/workers/${worker.id}/rotate_secret`,
        { method: 'POST', body: {} },
      ),
    onSuccess: (data) => {
      onSecretShown(data.secret)
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
      setConfirmRotate(false)
    },
  })

  const updateAllowlist = useMutation({
    mutationFn: (payload: {
      allowed_ip_cidrs: string[]
      accept_open_allowlist: boolean
      allowed_profiles?: string[]
    }) =>
      adminFetch(
        `/audio-compute/workers/${worker.id}/allowlist`,
        {
          method: 'PATCH',
          body: payload,
        },
      ),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
      setEditCidrs(null)
      setAcceptOpen(false)
    },
  })

  const pauseClaims = useMutation({
    mutationFn: (payload: {
      minutes: number
      mode: 'soft' | 'drain'
    }) =>
      adminFetch(
        `/audio-compute/workers/${worker.id}/claims/pause`,
        {
          method: 'POST',
          body: payload,
        },
      ),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
    },
  })

  const resumeClaims = useMutation({
    mutationFn: () =>
      adminFetch(
        `/audio-compute/workers/${worker.id}/claims/resume`,
        {
          method: 'POST',
          body: {},
        },
      ),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'compute', 'workers'],
      })
    },
  })

  useEffect(() => {
    setWsEvents([])
    const ws = new AdminWs({
      onEvent: (ev) => {
        if (ev.channel !== 'worker_logs') {
          return
        }
        const d = ev.data as {
          worker_id?: string
          items?: Record<string, unknown>[]
        }
        if (
          d?.worker_id !== worker.id ||
          !Array.isArray(d.items)
        ) {
          return
        }
        const mapped = d.items.map(wsPayloadToWorkerEvent)
        setWsEvents((prev) => {
          const merged = [...mapped, ...prev]
          const seen = new Set<string>()
          const out: WorkerEvent[] = []
          for (const row of merged) {
            if (!row.id || seen.has(row.id)) continue
            seen.add(row.id)
            out.push(row)
          }
          return out.slice(0, 200)
        })
      },
      onOpen: () => setWsOnline(true),
      onClose: () => setWsOnline(false),
    })
    ws.connect()
    ws.subscribe('worker_logs', {
      worker_id: worker.id,
    })
    return () => {
      ws.unsubscribe('worker_logs')
      ws.close()
      setWsOnline(false)
    }
  }, [worker.id])

  const displayEvents = useMemo(() => {
    const base = events.data?.events ?? []
    const merged = [...wsEvents, ...base]
    const seen = new Set<string>()
    const out: WorkerEvent[] = []
    for (const row of merged) {
      if (!row.id || seen.has(row.id)) continue
      seen.add(row.id)
      out.push(row)
    }
    out.sort(
      (a, b) =>
        new Date(b.ts).getTime() -
        new Date(a.ts).getTime(),
    )
    return out
  }, [events.data?.events, wsEvents])

  const envSnippet = useMemo(
    () =>
      `WORKER_ID=${worker.id}
WORKER_SECRET=<paste secret you saved at creation>
WORKER_BACKEND_BASE_URL=${backendBaseUrl}
WORKER_DEBUG=false
WORKER_ASR_MODEL_SIZE=large-v3
WORKER_ASR_DEVICE=auto`,
    [worker.id, backendBaseUrl],
  )

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(
        envSnippet,
      )
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  const profileFix = useMemo(() => {
    const cidrs = worker.allowed_ip_cidrs || []
    const effective: string[] = (
      (worker.allowed_profiles?.length
        ? worker.allowed_profiles
        : [worker.profile]) as string[]
    ).filter(
      (p) => typeof p === 'string' && p.length > 0,
    )
    return {
      cidrsForApi: cidrs,
      hasGpuFull: effective.includes('gpu_full'),
      merged: [...new Set([...effective, 'gpu_full'])],
      needsOpenAccept: cidrs.includes('0.0.0.0/0'),
    }
  }, [worker])

  const livenessLabel = computeWorkerPillLabel(
    worker,
    t,
    fmtDate,
  )
  const livenessKind = computeWorkerPillKind(
    worker,
  )

  const editParsed =
    editCidrs === null
      ? []
      : editCidrs
          .split(/[\n,]+/)
          .map((s) => s.trim())
          .filter(Boolean)
  const editIsOpen = editParsed.includes('0.0.0.0/0')

  return (
    <div
      ref={drawerRootRef}
      role="dialog"
      aria-label={t(`${WD}.aria`, {
        name: worker.name,
      })}
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 'min(560px, 100vw)',
        background: 'var(--admin-bg)',
        borderLeft:
          '1px solid var(--admin-border)',
        boxShadow:
          '-4px 0 24px rgba(0, 0, 0, 0.25)',
        overflowY: 'auto',
        padding: 20,
        zIndex: 50,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <h2 style={{ margin: 0 }}>
          {t(`${WD}.headingPrefix`)} ·{' '}
          <code>{worker.name}</code>
        </h2>
        <MotionPress variant="ghost" onClick={onClose}>
          {t(`${WD}.close`)}
        </MotionPress>
      </div>

      <AdminPageNav
        scrollRoot={drawerRootRef.current}
        items={[
          { id: 'wd-env', label: t(`${WD}.envTitle`) },
          { id: 'wd-jobs', label: t(`${WD}.jobsTitle`) },
          { id: 'wd-events', label: t(`${WD}.eventsTitle`) },
          { id: 'wd-danger', label: t(`${WD}.danger`) },
        ]}
      />

      <p>
        <StatusPill
          kind={livenessKind}
          title={
            worker.last_seen_at
              ? `${t(`${WD}.lastSeen`)}: ${fmtDate(
                  worker.last_seen_at,
                )}`
              : undefined
          }
        >
          {livenessLabel}
        </StatusPill>
      </p>

      <table
        className="admin-table"
        style={{ width: '100%', marginBottom: 12 }}
      >
        <tbody>
          <tr>
            <th>{t(`${WD}.id`)}</th>
            <td className="admin-mono">
              {worker.id}
            </td>
          </tr>
          <tr>
            <th>{t(`${WD}.profile`)}</th>
            <td>
              <code>{worker.profile}</code>
            </td>
          </tr>
          <tr>
            <th>{t(`${WD}.allowedProfiles`)}</th>
            <td>
              {(
                worker.allowed_profiles || []
              ).join(', ') || '–'}
            </td>
          </tr>
          {!profileFix.hasGpuFull && (
            <tr>
              <th />
              <td>
                <p
                  className="admin-card__sub"
                  style={{ margin: '0 0 6px' }}
                >
                  {t(`${WD}.lyricsProfileHint`)}
                </p>
                <MotionPress
                  variant="ghost"
                  disabled={updateAllowlist.isPending}
                  onClick={() =>
                    updateAllowlist.mutate({
                      allowed_ip_cidrs: profileFix.cidrsForApi,
                      accept_open_allowlist: profileFix.needsOpenAccept,
                      allowed_profiles: profileFix.merged,
                    })
                  }
                >
                  {t(`${WD}.lyricsProfileFixButton`)}
                </MotionPress>
              </td>
            </tr>
          )}
          <tr>
            <th>{t(`${WD}.concurrency`)}</th>
            <td>{worker.max_concurrent_jobs}</td>
          </tr>
          <tr>
            <th>{t(`${WD}.packageVersion`)}</th>
            <td className="admin-mono">
              {worker.worker_package_version ||
                '–'}
            </td>
          </tr>
          <tr>
            <th>{t(`${WD}.claimsPause`)}</th>
            <td>
              {worker.claims_paused_until ? (
                <>
                  {fmtDate(
                    worker.claims_paused_until,
                  )}
                  {' · '}
                  <code>
                    {worker.claims_pause_reason ||
                      '–'}
                  </code>
                </>
              ) : (
                '–'
              )}
            </td>
          </tr>
          <tr>
            <th>{t(`${WD}.allowedIps`)}</th>
            <td className="admin-mono">
              {(
                worker.allowed_ip_cidrs || []
              ).join(', ') || t(`${WD}.noneCidr`)}
              <MotionPress
                variant="ghost"
                onClick={() =>
                  setEditCidrs(
                    (
                      worker.allowed_ip_cidrs ||
                      []
                    ).join('\n'),
                  )
                }
                style={{ marginLeft: 8 }}
              >
                {t(`${WD}.editCidr`)}
              </MotionPress>
            </td>
          </tr>
          <tr>
            <th>{t(`${WD}.lastSeen`)}</th>
            <td>{fmtDate(worker.last_seen_at)}</td>
          </tr>
          <tr>
            <th>{t(`${WD}.lastIp`)}</th>
            <td className="admin-mono">
              {worker.last_ip || '–'}
            </td>
          </tr>
          <tr>
            <th>{t(`${WD}.created`)}</th>
            <td>{fmtDate(worker.created_at)}</td>
          </tr>
        </tbody>
      </table>

      {editCidrs !== null && (
        <div className="admin-card admin-card--inline">
          <label>
            <div>{t(`${WD}.editCidrLabel`)}</div>
            <textarea
              rows={4}
              value={editCidrs}
              onChange={(e) =>
                setEditCidrs(e.target.value)
              }
              style={{ width: '100%' }}
            />
          </label>
          {editIsOpen && (
            <p>
              <StatusPill kind="error">
                {t(`${WD}.wildcardPill`)}
              </StatusPill>{' '}
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
                {t(`${WD}.wildcardLabel`)}
              </label>
            </p>
          )}
          <div
            style={{ display: 'flex', gap: 8 }}
          >
            <MotionPress
              variant="ghost"
              disabled={
                editParsed.length === 0 ||
                (editIsOpen && !acceptOpen) ||
                updateAllowlist.isPending
              }
              onClick={() =>
                updateAllowlist.mutate({
                  allowed_ip_cidrs: editParsed,
                  accept_open_allowlist:
                    editIsOpen,
                })
              }
            >
              {t(`${WD}.save`)}
            </MotionPress>
            <MotionPress
              variant="ghost"
              onClick={() => {
                setEditCidrs(null)
                setAcceptOpen(false)
              }}
            >
              {t(`${WD}.cancel`)}
            </MotionPress>
          </div>
        </div>
      )}

      {!worker.revoked_at && worker.active && (
        <div
          className="admin-card admin-card--inline"
          style={{ marginBottom: 12 }}
        >
          <h3 style={{ marginTop: 0 }}>
            {t(`${WD}.claimsControlTitle`)}
          </h3>
          <p
            className="admin-card__sub"
            style={{ margin: '0 0 8px' }}
          >
            {t(`${WD}.claimsControlHint`)}
          </p>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 8,
              alignItems: 'center',
            }}
          >
            <label
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'center',
              }}
            >
              <span>{t(`${WD}.pauseMinutes`)}</span>
              <input
                type="number"
                min={1}
                max={10080}
                value={pauseMinutes}
                onChange={(e) =>
                  setPauseMinutes(
                    Number(e.target.value) || 1,
                  )
                }
                style={{ width: 80 }}
              />
            </label>
            <MotionPress
              variant="ghost"
              disabled={pauseClaims.isPending}
              onClick={() =>
                pauseClaims.mutate({
                  minutes: pauseMinutes,
                  mode: 'soft',
                })
              }
            >
              {t(`${WD}.pauseSoft`)}
            </MotionPress>
            <MotionPress
              variant="ghost"
              disabled={pauseClaims.isPending}
              onClick={() =>
                pauseClaims.mutate({
                  minutes: pauseMinutes,
                  mode: 'drain',
                })
              }
            >
              {t(`${WD}.pauseDrain`)}
            </MotionPress>
            <MotionPress
              variant="ghost"
              disabled={resumeClaims.isPending}
              onClick={() => resumeClaims.mutate()}
            >
              {t(`${WD}.resumeClaims`)}
            </MotionPress>
          </div>
        </div>
      )}

      <h3 id="wd-env">{t(`${WD}.envTitle`)}</h3>
      <pre
        className="admin-mono"
        style={{
          padding: 12,
          borderRadius: 6,
          background: 'var(--admin-bg-elev)',
          border: '1px solid var(--admin-border)',
          overflowX: 'auto',
          fontSize: 12,
        }}
      >
        {envSnippet}
      </pre>
      <MotionPress variant="ghost" onClick={copy}>
        {copied
          ? t(`${AC}.copied`)
          : t(`${AC}.copy`)}
      </MotionPress>

      <h3 id="wd-jobs" style={{ marginTop: 20 }}>
        {t(`${WD}.jobsTitle`)}
      </h3>
      <p className="admin-card__sub" style={{ margin: '0 0 8px' }}>
        {t(`${WD}.jobsHint`)}
      </p>
      {workerJobs.isLoading && (
        <p>{t(`${WD}.loading`)}</p>
      )}
      {workerJobs.isError && (
        <p className="admin-card__sub">
          {String(workerJobs.error)}
        </p>
      )}
      {workerJobs.data && (
        <div style={{ marginBottom: 12 }}>
          {workerJobs.data.length === 0 ? (
            <p className="admin-card__sub">
              {t(`${WD}.jobsEmpty`)}
            </p>
          ) : (
            <table
              className="admin-table"
              style={{ width: '100%', fontSize: 12 }}
            >
              <thead>
                <tr>
                  <th>{t(`${WD}.tableJob`)}</th>
                  <th>{t(`${WD}.tableTrack`)}</th>
                  <th>{t(`${WD}.tableStatus`)}</th>
                  <th>{t(`${WD}.tableTier`)}</th>
                  <th>{t(`${WD}.tableStage`)}</th>
                  <th>{t(`${WD}.tableProgress`)}</th>
                </tr>
              </thead>
              <tbody>
                {workerJobs.data.map((row) => {
                  const ps = progressSummary(
                    row.lyrics_progress,
                  )
                  return (
                    <tr key={row.id}>
                      <td
                        className="admin-mono"
                        style={{ maxWidth: 100 }}
                        title={row.id}
                      >
                        {row.id.slice(0, 10)}…
                      </td>
                      <td>{row.track_id}</td>
                      <td>{row.status}</td>
                      <td>
                        {row.current_tier || '—'}
                      </td>
                      <td
                        className="admin-mono"
                        style={{ maxWidth: 140 }}
                        title={
                          ps.logs
                            ? ps.logs.join('\n')
                            : ps.stage
                        }
                      >
                        {ps.stage}
                        {ps.logs &&
                        ps.logs.length > 0
                          ? ` · ${ps.logs[ps.logs.length - 1]?.slice(0, 64)}${(ps.logs[ps.logs.length - 1]?.length || 0) > 64 ? '…' : ''}`
                          : null}
                      </td>
                      <td>{ps.percent}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      <h3 id="wd-events" style={{ marginTop: 8 }}>
        {t(`${WD}.eventsTitle`)}
      </h3>
      <p
        className="admin-card__sub"
        style={{ margin: '0 0 8px' }}
      >
        {wsOnline
          ? t(`${WD}.eventsHintLive`)
          : t(`${WD}.eventsHint`)}
      </p>
      {events.isLoading && (
        <p>{t(`${WD}.loading`)}</p>
      )}
      {events.isError && (
        <p className="admin-card__sub">
          {String(events.error)}
        </p>
      )}
      {!events.isLoading && (
        <ul
          style={{
            paddingLeft: 0,
            listStyle: 'none',
            maxHeight: 320,
            overflowY: 'auto',
            border:
              '1px solid var(--admin-border)',
            borderRadius: 6,
            padding: 8,
          }}
        >
          {displayEvents.length === 0 && (
            <li className="admin-card__sub">
              {t(`${WD}.eventsEmpty`)}
            </li>
          )}
          {displayEvents.map((ev) => (
            <li
              key={ev.id}
              style={{
                padding: '4px 0',
                borderBottom:
                  '1px dashed var(--admin-border)',
              }}
            >
              <span className="admin-card__sub">
                {fmtDate(ev.ts)}{' '}
              </span>
              <StatusPill
                kind={actionKind(
                  ev.action,
                  ev.status_code,
                )}
              >
                {ev.action}
              </StatusPill>{' '}
              {ev.job_id && (
                <span className="admin-mono">
                  job=
                  {ev.job_id.slice(0, 8)}{' '}
                </span>
              )}
              {ev.status_code && (
                <span className="admin-mono">
                  {ev.status_code}{' '}
                </span>
              )}
              {ev.ip && (
                <span className="admin-mono">
                  ip={ev.ip}{' '}
                </span>
              )}
              {Boolean(
                ev.meta &&
                  Object.keys(
                    (ev.meta as Record<
                      string,
                      unknown
                    >) || {},
                  ).length > 0,
              ) && (
                <span
                  className="admin-mono"
                  title={JSON.stringify(ev.meta)}
                >
                  [meta]
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <h3 id="wd-danger" style={{ marginTop: 20 }}>
        {t(`${WD}.danger`)}
      </h3>
      <div style={{ display: 'flex', gap: 8 }}>
        {!confirmRotate ? (
          <MotionPress
            variant="ghost"
            onClick={() => setConfirmRotate(true)}
          >
            {t(`${WD}.rotate`)}
          </MotionPress>
        ) : (
          <>
            <span className="admin-card__sub">
              {t(`${WD}.rotateHelp`)}
            </span>
            <MotionPress
              variant="ghost"
              onClick={() => rotateSecret.mutate()}
              disabled={rotateSecret.isPending}
            >
              {t(`${WD}.confirmRotate`)}
            </MotionPress>
            <MotionPress
              variant="ghost"
              onClick={() =>
                setConfirmRotate(false)
              }
            >
              {t(`${WD}.cancel`)}
            </MotionPress>
          </>
        )}
        {!confirmRevoke ? (
          <MotionPress
            variant="ghost"
            onClick={() => setConfirmRevoke(true)}
          >
            {t(`${WD}.revoke`)}
          </MotionPress>
        ) : (
          <>
            <span className="admin-card__sub">
              {t(`${WD}.revokeHelp`)}
            </span>
            <MotionPress
              variant="ghost"
              onClick={() => revokeWorker.mutate()}
              disabled={revokeWorker.isPending}
            >
              {t(`${WD}.confirmRevoke`)}
            </MotionPress>
            <MotionPress
              variant="ghost"
              onClick={() =>
                setConfirmRevoke(false)
              }
            >
              {t(`${WD}.cancel`)}
            </MotionPress>
          </>
        )}
      </div>

      {worker.revoked_at && onRequestDeleteRevoked && (
        <>
          <h3 style={{ marginTop: 20 }}>
            {t(`${WD}.removeFromListTitle`)}
          </h3>
          <p
            className="admin-card__sub"
            style={{ margin: '0 0 8px' }}
          >
            {t(`${WD}.removeFromListBody`)}
          </p>
          <div
            style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}
          >
            {!confirmDeleteFromList ? (
              <MotionPress
                variant="ghost"
                onClick={() => setConfirmDeleteFromList(true)}
                disabled={deleteFromListPending}
              >
                {t(`${WD}.removeFromList`)}
              </MotionPress>
            ) : (
              <>
                <span className="admin-card__sub">
                  {t(`${WD}.removeFromListHelp`)}
                </span>
                <MotionPress
                  variant="ghost"
                  onClick={() => {
                    onRequestDeleteRevoked()
                    setConfirmDeleteFromList(false)
                  }}
                  disabled={deleteFromListPending}
                >
                  {t(`${WD}.confirmRemoveFromList`)}
                </MotionPress>
                <MotionPress
                  variant="ghost"
                  onClick={() => setConfirmDeleteFromList(false)}
                >
                  {t(`${WD}.cancel`)}
                </MotionPress>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
