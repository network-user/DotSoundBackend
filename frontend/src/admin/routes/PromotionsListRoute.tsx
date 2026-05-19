import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { getAdminPanelRoute } from '@/lib/adminPath'
import { adminApi } from '../lib/adminApi'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

type EntityType = 'artist' | 'track' | 'playlist' | 'album'
type Surface = 'hero' | 'section' | 'in_feed' | 'search_pin'
type Availability = 'available' | 'hidden' | 'missing'

interface PromotionRow {
  id: number
  entity_type: EntityType
  entity_id: number
  entity_label: string | null
  surfaces: Surface[]
  priority: number
  starts_at: string | null
  ends_at: string | null
  is_active: boolean
  availability: Availability
  impressions_total: number
  clicks_total: number
  created_at: string
  updated_at: string
}

const AVAILABILITY_KIND: Record<
  Availability,
  'ok' | 'warn' | 'error'
> = {
  available: 'ok',
  hidden: 'warn',
  missing: 'error',
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

export function PromotionsListRoute() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [entityType, setEntityType] = useState<EntityType | ''>('')
  const [activeFilter, setActiveFilter] = useState<
    'all' | 'active' | 'inactive'
  >('all')

  const { data, isFetching } = useQuery({
    queryKey: ['admin', 'promotions', page, entityType, activeFilter],
    queryFn: () =>
      adminApi.listAdminPromotions({
        page,
        size: 25,
        entity_type: entityType || undefined,
        is_active:
          activeFilter === 'all'
            ? undefined
            : activeFilter === 'active',
      }),
    placeholderData: keepPreviousData,
  })

  const toggleActive = useMutation({
    mutationFn: ({
      id,
      is_active,
    }: {
      id: number
      is_active: boolean
    }) =>
      adminApi.patchAdminPromotion(id, { is_active }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'promotions'] })
    },
  })

  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / 25))
  const rows = (data?.items ?? []) as PromotionRow[]

  const entityLabel = (et: EntityType): string =>
    t(`admin.promotions.entity${et.charAt(0).toUpperCase()}${et.slice(1)}`)

  const surfaceLabel = (s: Surface): string => {
    const map: Record<Surface, string> = {
      hero: t('admin.promotions.surfaceHero'),
      section: t('admin.promotions.surfaceSection'),
      in_feed: t('admin.promotions.surfaceInFeed'),
      search_pin: t('admin.promotions.surfaceSearchPin'),
    }
    return map[s]
  }

  const availabilityLabel = (a: Availability): string =>
    t(
      `admin.promotions.availability${a.charAt(0).toUpperCase()}${a.slice(1)}`,
    )

  const columns: ColumnDef<PromotionRow>[] = [
    {
      accessorKey: 'id',
      header: t('admin.promotions.colId'),
      cell: ({ row }) => row.original.id,
    },
    {
      id: 'entity',
      header: t('admin.promotions.colEntity'),
      cell: ({ row }) => (
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span>
            {entityLabel(row.original.entity_type)} #
            {row.original.entity_id}
          </span>
          {row.original.entity_label && (
            <span
              style={{
                fontSize: 12,
                color: 'var(--admin-text-muted)',
              }}
            >
              {row.original.entity_label}
            </span>
          )}
        </span>
      ),
    },
    {
      id: 'surfaces',
      header: t('admin.promotions.colSurfaces'),
      cell: ({ row }) => (
        <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {row.original.surfaces.map((s) => (
            <StatusPill key={s} kind="unknown">
              {surfaceLabel(s)}
            </StatusPill>
          ))}
        </span>
      ),
    },
    {
      accessorKey: 'priority',
      header: t('admin.promotions.colPriority'),
      cell: ({ row }) => row.original.priority,
    },
    {
      id: 'window',
      header: t('admin.promotions.colWindow'),
      cell: ({ row }) => (
        <span style={{ fontSize: 12 }}>
          {formatDate(row.original.starts_at)}
          <br />
          {formatDate(row.original.ends_at)}
        </span>
      ),
    },
    {
      id: 'status',
      header: t('admin.promotions.colStatus'),
      cell: ({ row }) => (
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <StatusPill kind={AVAILABILITY_KIND[row.original.availability]}>
            {availabilityLabel(row.original.availability)}
          </StatusPill>
          <StatusPill kind={row.original.is_active ? 'ok' : 'warn'}>
            {row.original.is_active
              ? t('admin.promotions.statusOn')
              : t('admin.promotions.statusOff')}
          </StatusPill>
        </span>
      ),
    },
    {
      id: 'metrics',
      header: t('admin.promotions.colMetrics'),
      cell: ({ row }) => (
        <span style={{ fontSize: 12 }}>
          {t('admin.promotions.metricImpressionsShort', {
            count: row.original.impressions_total,
          })}
          <br />
          {t('admin.promotions.metricClicksShort', {
            count: row.original.clicks_total,
          })}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <span style={{ display: 'flex', gap: 6 }}>
          <MotionPress
            variant="ghost"
            onClick={() =>
              toggleActive.mutate({
                id: row.original.id,
                is_active: !row.original.is_active,
              })
            }
          >
            {row.original.is_active
              ? t('admin.promotions.actionDisable')
              : t('admin.promotions.actionEnable')}
          </MotionPress>
          <MotionPress
            variant="ghost"
            onClick={() =>
              navigate(
                getAdminPanelRoute(`/promotions/${row.original.id}`),
              )
            }
          >
            {t('admin.promotions.actionOpen')}
          </MotionPress>
        </span>
      ),
    },
  ]

  return (
    <section className="admin-card">
      <h1>{t('admin.promotions.title')}</h1>
      <p className="admin-card__sub">
        {t('admin.promotions.listHint')}
      </p>
      <div
        className="admin-toolbar"
        style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}
      >
        <select
          className="admin-input"
          value={entityType}
          onChange={(e) => {
            setEntityType(e.target.value as EntityType | '')
            setPage(1)
          }}
        >
          <option value="">
            {t('admin.promotions.filterEntityAny')}
          </option>
          <option value="artist">
            {t('admin.promotions.entityArtist')}
          </option>
          <option value="track">
            {t('admin.promotions.entityTrack')}
          </option>
          <option value="playlist">
            {t('admin.promotions.entityPlaylist')}
          </option>
          <option value="album">
            {t('admin.promotions.entityAlbum')}
          </option>
        </select>
        <select
          className="admin-input"
          value={activeFilter}
          onChange={(e) => {
            setActiveFilter(
              e.target.value as 'all' | 'active' | 'inactive',
            )
            setPage(1)
          }}
        >
          <option value="all">
            {t('admin.promotions.filterStatusAny')}
          </option>
          <option value="active">
            {t('admin.promotions.filterStatusActive')}
          </option>
          <option value="inactive">
            {t('admin.promotions.filterStatusInactive')}
          </option>
        </select>
        <MotionPress
          variant="primary"
          onClick={() =>
            navigate(getAdminPanelRoute('/promotions/new'))
          }
        >
          {t('admin.promotions.create')}
        </MotionPress>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        emptyHint={t('admin.promotions.empty')}
      />
      <div className="admin-pagination">
        <MotionPress
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          {t('admin.common.prev', 'Назад')}
        </MotionPress>
        <span>
          {t('admin.promotions.paginationTotal', {
            page,
            totalPages,
            total,
          })}
        </span>
        <MotionPress
          variant="ghost"
          disabled={page >= totalPages || isFetching}
          onClick={() =>
            setPage((p) => Math.min(totalPages, p + 1))
          }
        >
          {t('admin.common.next', 'Вперёд')}
        </MotionPress>
      </div>
    </section>
  )
}
