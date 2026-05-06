import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { api } from '@/lib/api'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { KpiCard } from '../components/widgets/KpiCard'
import { Sparkline } from '../components/charts/Sparkline'

interface ComplaintRow {
  id: number
  track_id: number
  reason: string
  reason_type: string
  is_resolved: boolean
  created_at: string
}

async function resolveAction(
  id: number,
  action: 'accept' | 'dismiss' | 'in_progress',
  note?: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    await api.updateComplaintStatus(id, {
      action,
      note,
    })
    return { ok: true }
  } catch (e) {
    const msg = e instanceof Error ? e.message : '0'
    if (msg === '404') {
      return { ok: false, error: 'not_implemented' }
    }
    return { ok: false, error: msg }
  }
}

function ActionsCell({
  complaint,
  onChange,
}: {
  complaint: ComplaintRow
  onChange: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [hint, setHint] = useState<string | null>(
    null,
  )

  const handle = async (
    action: 'accept' | 'dismiss' | 'in_progress',
  ) => {
    setBusy(true)
    setHint(null)
    const note =
      action === 'accept'
        ? window.prompt(
            'Краткий комментарий пользователю (опц.):',
          ) || undefined
        : undefined
    const res = await resolveAction(
      complaint.id,
      action,
      note,
    )
    setBusy(false)
    if (!res.ok && res.error === 'not_implemented') {
      setHint('Endpoint не реализован на backend')
    } else if (!res.ok) {
      setHint(`Ошибка ${res.error}`)
    } else {
      setHint('OK')
      onChange()
    }
  }

  if (complaint.is_resolved) return null

  return (
    <div
      style={{
        display: 'flex',
        gap: 6,
        flexWrap: 'wrap',
      }}
    >
      <Press
        variant="primary"
        disabled={busy}
        onClick={() => handle('accept')}
      >
        Принять
      </Press>
      <Press
        variant="ghost"
        disabled={busy}
        onClick={() => handle('dismiss')}
      >
        Отклонить
      </Press>
      <Press
        variant="ghost"
        disabled={busy}
        onClick={() => handle('in_progress')}
      >
        В работе
      </Press>
      {hint && (
        <span
          style={{
            fontSize: 12,
            color: 'var(--text-secondary)',
          }}
        >
          {hint}
        </span>
      )}
    </div>
  )
}

export function ComplaintsRoute() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [unresolvedOnly, setUnresolvedOnly] =
    useState(true)
  const queryKey = [
    'admin',
    'complaints',
    page,
    unresolvedOnly,
  ] as const
  const { data, isFetching } = useQuery({
    queryKey,
    queryFn: () =>
      adminApi.listComplaints({
        page,
        size: 25,
        unresolved_only: unresolvedOnly,
      }),
    placeholderData: keepPreviousData,
  })

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey })

  const columns: ColumnDef<ComplaintRow>[] = [
    {
      header: 'ID',
      accessorKey: 'id',
      cell: (i) => (
        <span className="admin-mono">
          {i.getValue<number>()}
        </span>
      ),
    },
    { header: 'Track', accessorKey: 'track_id' },
    { header: 'Reason', accessorKey: 'reason' },
    { header: 'Type', accessorKey: 'reason_type' },
    {
      header: 'Status',
      cell: (i) =>
        i.row.original.is_resolved ? (
          <StatusPill kind="ok">resolved</StatusPill>
        ) : (
          <StatusPill kind="warn">open</StatusPill>
        ),
    },
    {
      header: 'Created',
      cell: (i) =>
        new Date(
          i.row.original.created_at,
        ).toLocaleString(),
    },
    {
      header: 'Действия',
      id: 'actions',
      cell: (i) => (
        <ActionsCell
          complaint={i.row.original}
          onChange={refresh}
        />
      ),
    },
  ]

  const total = data?.total || 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 25),
  )
  const rows =
    (data?.items || []) as unknown as ComplaintRow[]
  const openCount = rows.filter((r) => !r.is_resolved).length
  const resolvedCount = rows.filter((r) => r.is_resolved).length
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
  return (
    <div>
      <h1>{t('admin.complaints.title')}</h1>
      <section className="kpi-grid">
        <KpiCard
          label={t('admin.complaints.title')}
          value={total}
          hint={t('admin.common.total', { count: total })}
        />
        <KpiCard
          label="Open"
          value={openCount}
          accent={openCount > 0 ? 'warn' : 'default'}
        />
        <KpiCard
          label="Resolved"
          value={resolvedCount}
          hint={
            sparkline.length > 1 ? (
              <Sparkline
                data={sparkline}
                ariaLabel="Complaints sparkline"
              />
            ) : undefined
          }
        />
      </section>
      <div className="admin-toolbar">
        <label className="admin-checkbox">
          <input
            type="checkbox"
            checked={unresolvedOnly}
            onChange={(e) => {
              setUnresolvedOnly(
                e.target.checked,
              )
              setPage(1)
            }}
          />
          {t('admin.complaints.unresolvedOnly')}
        </label>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
      />
      <div className="admin-pagination">
        <Press
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() =>
            setPage((p) => Math.max(1, p - 1))
          }
        >
          {t('admin.common.prev')}
        </Press>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <Press
          variant="ghost"
          disabled={
            page >= totalPages || isFetching
          }
          onClick={() => setPage((p) => p + 1)}
        >
          {t('admin.common.next')}
        </Press>
      </div>
    </div>
  )
}
