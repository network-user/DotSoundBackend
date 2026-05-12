import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  keepPreviousData,
  useQuery,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { getAdminPanelRoute } from '@/lib/adminPath'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { ListPageTemplate } from '../components/layout/ListPageTemplate'
import {
  FilterGroup,
  type FilterDef,
} from '../components/widgets/FilterGroup'

interface AlbumRow {
  id: number
  title: string
  owner_id: number
  is_public: boolean
  created_at: string
  track_count: number
}

export function AlbumsListRoute() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isFetching, isLoading, error, refetch } =
    useQuery({
      queryKey: ['admin', 'albums', page, search],
      queryFn: () =>
        adminApi.listAdminAlbums({
          page,
          size: 25,
          search: search || undefined,
        }),
      placeholderData: keepPreviousData,
    })

  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / 25))
  const rows = (data?.items ?? []) as AlbumRow[]

  const columns: ColumnDef<AlbumRow>[] = [
    {
      accessorKey: 'id',
      header: t('admin.albums.colId'),
      cell: ({ row }) => row.original.id,
    },
    {
      accessorKey: 'title',
      header: t('admin.albums.colTitle'),
      cell: ({ row }) => row.original.title,
    },
    {
      accessorKey: 'owner_id',
      header: t('admin.albums.colOwner'),
      cell: ({ row }) => row.original.owner_id,
    },
    {
      accessorKey: 'track_count',
      header: t('admin.albums.colTracks'),
      cell: ({ row }) => row.original.track_count,
    },
    {
      id: 'pub',
      header: t('admin.albums.colPublic'),
      cell: ({ row }) =>
        row.original.is_public ? (
          <StatusPill kind="ok">
            {t('admin.albums.public')}
          </StatusPill>
        ) : (
          <StatusPill kind="warn">
            {t('admin.albums.private')}
          </StatusPill>
        ),
    },
    {
      id: 'open',
      header: '',
      cell: ({ row }) => (
        <MotionPress
          variant="ghost"
          onClick={() =>
            navigate(
              getAdminPanelRoute(`/albums/${row.original.id}`),
            )
          }
        >
          {t('admin.albums.open')}
        </MotionPress>
      ),
    },
  ]

  const filters: FilterDef[] = [
    {
      type: 'search',
      key: 'q',
      placeholder: t('admin.albums.searchPlaceholder'),
      ariaLabel: t('admin.albums.searchPlaceholder'),
    },
  ]

  return (
    <ListPageTemplate
      title={t('admin.albums.title')}
      subtitle={t('admin.albums.listHint')}
      filters={
        <FilterGroup
          filters={filters}
          values={{ q: search || undefined }}
          onChange={(_, v) => {
            setSearch(v ?? '')
            setPage(1)
          }}
        />
      }
      toolbarHint={t('admin.common.total', { count: total })}
      pagination={
        <>
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
            {page} / {totalPages}
          </span>
          <MotionPress
            variant="ghost"
            disabled={page >= totalPages || isFetching}
            onClick={() =>
              setPage((p) => Math.min(totalPages, p + 1))
            }
          >
            {t('admin.common.next')}
          </MotionPress>
        </>
      }
    >
      <DataTable
        columns={columns}
        rows={rows}
        isLoading={isLoading}
        error={error ? (error as Error).message : null}
        onRetry={() => refetch()}
        emptyHint={t('admin.albums.empty')}
      />
    </ListPageTemplate>
  )
}
