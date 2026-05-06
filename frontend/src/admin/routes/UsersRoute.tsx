import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'
import { KpiCard } from '../components/widgets/KpiCard'
import { Sparkline } from '../components/charts/Sparkline'
import { LineChart } from '../components/charts/LineChart'

interface UserRow {
  id: number
  username: string | null
  email: string | null
  display_name: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

function userDisplayName(u: UserRow): string {
  return (
    u.username ??
    u.email ??
    `#${u.id}`
  )
}

export function UsersRoute() {
  const { t } = useTranslation()
  const { showConfirm, showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [activeOnly, setActiveOnly] =
    useState<boolean | undefined>(undefined)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [statsPeriod, setStatsPeriod] = useState<
    'today' | '7d' | '30d' | 'all'
  >('7d')
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
  const adminStats = useQuery({
    queryKey: ['admin', 'users', 'admin-stats', statsPeriod],
    queryFn: () => adminApi.dashboardAdminStats(statsPeriod),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })

  const total = data?.total || 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 25),
  )
  const rows = (data?.items || []) as unknown as UserRow[]
  const activeCount = rows.filter((u) => u.is_active).length
  const adminCount = rows.filter((u) => u.is_admin).length
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

  const refresh = () =>
    qc.invalidateQueries({ queryKey: ['admin', 'users'] })

  const handleBan = async (u: UserRow) => {
    const ok = await showConfirm(
      t('admin.users.confirmBan', {
        name: userDisplayName(u),
      }),
      { danger: true },
    )
    if (!ok) return
    setBusyId(u.id)
    try {
      await adminApi.banUser(u.id)
      refresh()
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
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
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusyId(null)
    }
  }

