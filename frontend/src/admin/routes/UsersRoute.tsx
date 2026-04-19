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

interface UserRow {
  id: number
  username: string | null
  email: string | null
  display_name: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

const columns: ColumnDef<UserRow>[] = [
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
    header: 'Username',
    accessorKey: 'username',
  },
  {
    header: 'Email',
    accessorKey: 'email',
  },
  {
    header: 'Status',
    cell: (i) =>
      i.row.original.is_active ? (
        <StatusPill kind="ok">active</StatusPill>
      ) : (
        <StatusPill kind="error">banned</StatusPill>
      ),
  },
  {
    header: 'Admin',
    cell: (i) =>
      i.row.original.is_admin ? (
        <StatusPill kind="warn">admin</StatusPill>
      ) : (
        '–'
      ),
  },
  {
    header: 'Created',
    cell: (i) =>
      new Date(
        i.row.original.created_at,
      ).toLocaleDateString(),
  },
]

export function UsersRoute() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [activeOnly, setActiveOnly] =
    useState<boolean | undefined>(undefined)
  const { data, isFetching } = useQuery({
    queryKey: [
      'admin',
      'users',
      page,
      search,
      activeOnly,
    ],
    queryFn: () =>
      adminApi.listUsers({
        page,
        size: 25,
        search: search || undefined,
        is_active: activeOnly,
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
      <h1>{t('admin.users.title')}</h1>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t(
            'admin.users.searchPlaceholder',
          )}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <select
          value={
            activeOnly === undefined
              ? 'all'
              : activeOnly
                ? 'active'
                : 'banned'
          }
          onChange={(e) => {
            const v = e.target.value
            setActiveOnly(
              v === 'all'
                ? undefined
                : v === 'active',
            )
            setPage(1)
          }}
        >
          <option value="all">
            {t('admin.users.filterAll')}
          </option>
          <option value="active">
            {t('admin.users.filterActive')}
          </option>
          <option value="banned">
            {t('admin.users.filterBanned')}
          </option>
        </select>
      </div>
      <DataTable
        columns={columns}
        rows={(data?.items || []) as UserRow[]}
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
