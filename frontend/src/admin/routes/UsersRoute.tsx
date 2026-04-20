import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
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

export function UsersRoute() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [activeOnly, setActiveOnly] =
    useState<boolean | undefined>(undefined)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [messageTarget, setMessageTarget] = useState<UserRow | null>(null)
  const [messageText, setMessageText] = useState('')
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

  const refresh = () =>
    qc.invalidateQueries({ queryKey: ['admin', 'users'] })

  const handleBan = async (u: UserRow) => {
    if (!window.confirm(`Забанить пользователя ${u.username ?? u.id}?`)) return
    setBusyId(u.id)
    try {
      await adminApi.banUser(u.id)
      refresh()
    } catch (err) {
      alert('Ошибка: ' + (err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleUnban = async (u: UserRow) => {
    setBusyId(u.id)
    try {
      await adminApi.unbanUser(u.id)
      refresh()
    } catch (err) {
      alert('Ошибка: ' + (err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleForceLogout = async (u: UserRow) => {
    if (
      !window.confirm(
        `Принудительно завершить все сессии пользователя ${u.username ?? u.id}?`,
      )
    )
      return
    setBusyId(u.id)
    try {
      const res = await adminApi.forceLogoutUser(u.id)
      alert(
        `Отозвано admin-сессий: ${res.admin_sessions_revoked}. Пользовательский revoke-маркер установлен.`,
      )
    } catch (err) {
      alert('Ошибка: ' + (err as Error).message)
    } finally {
      setBusyId(null)
    }
  }

  const handleSendMessage = async () => {
    if (!messageTarget || !messageText.trim()) return
    setBusyId(messageTarget.id)
    try {
      await adminApi.sendAdminMessage(
        messageTarget.id,
        messageText.trim(),
      )
      setMessageTarget(null)
      setMessageText('')
    } catch (err) {
      alert('Ошибка: ' + (err as Error).message)
    } finally {
      setBusyId(null)
    }
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
    {
      header: '',
      id: 'actions',
      cell: (i) => {
        const u = i.row.original
        const busy = busyId === u.id
        return (
          <div
            style={{
              display: 'flex',
              gap: 6,
              flexWrap: 'wrap',
            }}
          >
            {u.is_active ? (
              <Press
                variant="ghost"
                disabled={busy}
                onClick={() => handleBan(u)}
              >
                Бан
              </Press>
            ) : (
              <Press
                variant="ghost"
                disabled={busy}
                onClick={() => handleUnban(u)}
              >
                Разбан
              </Press>
            )}
            <Press
              variant="ghost"
              disabled={busy}
              onClick={() => handleForceLogout(u)}
            >
              Logout
            </Press>
            <Press
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setMessageTarget(u)
                setMessageText('')
              }}
            >
              Сообщение
            </Press>
          </div>
        )
      },
    },
  ]

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
      {messageTarget && (
        <div
          className="admin-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setMessageTarget(null)
              setMessageText('')
            }
          }}
        >
          <div className="admin-modal">
            <h3>
              Сообщение для{' '}
              {messageTarget.username ??
                messageTarget.email ??
                `#${messageTarget.id}`}
            </h3>
            <textarea
              rows={5}
              maxLength={4000}
              value={messageText}
              onChange={(e) =>
                setMessageText(e.target.value)
              }
              placeholder="Текст сообщения…"
              style={{ width: '100%', resize: 'vertical' }}
            />
            <div
              style={{
                display: 'flex',
                gap: 8,
                justifyContent: 'flex-end',
                marginTop: 12,
              }}
            >
              <Press
                variant="ghost"
                onClick={() => {
                  setMessageTarget(null)
                  setMessageText('')
                }}
              >
                Отмена
              </Press>
              <Press
                variant="primary"
                disabled={
                  !messageText.trim() ||
                  busyId === messageTarget.id
                }
                onClick={handleSendMessage}
              >
                Отправить
              </Press>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
