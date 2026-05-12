import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { adminApi } from '../lib/adminApi'
import { KpiCard } from '../components/widgets/KpiCard'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { ListPageTemplate } from '../components/layout/ListPageTemplate'

interface ScanEvent {
  id: number
  filename: string
  file_size: number | null
  verdict: string
  threat_name: string | null
  scan_mode: string
  scanned_at: string
}

const VERDICT_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'clean', label: 'Clean' },
  { value: 'infected', label: 'Infected' },
  { value: 'error', label: 'Error' },
  { value: 'skipped', label: 'Skipped' },
]

function verdictKind(
  v: string,
): 'ok' | 'error' | 'warn' | 'unknown' {
  if (v === 'clean') return 'ok'
  if (v === 'infected') return 'error'
  if (v === 'error') return 'warn'
  return 'unknown'
}

function fmtBytes(n: number | null): string {
  if (n === null) return '–'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

const eventColumns: ColumnDef<ScanEvent>[] = [
  {
    header: 'File',
    cell: (i) => (
      <span
        className="admin-mono"
        title={i.row.original.filename}
      >
        {i.row.original.filename.length > 48
          ? '…' +
            i.row.original.filename.slice(-48)
          : i.row.original.filename}
      </span>
    ),
  },
  {
    header: 'Size',
    cell: (i) => fmtBytes(i.row.original.file_size),
  },
  {
    header: 'Verdict',
    cell: (i) => (
      <StatusPill kind={verdictKind(i.row.original.verdict)}>
        {i.row.original.verdict}
      </StatusPill>
    ),
  },
  {
    header: 'Threat',
    cell: (i) => i.row.original.threat_name || '–',
  },
  {
    header: 'Mode',
    accessorKey: 'scan_mode',
  },
  {
    header: 'When',
    cell: (i) =>
      new Date(i.row.original.scanned_at).toLocaleString(),
  },
]

export function AntivirusRoute() {
  const [verdictFilter, setVerdictFilter] = useState('')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 100

  const statusQ = useQuery({
    queryKey: ['admin', 'antivirus', 'status'],
    queryFn: () => adminApi.antivirusStatus(),
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  })

  const statsQ = useQuery({
    queryKey: ['admin', 'antivirus', 'stats'],
    queryFn: () => adminApi.antivirusStats(),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })

  const eventsQ = useQuery({
    queryKey: [
      'admin',
      'antivirus',
      'events',
      verdictFilter,
      page,
    ],
    queryFn: () =>
      adminApi.antivirusEvents({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        verdict: verdictFilter || undefined,
      }),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })

  function refetchAll() {
    statusQ.refetch()
    statsQ.refetch()
    eventsQ.refetch()
  }

  const status = statusQ.data
  const stats = statsQ.data
  const events = eventsQ.data

  return (
    <ListPageTemplate
      title="Antivirus"
      subtitle="ClamAV file scan status and history"
      actions={
        <MotionPress
          variant="ghost"
          haptic="selection"
          onClick={refetchAll}
          disabled={
            statusQ.isFetching ||
            statsQ.isFetching ||
            eventsQ.isFetching
          }
        >
          <Icon name="refresh" size={14} />
          <span style={{ marginLeft: 6 }}>Refresh</span>
        </MotionPress>
      }
    >
      <section className="admin-card">
        <h2>Scanner status</h2>
        <div className="admin-kpi-row">
          <KpiCard
            label="ClamAV"
            value={
              statusQ.isLoading
                ? '…'
                : status?.reachable
                  ? 'Online'
                  : 'Offline'
            }
            accent={
              statusQ.isLoading
                ? 'default'
                : status?.reachable
                  ? 'default'
                  : 'error'
            }
          />
          <KpiCard
            label="Mode"
            value={status?.mode ?? '–'}
          />
          <KpiCard
            label="Version"
            value={status?.version ?? '–'}
            hint={
              status?.host
                ? `${status.host}:${status.port}`
                : undefined
            }
          />
          {status?.error && (
            <KpiCard
              label="Error"
              value={status.error}
              accent="warn"
            />
          )}
        </div>
      </section>

      <section className="admin-card">
        <h2>Scan statistics</h2>
        <div className="admin-kpi-row">
          <KpiCard
            label="Total scanned"
            value={stats?.total ?? '–'}
          />
          <KpiCard
            label="Clean"
            value={stats?.clean ?? '–'}
            accent="default"
          />
          <KpiCard
            label="Infected"
            value={stats?.infected ?? '–'}
            accent={
              (stats?.infected ?? 0) > 0 ? 'error' : 'default'
            }
          />
          <KpiCard
            label="Errors"
            value={stats?.error ?? '–'}
            accent={
              (stats?.error ?? 0) > 0 ? 'warn' : 'default'
            }
          />
          <KpiCard
            label="Skipped"
            value={stats?.skipped ?? '–'}
          />
        </div>
      </section>

      <section className="admin-card">
        <h2>Scan events</h2>
        <div className="admin-toolbar">
          <select
            className="admin-select"
            value={verdictFilter}
            onChange={(e) => {
              setVerdictFilter(e.target.value)
              setPage(0)
            }}
          >
            {VERDICT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {(events?.total ?? 0) > PAGE_SIZE && (
            <div className="admin-pagination">
              <MotionPress
                variant="ghost"
                onClick={() =>
                  setPage((p) => Math.max(0, p - 1))
                }
                disabled={page === 0}
              >
                Prev
              </MotionPress>
              <span className="admin-pagination__info">
                {page * PAGE_SIZE + 1}–
                {Math.min(
                  (page + 1) * PAGE_SIZE,
                  events?.total ?? 0,
                )}{' '}
                / {events?.total}
              </span>
              <MotionPress
                variant="ghost"
                onClick={() => setPage((p) => p + 1)}
                disabled={
                  (page + 1) * PAGE_SIZE >=
                  (events?.total ?? 0)
                }
              >
                Next
              </MotionPress>
            </div>
          )}
        </div>
        <DataTable
          columns={eventColumns}
          rows={(events?.items ?? []) as ScanEvent[]}
          isLoading={eventsQ.isLoading}
          error={
            eventsQ.error
              ? (eventsQ.error as Error).message
              : null
          }
          onRetry={() => eventsQ.refetch()}
          emptyHint="No scan events yet"
        />
      </section>
    </ListPageTemplate>
  )
}
