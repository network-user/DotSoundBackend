import { useState } from 'react'
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { adminApi } from '../lib/adminApi'
import { useStepUp } from '../components/auth/StepUpDialog'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { DataTable } from '../components/widgets/DataTable'
import { BulkPageSelector } from '../components/widgets/BulkPageSelector'
import { ListPageTemplate } from '../components/layout/ListPageTemplate'

const PAGE_SIZE = 50
const DEFAULT_MIN_TRACKS = 10

interface StationGapRow {
  id: number
  name: string
  soundcloud_user_id: number | null
  station_track_count: number | null
  station_synced_at: string | null
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString()
}

function StationCountCell({
  count,
}: {
  count: number | null
}) {
  if (count === null) {
    return (
      <span style={{ color: 'var(--color-error, #c0392b)', fontWeight: 600 }}>
        нет станции
      </span>
    )
  }
  return (
    <span
      style={{
        color:
          count === 0
            ? 'var(--color-error, #c0392b)'
            : 'var(--color-warn, #e67e22)',
        fontWeight: 600,
      }}
    >
      {count}
    </span>
  )
}

export function StationGapRoute() {
  const { showAlert } = useAdminPrompt()
  const stepUp = useStepUp()
  const qc = useQueryClient()

  const [minTracks, setMinTracks] = useState(DEFAULT_MIN_TRACKS)
  const [minTracksInput, setMinTracksInput] = useState(
    String(DEFAULT_MIN_TRACKS),
  )
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [resyncResult, setResyncResult] = useState<{
    queued: number
    errors: Array<{ artist_id: number; detail: string }>
  } | null>(null)

  const list = useQuery({
    queryKey: ['admin', 'station-gap', minTracks, page],
    queryFn: () =>
      adminApi.getStationGapArtists({
        min_tracks: minTracks,
        page,
        size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })

  const resyncMutation = useMutation({
    mutationFn: (ids: number[]) => adminApi.bulkResyncStations(ids, false),
    onSuccess: (res) => {
      setResyncResult({ queued: res.queued, errors: res.errors })
      setSelectedIds(new Set())
      qc.invalidateQueries({ queryKey: ['admin', 'station-gap'] })
    },
    onError: (err: Error) => {
      showAlert(err.message)
    },
  })

  const rows: StationGapRow[] = list.data?.items ?? []
  const total = list.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selectedIds.has(r.id))

  function applyMinTracks() {
    const v = parseInt(minTracksInput, 10)
    if (!Number.isFinite(v) || v < 0) return
    setMinTracks(v)
    setPage(1)
    setSelectedIds(new Set())
  }

  function toggleSelectAll(checked: boolean) {
    const ids = rows.map((r) => r.id)
    if (checked) {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        ids.forEach((id) => next.add(id))
        return next
      })
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        ids.forEach((id) => next.delete(id))
        return next
      })
    }
  }

  function toggleOne(id: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  async function handleResync() {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    const ok = await stepUp.request('catalog.sync.run')
    if (!ok) return
    resyncMutation.mutate(ids)
  }

  async function fetchPageIds(targetPage: number): Promise<number[]> {
    const res = await adminApi.getStationGapArtists({
      min_tracks: minTracks,
      page: targetPage,
      size: PAGE_SIZE,
    })
    return res.items.map((r) => r.id)
  }

  const columns: ColumnDef<StationGapRow>[] = [
    {
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          checked={allOnPageSelected}
          onChange={(e) => toggleSelectAll(e.target.checked)}
          aria-label="Выбрать всех на странице"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedIds.has(row.original.id)}
          onChange={(e) => toggleOne(row.original.id, e.target.checked)}
          aria-label={`Выбрать ${row.original.name}`}
        />
      ),
      size: 40,
    },
    {
      accessorKey: 'id',
      header: 'ID',
      size: 60,
    },
    {
      accessorKey: 'name',
      header: 'Артист',
      cell: ({ row }) => (
        <span style={{ fontWeight: 500 }}>{row.original.name}</span>
      ),
    },
    {
      accessorKey: 'soundcloud_user_id',
      header: 'SC user',
      cell: ({ row }) => row.original.soundcloud_user_id ?? '—',
      size: 100,
    },
    {
      accessorKey: 'station_track_count',
      header: 'Треков в станции',
      cell: ({ row }) => (
        <StationCountCell count={row.original.station_track_count} />
      ),
      size: 130,
    },
    {
      accessorKey: 'station_synced_at',
      header: 'Синхр.',
      cell: ({ row }) => fmtDate(row.original.station_synced_at),
      size: 100,
    },
  ]

  const selectedCount = selectedIds.size
  const isBusy = resyncMutation.isPending || list.isFetching

  return (
    <ListPageTemplate
      title="Пробелы станций"
      subtitle={`Артисты без станционного плейлиста или с < ${minTracks} треков`}
      actions={
        <MotionPress
          type="button"
          variant="primary"
          disabled={selectedCount === 0 || isBusy}
          onClick={handleResync}
        >
          {resyncMutation.isPending
            ? 'Ставим в очередь…'
            : `Resync станций (${selectedCount})`}
        </MotionPress>
      }
      filters={
        <div
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <label
            htmlFor="min-tracks-input"
            style={{ fontSize: '13px', whiteSpace: 'nowrap' }}
          >
            Порог треков:
          </label>
          <input
            id="min-tracks-input"
            type="number"
            min={0}
            max={200}
            value={minTracksInput}
            onChange={(e) => setMinTracksInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') applyMinTracks()
            }}
            style={{ width: '70px' }}
          />
          <MotionPress
            type="button"
            variant="ghost"
            onClick={applyMinTracks}
            disabled={isBusy}
          >
            Применить
          </MotionPress>
        </div>
      }
      toolbarHint={
        <BulkPageSelector
          currentPage={page}
          totalPages={totalPages}
          totalItems={total}
          selectedCount={selectedCount}
          disabled={isBusy}
          fetchPageIds={fetchPageIds}
          onAddIds={(ids) =>
            setSelectedIds((prev) => {
              const next = new Set(prev)
              ids.forEach((id) => next.add(id))
              return next
            })
          }
          onClear={() => setSelectedIds(new Set())}
        />
      }
      pagination={
        totalPages > 1 ? (
          <div
            style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MotionPress
              type="button"
              variant="ghost"
              disabled={page <= 1 || isBusy}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Назад
            </MotionPress>
            <span style={{ fontSize: '13px' }}>
              {page} / {totalPages} ({total} арт.)
            </span>
            <MotionPress
              type="button"
              variant="ghost"
              disabled={page >= totalPages || isBusy}
              onClick={() => setPage((p) => p + 1)}
            >
              Вперёд →
            </MotionPress>
          </div>
        ) : null
      }
    >
      {resyncResult && (
        <div
          style={{
            marginBottom: '12px',
            padding: '10px 14px',
            background: 'var(--color-surface-raised, #1e1e1e)',
            borderRadius: '6px',
            fontSize: '13px',
          }}
        >
          <strong>Результат:</strong> поставлено в очередь{' '}
          {resyncResult.queued}
          {resyncResult.errors.length > 0 && (
            <span style={{ color: 'var(--color-error, #c0392b)' }}>
              {' '}
              | ошибок: {resyncResult.errors.length}
            </span>
          )}
          <button
            type="button"
            onClick={() => setResyncResult(null)}
            style={{
              marginLeft: '12px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '12px',
              opacity: 0.6,
            }}
          >
            ✕
          </button>
        </div>
      )}

      <DataTable
        columns={columns}
        data={rows}
        isLoading={list.isLoading}
        emptyMessage={
          list.isError
            ? 'Ошибка загрузки'
            : `Нет артистов с проблемами станций (порог ${minTracks})`
        }
      />
    </ListPageTemplate>
  )
}
