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

const ENTITY_LABELS: Record<EntityType, string> = {
  artist: 'Артист',
  track: 'Трек',
  playlist: 'Плейлист',
  album: 'Альбом',
}

const SURFACE_LABELS: Record<Surface, string> = {
  hero: 'Hero',
  section: 'Секция',
  in_feed: 'В ленте',
  search_pin: 'Поиск',
}

const AVAILABILITY_PILL: Record<
  Availability,
  { kind: 'ok' | 'warn' | 'error'; label: string }
> = {
  available: { kind: 'ok', label: 'Доступно' },
  hidden: { kind: 'warn', label: 'Скрыто' },
  missing: { kind: 'error', label: 'Удалено' },
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

  const columns: ColumnDef<PromotionRow>[] = [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: ({ row }) => row.original.id,
    },
    {
      id: 'entity',
      header: 'Сущность',
      cell: ({ row }) => (
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span>
            {ENTITY_LABELS[row.original.entity_type]} #
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
      header: 'Поверхности',
      cell: ({ row }) => (
        <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {row.original.surfaces.map((s) => (
            <StatusPill key={s} kind="unknown">
              {SURFACE_LABELS[s]}
            </StatusPill>
          ))}
        </span>
      ),
    },
    {
      accessorKey: 'priority',
      header: 'Приоритет',
      cell: ({ row }) => row.original.priority,
    },
    {
      id: 'window',
      header: 'Окно',
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
      header: 'Статус',
      cell: ({ row }) => {
        const pill = AVAILABILITY_PILL[row.original.availability]
        return (
          <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <StatusPill kind={pill.kind}>{pill.label}</StatusPill>
            <StatusPill kind={row.original.is_active ? 'ok' : 'warn'}>
              {row.original.is_active ? 'Включено' : 'Выключено'}
            </StatusPill>
          </span>
        )
      },
    },
    {
      id: 'metrics',
      header: 'Метрики',
      cell: ({ row }) => (
        <span style={{ fontSize: 12 }}>
          Показы: {row.original.impressions_total}
          <br />
          Клики: {row.original.clicks_total}
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
            {row.original.is_active ? 'Выключить' : 'Включить'}
          </MotionPress>
          <MotionPress
            variant="ghost"
            onClick={() =>
              navigate(
                getAdminPanelRoute(`/promotions/${row.original.id}`),
              )
            }
          >
            Открыть
          </MotionPress>
        </span>
      ),
    },
  ]

  return (
    <section className="admin-card">
      <h1>Продвижение</h1>
      <p className="admin-card__sub">
        Управление продвигаемыми артистами, треками, плейлистами и
        альбомами. Окно действия, приоритет и поверхности задаются на
        форме записи.
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
          <option value="">Все сущности</option>
          <option value="artist">Артисты</option>
          <option value="track">Треки</option>
          <option value="playlist">Плейлисты</option>
          <option value="album">Альбомы</option>
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
          <option value="all">Все статусы</option>
          <option value="active">Включённые</option>
          <option value="inactive">Выключенные</option>
        </select>
        <MotionPress
          variant="primary"
          onClick={() =>
            navigate(getAdminPanelRoute('/promotions/new'))
          }
        >
          Создать промо
        </MotionPress>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        emptyHint="Нет записей"
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
          {page} / {totalPages} · всего {total}
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
