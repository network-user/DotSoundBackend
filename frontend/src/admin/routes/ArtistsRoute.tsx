import { useState } from 'react'
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
  updated_at: string
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

export function ArtistsRoute() {
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

  function handleEnrich(id: number) {
    setBusyId(id)
    enrichMutation.mutate(id)
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
      accessorKey: 'name',
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
              none
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
      cell: (info) =>
        new Date(
          info.row.original.updated_at,
        ).toLocaleDateString(),
    },
    {
      header: '',
      id: 'actions',
      cell: (info) => (
        <Press
          variant="ghost"
          disabled={
            busyId === info.row.original.id
          }
          onClick={() =>
            handleEnrich(info.row.original.id)
          }
        >
          {busyId === info.row.original.id
            ? 'Enriching…'
            : 'Enrich'}
        </Press>
      ),
    },
  ]

  const total = list.data?.total ?? 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 25),
  )

  return (
    <div>
      <h1>Artists</h1>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder="Search by name…"
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
        emptyHint="No artists yet"
      />
      <div className="admin-pagination">
        <Press
          variant="ghost"
          disabled={page <= 1}
          onClick={() =>
            setPage((p) => Math.max(1, p - 1))
          }
        >
          Prev
        </Press>
        <span>
          {page} / {totalPages} · {total} total
        </span>
        <Press
          variant="ghost"
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </Press>
      </div>
    </div>
  )
}
