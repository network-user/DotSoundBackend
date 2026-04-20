import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Press } from '@/components/ui/Press'
import { api } from '@/lib/api'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

interface ArtistRow {
  id: number
  name: string
  country: string | null
  enrichment_status: string | null
  enrichment_confidence: number | null
  cover_url: string | null
  updated_at: string | null
  created_at: string | null
}

interface ArtistListResponse {
  items: ArtistRow[]
  total: number
}

async function fetchArtists(
  q: string,
  page: number,
  size: number,
): Promise<ArtistListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    size: String(size),
  })
  if (q) params.set('q', q)
  const url = `/api/v1/artists?${params.toString()}`
  const token = api.getToken()
  const res = await fetch(url, {
    headers: token
      ? { Authorization: `Bearer ${token}` }
      : undefined,
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json()
}

async function enrichArtist(
  artistId: number,
): Promise<unknown> {
  const token = api.getToken()
  const res = await fetch(
    `/api/v1/artists/${artistId}/enrich`,
    {
      method: 'POST',
      headers: token
        ? { Authorization: `Bearer ${token}` }
        : undefined,
    },
  )
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json()
}

async function deleteArtist(artistId: number): Promise<void> {
  const token = api.getToken()
  const res = await fetch(`/api/v1/artists/${artistId}`, {
    method: 'DELETE',
    headers: token
      ? { Authorization: `Bearer ${token}` }
      : undefined,
  })
  if (!res.ok && res.status !== 204) {
    throw new Error(`HTTP ${res.status}`)
  }
}

function fmtArtistUpdated(row: ArtistRow): string {
  const iso = row.updated_at || row.created_at
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString()
}

export function ArtistsRoute() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [busyId, setBusyId] = useState<
    number | null
  >(null)

  const list = useQuery({
    queryKey: ['admin', 'artists', q, page],
    queryFn: () => fetchArtists(q, page, 25),
    placeholderData: keepPreviousData,
  })

  const enrichMutation = useMutation({
    mutationFn: (id: number) =>
      enrichArtist(id),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'artists'],
      })
      setBusyId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteArtist(id),
    onSettled: () => {
      qc.invalidateQueries({
        queryKey: ['admin', 'artists'],
      })
      setBusyId(null)
    },
  })

  function handleEnrich(id: number) {
    setBusyId(id)
    enrichMutation.mutate(id)
  }

  function handleDelete(id: number, name: string) {
    if (
      !window.confirm(
        `Удалить артиста «${name}» (id=${id})? Связи track_artist будут удалены.`,
      )
    )
      return
    setBusyId(id)
    deleteMutation.mutate(id)
  }

  function handleOpenArtist(id: number) {
    window.open(`/mini_app/artist/${id}`, '_blank')
  }

  const columns: ColumnDef<ArtistRow>[] = [
    {
      header: 'ID',
      accessorKey: 'id',
      cell: (info) => (
        <span className="admin-mono">
          {info.getValue<number>()}
        </span>
      ),
    },
    {
      header: 'Name',
      cell: (info) => (
        <button
          type="button"
          className="admin-link"
          onClick={() =>
            handleOpenArtist(info.row.original.id)
          }
        >
          {info.row.original.name}
        </button>
      ),
    },
    {
      header: 'Country',
      accessorKey: 'country',
    },
    {
      header: 'Enrichment',
      cell: (info) => {
        const status =
          info.row.original.enrichment_status
        if (!status)
          return (
            <StatusPill kind="unknown">
              {t('admin.artists.noEnrichment')}
            </StatusPill>
          )
        if (status === 'done')
          return (
            <StatusPill kind="ok">
              {status}
            </StatusPill>
          )
        if (status === 'error')
          return (
            <StatusPill kind="error">
              {status}
            </StatusPill>
          )
        return (
          <StatusPill kind="warn">
            {status}
          </StatusPill>
        )
      },
    },
    {
      header: 'Confidence',
      cell: (info) => {
        const c =
          info.row.original.enrichment_confidence
        if (c === null) return '–'
        return `${(c * 100).toFixed(0)}%`
      },
    },
    {
      header: 'Updated',
      cell: (info) => fmtArtistUpdated(info.row.original),
    },
    {
      header: '',
      id: 'actions',
      cell: (info) => {
        const { id, name } = info.row.original
        const busy = busyId === id
        return (
          <div
            style={{
              display: 'flex',
              gap: 6,
              flexWrap: 'wrap',
            }}
          >
            <Press
              variant="ghost"
              disabled={busy}
              onClick={() => handleEnrich(id)}
            >
              {busy && enrichMutation.isPending
                ? t('admin.artists.enriching')
                : t('admin.artists.enrich')}
            </Press>
            <Press
              variant="ghost"
              disabled={busy}
              onClick={() =>
                handleDelete(id, name)
              }
            >
              Удалить
            </Press>
          </div>
        )
      },
    },
  ]

  const total = list.data?.total ?? 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 25),
  )

  return (
    <div>
      <h1>{t('admin.artists.title')}</h1>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t(
            'admin.artists.searchPlaceholder',
          )}
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setPage(1)
          }}
        />
      </div>
      {list.error && (
        <div className="admin-error">
          {(list.error as Error).message}
        </div>
      )}
      <DataTable
        columns={columns}
        rows={
          (list.data?.items as ArtistRow[]) || []
        }
        emptyHint={t('admin.artists.empty')}
      />
      <div className="admin-pagination">
        <Press
          variant="ghost"
          disabled={page <= 1}
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
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          {t('admin.common.next')}
        </Press>
      </div>
    </div>
  )
}
