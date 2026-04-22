import { useMemo, useState } from 'react'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { Press } from '@/components/ui/Press'
import { adminFetch } from '../../lib/adminApi'
import { StatusPill } from './StatusPill'

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

interface Props {
  worker: WorkerRow
  backendBaseUrl: string
  onClose: () => void
  onSecretShown: (secret: string) => void
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

export function WorkerDetailDrawer({
  worker,
  backendBaseUrl,
  onClose,
  onSecretShown,
}: Props) {
  const qc = useQueryClient()
  const [confirmRevoke, setConfirmRevoke] =
    useState(false)
  const [confirmRotate, setConfirmRotate] =
    useState(false)
  const [editCidrs, setEditCidrs] = useState<
    string | null
  >(null)
  const [acceptOpen, setAcceptOpen] = useState(false)
  const [copied, setCopied] = useState(false)

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
    refetchInterval: 5_000,
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

  const status: 'ok' | 'warn' | 'error' = worker.revoked_at
    ? 'error'
    : worker.suspended_until
      ? 'warn'
      : worker.active
        ? 'ok'
        : 'error'

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
      role="dialog"
      aria-label={`Worker ${worker.name}`}
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
          Worker · <code>{worker.name}</code>
        </h2>
        <Press variant="ghost" onClick={onClose}>
          Close
        </Press>
      </div>

      <p>
        <StatusPill kind={status}>
          {worker.revoked_at
            ? 'revoked'
            : worker.suspended_until
              ? `suspended until ${fmtDate(
                  worker.suspended_until,
                )}`
              : worker.active
                ? 'active'
                : worker.suspended_reason ||
                  'inactive'}
        </StatusPill>
      </p>

      <table
        className="admin-table"
        style={{ width: '100%', marginBottom: 12 }}
      >
        <tbody>
          <tr>
            <th>ID</th>
            <td className="admin-mono">
              {worker.id}
            </td>
          </tr>
          <tr>
            <th>Profile</th>
            <td>
              <code>{worker.profile}</code>
            </td>
          </tr>
          <tr>
            <th>Allowed profiles</th>
            <td>
              {(
                worker.allowed_profiles || []
              ).join(', ') || '–'}
            </td>
          </tr>
          <tr>
            <th>Concurrency</th>
            <td>{worker.max_concurrent_jobs}</td>
          </tr>
          <tr>
            <th>Allowed IPs</th>
            <td className="admin-mono">
              {(
                worker.allowed_ip_cidrs || []
              ).join(', ') || '(none)'}
              <Press
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
                Edit
              </Press>
            </td>
          </tr>
          <tr>
            <th>Last seen</th>
            <td>{fmtDate(worker.last_seen_at)}</td>
          </tr>
          <tr>
            <th>Last IP</th>
            <td className="admin-mono">
              {worker.last_ip || '–'}
            </td>
          </tr>
          <tr>
            <th>Created</th>
            <td>{fmtDate(worker.created_at)}</td>
          </tr>
        </tbody>
      </table>

      {editCidrs !== null && (
        <div className="admin-card admin-card--inline">
          <label>
            <div>Edit allowed CIDRs:</div>
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
                wildcard
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
                I accept the risk of allowing all
                IPs
              </label>
            </p>
          )}
          <div
            style={{ display: 'flex', gap: 8 }}
          >
            <Press
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
              Save
            </Press>
            <Press
              variant="ghost"
              onClick={() => {
                setEditCidrs(null)
                setAcceptOpen(false)
              }}
            >
              Cancel
            </Press>
          </div>
        </div>
      )}

      <h3>.env snippet (paste into worker)</h3>
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
      <Press variant="ghost" onClick={copy}>
        {copied ? 'Copied!' : 'Copy'}
      </Press>

      <h3 style={{ marginTop: 20 }}>
        Recent events (auto-refreshes every 5s)
      </h3>
      {events.isLoading && <p>Loading…</p>}
      {events.data && (
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
          {events.data.events.length === 0 && (
            <li className="admin-card__sub">
              No events yet. The worker hasn't
              talked to Backend or it talked
              before this stream started.
            </li>
          )}
          {events.data.events.map((ev) => (
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
              {ev.meta &&
                Object.keys(
                  (ev.meta as Record<
                    string,
                    unknown
                  >) || {},
                ).length > 0 && (
                  <span
                    className="admin-mono"
                    title={JSON.stringify(
                      ev.meta,
                    )}
                  >
                    [meta]
                  </span>
                )}
            </li>
          ))}
        </ul>
      )}

      <h3 style={{ marginTop: 20 }}>
        Dangerous actions
      </h3>
      <div style={{ display: 'flex', gap: 8 }}>
        {!confirmRotate ? (
          <Press
            variant="ghost"
            onClick={() => setConfirmRotate(true)}
          >
            Rotate secret
          </Press>
        ) : (
          <>
            <span className="admin-card__sub">
              This invalidates the current secret
              and shows you a new one once.
            </span>
            <Press
              variant="ghost"
              onClick={() => rotateSecret.mutate()}
              disabled={rotateSecret.isPending}
            >
              Confirm rotate
            </Press>
            <Press
              variant="ghost"
              onClick={() =>
                setConfirmRotate(false)
              }
            >
              Cancel
            </Press>
          </>
        )}
        {!confirmRevoke ? (
          <Press
            variant="ghost"
            onClick={() => setConfirmRevoke(true)}
          >
            Revoke worker
          </Press>
        ) : (
          <>
            <span className="admin-card__sub">
              This revokes the worker permanently
              and cascades any in-flight jobs to
              the next tier.
            </span>
            <Press
              variant="ghost"
              onClick={() => revokeWorker.mutate()}
              disabled={revokeWorker.isPending}
            >
              Confirm revoke
            </Press>
            <Press
              variant="ghost"
              onClick={() =>
                setConfirmRevoke(false)
              }
            >
              Cancel
            </Press>
          </>
        )}
      </div>
    </div>
  )
}
