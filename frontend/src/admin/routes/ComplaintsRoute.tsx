import { useState } from 'react'
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
  return (
    <div>
      <h1>{t('admin.complaints.title')}</h1>
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
        rows={
          (data?.items || []) as unknown as ComplaintRow[]
        }
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