  const handleForceLogout = async (u: UserRow) => {
    const ok = await showConfirm(
      t('admin.users.confirmForceLogout', {
        name: userDisplayName(u),
      }),
    )
    if (!ok) return
    setBusyId(u.id)
    try {
      const res = await adminApi.forceLogoutUser(u.id)
      await showAlert(
        t('admin.users.forceLogoutResult', {
          adminCount: res.admin_sessions_revoked,
        }),
      )
    } catch (err) {
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
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
      await showAlert(
        t('admin.common.errorWithMessage', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusyId(null)
    }
  }

  const columns: ColumnDef<UserRow>[] = [
    {
      header: t('admin.users.colId'),
      accessorKey: 'id',
      cell: (i) => (
        <span className="admin-mono">
          {i.getValue<number>()}
        </span>
      ),
    },
    {
      header: t('admin.users.colUsername'),
      accessorKey: 'username',
    },
    {
      header: t('admin.users.colEmail'),
      accessorKey: 'email',
    },
    {
      header: t('admin.users.colStatus'),
      accessorKey: 'is_active',
      cell: (i) =>
        i.row.original.is_active ? (
          <StatusPill kind="ok">
            {t('admin.users.active')}
          </StatusPill>
        ) : (
          <StatusPill kind="error">
            {t('admin.users.banned')}
          </StatusPill>
        ),
    },
    {
      header: t('admin.users.colAdmin'),
      accessorKey: 'is_admin',
      cell: (i) =>
        i.row.original.is_admin ? (
          <StatusPill kind="warn">
            {t('admin.users.admin')}
          </StatusPill>
        ) : (
          '–'
        ),
    },
    {
      header: t('admin.users.colCreated'),
      accessorKey: 'created_at',
      cell: (i) =>
        new Date(
          i.row.original.created_at,
        ).toLocaleDateString(),
    },
    {
      header: '',
      id: 'actions',
      enableSorting: false,
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
                {t('admin.users.actionBan')}
              </Press>
            ) : (
              <Press
                variant="ghost"
                disabled={busy}
                onClick={() => handleUnban(u)}
              >
                {t('admin.users.actionUnban')}
              </Press>
            )}
            <Press
              variant="ghost"
              disabled={busy}
              onClick={() => handleForceLogout(u)}
            >
              {t('admin.users.actionLogout')}
            </Press>
            <Press
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setMessageTarget(u)
                setMessageText('')
              }}
            >
              {t('admin.users.actionMessage')}
            </Press>
          </div>
        )
      },
    },
  ]

  return (
    <div>
      <h1>{t('admin.users.title')}</h1>
      <section className="kpi-grid">
        <KpiCard
          label={t('admin.users.title')}
          value={total}
          hint={t('admin.common.total', { count: total })}
        />
        <KpiCard
          label={t('admin.users.filterActive')}
          value={activeCount}
          hint={t('admin.users.filterBanned')}
        />
        <KpiCard
          label={t('admin.users.colAdmin')}
          value={adminCount}
          hint={
            sparkline.length > 1 ? (
              <Sparkline
                data={sparkline}
                ariaLabel="Users growth sparkline"
              />
            ) : undefined
          }
        />
      </section>
      <section className="admin-card">
        <div className="admin-dashboard__toplist-head">
          <h2>Admin activity</h2>
          <div className="admin-range-switch">
            {(['today', '7d', '30d', 'all'] as const).map((period) => (
              <button
                key={period}
                type="button"
                className={`admin-range-switch__btn${
                  statsPeriod === period ? ' is-active' : ''
                }`}
                onClick={() => setStatsPeriod(period)}
              >
                {period}
              </button>
            ))}
          </div>
        </div>
        {adminStats.isLoading || !adminStats.data ? (
          <div className="admin-skeleton admin-skeleton--card" />
        ) : (
          <>
            <section className="kpi-grid">
              <KpiCard
                label="Total actions"
                value={adminStats.data.total_actions}
              />
              <KpiCard
                label="Unique admins"
                value={adminStats.data.unique_admins}
              />
            </section>
            <h3>Actions timeline</h3>
            <LineChart
              data={adminStats.data.actions_series}
              ariaLabel="Admin actions timeline"
            />
            <h3>Top admins</h3>
            {adminStats.data.top_admins.length === 0 ? (
              <div className="admin-log-empty">No data</div>
            ) : (
              <div className="admin-dashboard__toplist-rows">
                {adminStats.data.top_admins.map((item) => (
                  <div
                    key={item.user_id}
                    className="admin-dashboard__toplist-row"
                  >
                    <div className="admin-dashboard__toplist-title">
                      {item.name}
                    </div>
                    <div className="admin-dashboard__toplist-meta">
                      {item.actions} actions
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>
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
        rows={rows}
        enableSorting
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
              {t('admin.users.messageTitle', {
                name: userDisplayName(messageTarget),
              })}
            </h3>
            <div className="admin-dm-templates">
              {DM_TEMPLATES.map((tpl) => (
                <button
                  key={tpl.id}
                  type="button"
                  className="admin-dm-template-btn"
                  onClick={() =>
                    setMessageText(t(tpl.textKey))
                  }
                  title={t(tpl.textKey)}
                >
                  {t(tpl.labelKey)}
                </button>
              ))}
            </div>
            <textarea
              rows={5}
              maxLength={4000}
              value={messageText}
              onChange={(e) =>
                setMessageText(e.target.value)
              }
              placeholder={t(
                'admin.users.messageBodyPlaceholder',
              )}
              style={{ width: '100%', resize: 'vertical' }}
            />
            {messageText.trim() && (
              <div className="admin-dm-preview">
                <strong>
                  {t('admin.users.messageAsTeam')}
                </strong>
                <br />
                {messageText}
              </div>
            )}
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
                {t('admin.users.messageCancel')}
              </Press>
              <Press
                variant="primary"
                disabled={
                  !messageText.trim() ||
                  busyId === messageTarget.id
                }
                onClick={async () => {
                  const ok = await showConfirm(
                    t('admin.users.sendMessageConfirm'),
                  )
                  if (!ok) return
                  handleSendMessage()
                }}
              >
                {t('admin.users.messageSend')}
              </Press>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const DM_TEMPLATES: Array<{
  id: string
  labelKey: string
  textKey: string
}> = [
  {
    id: 'welcome',
    labelKey: 'admin.users.dmTemplateWelcomeLabel',
    textKey: 'admin.users.dmTemplateWelcomeText',
  },
  {
    id: 'warning',
    labelKey: 'admin.users.dmTemplateWarningLabel',
    textKey: 'admin.users.dmTemplateWarningText',
  },
  {
    id: 'rights',
    labelKey: 'admin.users.dmTemplateRightsLabel',
    textKey: 'admin.users.dmTemplateRightsText',
  },
  {
    id: 'restored',
    labelKey: 'admin.users.dmTemplateRestoredLabel',
    textKey: 'admin.users.dmTemplateRestoredText',
  },
]
