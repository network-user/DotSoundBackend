import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

interface TrackRow {
  id: number
  title: string
  artist: string | null
  source: string | null
  is_active: boolean
  uploaded_by_id: number | null
  created_at: string
}

const columns: ColumnDef<TrackRow>[] = [
  {
    header: 'ID',
    accessorKey: 'id',
    cell: (i) => (
      <span className="admin-mono">
        {i.getValue<number>()}
      </span>
    ),
  },
  { header: 'Title', accessorKey: 'title' },
  { header: 'Artist', accessorKey: 'artist' },
  { header: 'Source', accessorKey: 'source' },
  {
    header: 'Status',
    cell: (i) =>
      i.row.original.is_active ? (
        <StatusPill kind="ok">visible</StatusPill>
      ) : (
        <StatusPill kind="warn">hidden</StatusPill>
      ),
  },
  {
    header: 'Uploaded',
    cell: (i) =>
      new Date(
        i.row.original.created_at,
      ).toLocaleDateString(),
  },
]

export function TracksRoute() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const { data, isFetching } = useQuery({
    queryKey: ['admin', 'tracks', page, search],
    queryFn: () =>
      adminApi.listTracks({
        page,
        size: 25,
        search: search || undefined,
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
      <h1>{t('admin.tracks.title')}</h1>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t(
            'admin.tracks.searchPlaceholder',
          )}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
      </div>
      <DataTable
        columns={columns}
        rows={(data?.items || []) as TrackRow[]}
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
