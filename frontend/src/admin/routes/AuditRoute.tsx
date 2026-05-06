import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { JsonViewer } from '../components/widgets/JsonViewer'
import { useCapability } from '../hooks/useCapability'

interface AuditRow {
  id: number
  user_id: number
  action: string
  target_type: string | null
  target_id: string | null
  ip: string | null
  meta: unknown
  created_at: string
}

const columns: ColumnDef<AuditRow>[] = [
  {
    header: 'When',
    cell: (i) =>
      new Date(
        i.row.original.created_at,
      ).toLocaleString(),
  },
  { header: 'User', accessorKey: 'user_id' },
  {
    header: 'Action',
    accessorKey: 'action',
    cell: (i) => (
      <span className="admin-mono">
        {i.getValue<string>()}
      </span>
    ),
  },
  {
    header: 'Target',
    cell: (i) =>
      i.row.original.target_type
        ? `${i.row.original.target_type}:${i.row.original.target_id || '–'}`
        : '–',
  },
  { header: 'IP', accessorKey: 'ip' },
  {
    header: 'Meta',
    cell: (i) =>
      i.row.original.meta ? (
        <JsonViewer
          value={i.row.original.meta}
          collapsed
        />
      ) : (
        '–'
      ),
  },
]

export function AuditRoute() {
  const { t } = useTranslation()
  const canExport = useCapability('audit.export')
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const [userId, setUserId] = useState('')
  const { data, isFetching, isError, error } =
    useQuery({
      queryKey: [
        'admin',
        'audit',
        page,
        action,
        userId,
      ],
      queryFn: () =>
        adminApi.listAudit({
          page,
          size: 50,
          action: action || undefined,
          user_id: userId
            ? Number(userId)
            : undefined,
        }),
      placeholderData: keepPreviousData,
    })
  const total = data?.total || 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 50),
  )
  return (
    <div>
      <h1>{t('admin.audit.title')}</h1>
      {isError && (
        <div className="admin-error" role="alert">
          {error instanceof Error
            ? error.message
            : String(error)}
        </div>
      )}
      <div className="admin-toolbar">
        <input
          type="text"
          placeholder={t(
            'admin.audit.actionPlaceholder',
          )}
          value={action}
          onChange={(e) => {
            setAction(e.target.value)
            setPage(1)
          }}
        />
        <input
          type="text"
          placeholder={t(
            'admin.audit.userPlaceholder',
          )}
          inputMode="numeric"
          value={userId}
          onChange={(e) => {
            setUserId(
              e.target.value.replace(/\D/g, ''),
            )
            setPage(1)
          }}
        />
        {canExport && (
          <a
            className="admin-link"
            href="/api/v1/admin/audit/export.csv"
            target="_blank"
            rel="noreferrer"
          >
            {t('admin.audit.export')}
          </a>
        )}
      </div>
      <DataTable
        columns={columns}
        rows={(data?.items || []) as unknown as AuditRow[]}
      />
      <div className="admin-pagination">
        <MotionPress
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() =>
            setPage((p) => Math.max(1, p - 1))
          }
        >
          {t('admin.common.prev')}
        </MotionPress>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <MotionPress
          variant="ghost"
          disabled={
            page >= totalPages || isFetching
          }
          onClick={() => setPage((p) => p + 1)}
        >
          {t('admin.common.next')}
        </MotionPress>
      </div>
    </div>
  )
}
