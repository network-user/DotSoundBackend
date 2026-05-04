import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  keepPreviousData,
  useQuery,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

interface PlaylistRow {
  id: number
  name: string
  owner_id: number
  is_public: boolean
  created_at: string
  track_count: number
}

export function PlaylistsListRoute() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isFetching } = useQuery({
    queryKey: ['admin', 'playlists', page, search],
    queryFn: () =>
      adminApi.listAdminPlaylists({
        page,
        size: 25,
        search: search || undefined,
      }),
    placeholderData: keepPreviousData,
  })

  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / 25))
  const rows = (data?.items ?? []) as PlaylistRow[]

  const columns: ColumnDef<PlaylistRow>[] = [
    {
      accessorKey: 'id',
      header: t('admin.playlists.colId'),
      cell: ({ row }) => row.original.id,
    },
    {
      accessorKey: 'name',
      header: t('admin.playlists.colName'),
      cell: ({ row }) => row.original.name,
    },
    {
      accessorKey: 'owner_id',
      header: t('admin.playlists.colOwner'),
      cell: ({ row }) => row.original.owner_id,
    },
    {
      accessorKey: 'track_count',
      header: t('admin.playlists.colTracks'),
      cell: ({ row }) => row.original.track_count,
    },
    {
      id: 'pub',
      header: t('admin.playlists.colPublic'),
      cell: ({ row }) =>
        row.original.is_public ? (
          <StatusPill kind="ok">
            {t('admin.playlists.public')}
          </StatusPill>
        ) : (
          <StatusPill kind="warn">
            {t('admin.playlists.private')}
          </StatusPill>
        ),
    },
    {
      id: 'open',
      header: '',
      cell: ({ row }) => (
        <Press
          variant="ghost"
          onClick={() =>
            navigate(`/admin/playlists/${row.original.id}`)
          }
        >
          {t('admin.playlists.open')}
        </Press>
      ),
    },
  ]

  return (
    <section className="admin-card">
      <h1>{t('admin.playlists.title')}</h1>
      <p className="admin-card__sub">
        {t('admin.playlists.listHint')}
      </p>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t('admin.playlists.searchPlaceholder')}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        emptyHint={t('admin.playlists.empty')}
      />
      <div className="admin-pagination">
        <Press
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          {t('admin.common.prev')}
        </Press>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <Press
          variant="ghost"
          disabled={page >= totalPages || isFetching}
          onClick={() =>
            setPage((p) => Math.min(totalPages, p + 1))
          }
        >
          {t('admin.common.next')}
        </Press>
      </div>
    </section>
  )
}
