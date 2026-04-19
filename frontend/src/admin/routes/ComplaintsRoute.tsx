import { useState } from 'react'
import {
  keepPreviousData,
  useQuery,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
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
  {
    header: 'Track',
    accessorKey: 'track_id',
  },
  { header: 'Reason', accessorKey: 'reason' },
  {
    header: 'Type',
    accessorKey: 'reason_type',
  },
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
]

export function ComplaintsRoute() {
  const [page, setPage] = useState(1)
  const [unresolvedOnly, setUnresolvedOnly] =
    useState(true)
  const { data, isFetching } = useQuery({
    queryKey: [
      'admin',
      'complaints',
      page,
      unresolvedOnly,
    ],
    queryFn: () =>
      adminApi.listComplaints({
        page,
        size: 25,
        unresolved_only: unresolvedOnly,
      }),
    placeholderData: keepPreviousData,
  })
  const total = data?.total || 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 25),
  )
  return (
    <div>
      <h1>Complaints</h1>
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
          Unresolved only
        </label>
      </div>
      <DataTable
        columns={columns}
        rows={
          (data?.items || []) as ComplaintRow[]
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
          Prev
        </Press>
        <span>
          {page} / {totalPages} · {total} total
        </span>
        <Press
          variant="ghost"
          disabled={
            page >= totalPages || isFetching
          }
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </Press>
      </div>
    </div>
  )
}
