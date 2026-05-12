import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { MotionPress } from '@/components/ui/MotionPress'
import { Icon } from '@/components/Icon/Icon'
import { adminApi } from '../lib/adminApi'
import { StatusPill } from '../components/widgets/StatusPill'
import { DataTable } from '../components/widgets/DataTable'
import { ListPageTemplate } from '../components/layout/ListPageTemplate'
import type { ColumnDef } from '@tanstack/react-table'

interface ContainerRow {
  name: string
  status: string
  health: string
  uptime_seconds: number | null
  restart_count: number
  cpu_pct: number | null
  mem_mb: number | null
  image: string | null
}

function statusKind(
  status: string,
  health: string,
): 'ok' | 'warn' | 'error' | 'unknown' {
  if (
    status === 'running' &&
    (health === 'healthy' || health === 'none')
  )
    return 'ok'
  if (status === 'running' && health === 'unhealthy')
    return 'error'
  if (status === 'exited') return 'error'
  if (status === 'running') return 'warn'
  return 'unknown'
}

function fmtUptime(s: number | null): string {
  if (!s) return '–'
  const days = Math.floor(s / 86400)
  const hours = Math.floor((s % 86400) / 3600)
  if (days > 0) return `${days}d ${hours}h`
  const mins = Math.floor((s % 3600) / 60)
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

const columns: ColumnDef<ContainerRow>[] = [
  {
    header: 'Name',
    accessorKey: 'name',
    cell: (info) => (
      <span className="admin-mono">
        {info.getValue<string>()}
      </span>
    ),
  },
  {
    header: 'Status',
    cell: (info) => (
      <StatusPill
        kind={statusKind(
          info.row.original.status,
          info.row.original.health,
        )}
      >
        {info.row.original.status}
      </StatusPill>
    ),
  },
  {
    header: 'Health',
    accessorKey: 'health',
  },
  {
    header: 'Uptime',
    cell: (info) =>
      fmtUptime(
        info.row.original.uptime_seconds,
      ),
  },
  {
    header: 'Restarts',
    accessorKey: 'restart_count',
  },
  {
    header: 'CPU %',
    cell: (info) =>
      info.row.original.cpu_pct === null
        ? '–'
        : `${info.row.original.cpu_pct.toFixed(
            1,
          )}%`,
  },
  {
    header: 'Memory',
    cell: (info) =>
      info.row.original.mem_mb === null
        ? '–'
        : `${info.row.original.mem_mb.toFixed(1)} MB`,
  },
]

export function ContainersRoute() {
  const { t } = useTranslation()
  const { data, isLoading, isFetching, error, refetch } =
    useQuery({
      queryKey: ['admin', 'containers', 'detail'],
      queryFn: () => adminApi.containers(),
      refetchInterval: 30_000,
      refetchIntervalInBackground: false,
    })

  const total = data?.total || 0

  return (
    <ListPageTemplate
      title={t('admin.containers.title')}
      subtitle={t(
        'admin.dashboard.containers.tracked',
        { count: total },
      )}
      actions={
        <MotionPress
          variant="ghost"
          haptic="selection"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <Icon name="refresh" size={14} />
          <span style={{ marginLeft: 6 }}>
            {t('admin.logs.refresh')}
          </span>
        </MotionPress>
      }
    >
      <DataTable
        columns={columns}
        rows={(data?.containers || []) as ContainerRow[]}
        isLoading={isLoading}
        error={error ? (error as Error).message : null}
        onRetry={() => refetch()}
        emptyHint="—"
      />
    </ListPageTemplate>
  )
}
