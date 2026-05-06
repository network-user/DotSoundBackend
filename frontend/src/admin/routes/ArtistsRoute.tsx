import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import { adminApi } from '../lib/adminApi'
import { ArtistCatalogEditor } from '../components/ArtistCatalogEditor'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
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
  const { showConfirm, showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [busyId, setBusyId] = useState<
    number | null
  >(null)
  const [catalogFor, setCatalogFor] = useState<{
    id: number
    name: string
  } | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [batchPromptModal, setBatchPromptModal] = useState<string | null>(null)
  const [importModal, setImportModal] = useState(false)
  const [importText, setImportText] = useState('')
  const [importResult, setImportResult] = useState<{
    imported: number
    errors: string[]
  } | null>(null)

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

  async function handleDelete(
    id: number,
    name: string,
  ) {
    const ok = await showConfirm(
      t('admin.artists.confirmDelete', {
        id,
        name,
      }),
      { danger: true },
    )
    if (!ok) return
    setBusyId(id)
    deleteMutation.mutate(id)
  }

  function handleOpenArtist(id: number) {
    window.open(`/mini_app/artist/${id}`, '_blank')
  }

  const rows = (list.data?.items as ArtistRow[]) || []
  const allOnPageSelected =
    rows.length > 0 && rows.every((r) => selectedIds.has(r.id))

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(rows.map((r) => r.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  const toggleSelectOne = (id: number, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const handleBatchPrompt = async () => {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    try {
      const res = await adminApi.artistSupplementalBatchPrompt(ids)
      setBatchPromptModal(res.prompt)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const handleBatchImport = async () => {
    try {
      const res = await adminApi.artistSupplementalBatchImport(importText)
      setImportResult(res)
    } catch (err) {
      await showAlert((err as Error).message)
    }
  }

  const columns: ColumnDef<ArtistRow>[] = [
    {
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          checked={allOnPageSelected}
          onChange={(e) => toggleSelectAll(e.target.checked)}
          aria-label="Выбрать все"
        />
      ),
      cell: (i) => (
        <input
          type="checkbox"
          checked={selectedIds.has(i.row.original.id)}
          onChange={(e) => toggleSelectOne(i.row.original.id, e.target.checked)}
          aria-label={`Выбрать артиста ${i.row.original.id}`}
        />
      ),
      enableSorting: false,
    },
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
      accessorKey: 'enrichment_status',
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
      accessorKey: 'enrichment_confidence',
      cell: (info) => {
        const c =
          info.row.original.enrichment_confidence
        if (c === null) return '–'
        return `${(c * 100).toFixed(0)}%`
      },
    },
    {
      header: 'Updated',
      accessorKey: 'updated_at',
      cell: (info) => fmtArtistUpdated(info.row.original),
    },
    {
      header: '',
      id: 'actions',
      enableSorting: false,
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
            <MotionPress
              variant="ghost"
              disabled={busy}
              onClick={() => handleEnrich(id)}
            >
              {busy && enrichMutation.isPending
                ? t('admin.artists.enriching')
                : t('admin.artists.enrich')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              disabled={busy}
              onClick={() =>
                setCatalogFor({ id, name })
              }
            >
              {t('admin.artists.catalog.open')}
            </MotionPress>
            <MotionPress
              variant="ghost"
              disabled={busy}
              onClick={() =>
                handleDelete(id, name)
              }
            >
              {t('admin.artists.actionDelete')}
            </MotionPress>
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
      {catalogFor && (
        <ArtistCatalogEditor
          artistId={catalogFor.id}
          artistName={catalogFor.name}
          open
          onClose={() => setCatalogFor(null)}
        />
      )}
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
        <MotionPress
          variant="ghost"
          disabled={selectedIds.size === 0}
          onClick={handleBatchPrompt}
        >
          Batch Prompt ({selectedIds.size})
        </MotionPress>
        <MotionPress
          variant="ghost"
          onClick={() => {
            setImportText('')
            setImportResult(null)
            setImportModal(true)
          }}
        >
          Импорт ответа AI (Artists)
        </MotionPress>
      </div>
      {list.error && (
        <div className="admin-error">
          {(list.error as Error).message}
        </div>
      )}
      <DataTable
        columns={columns}
        rows={rows}
        emptyHint={t('admin.artists.empty')}
        enableSorting
      />
      <div className="admin-pagination">
        <MotionPress
          variant="ghost"
          disabled={page <= 1}
          onClick={() =>
            setPage((p) => Math.max(1, p - 1))
          }
        >
          {t('admin.common.prev')}
        </MotionPress>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <MotionPress
          variant="ghost"
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          {t('admin.common.next')}
        </MotionPress>
      </div>

      {batchPromptModal && (
        <div
          className="admin-modal-overlay"
          onClick={() => setBatchPromptModal(null)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 760 }}
          >
            <h3>Artist Batch Prompt</h3>
            <textarea
              readOnly
              value={batchPromptModal}
              rows={22}
              style={{
                width: '100%',
                fontFamily: 'monospace',
                fontSize: 12,
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <MotionPress
                variant="primary"
                onClick={() => navigator.clipboard.writeText(batchPromptModal)}
              >
                Копировать
              </MotionPress>
              <MotionPress variant="ghost" onClick={() => setBatchPromptModal(null)}>
                Закрыть
              </MotionPress>
            </div>
          </div>
        </div>
      )}

      {importModal && (
        <div
          className="admin-modal-overlay"
          onClick={() => setImportModal(false)}
        >
          <div
            className="admin-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 640 }}
          >
            <h3>Импорт ответа AI (Artists)</h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
              Вставьте JSON-ответ в формате artists[].id + artists[].content.
            </p>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={14}
              placeholder='{"artists":[{"id":1,"content":"..."}]}'
              style={{
                width: '100%',
                fontFamily: 'monospace',
                fontSize: 12,
                resize: 'vertical',
              }}
            />
            {importResult && (
              <div style={{ marginTop: 8 }}>
                <p style={{ fontWeight: 600 }}>
                  Импортировано: {importResult.imported}
                </p>
                {importResult.errors.length > 0 && (
                  <ul
                    style={{
                      fontSize: 12,
                      color: 'var(--color-danger, #c00)',
                      paddingLeft: 16,
                      margin: '4px 0 0',
                    }}
                  >
                    {importResult.errors.map((e, idx) => (
                      <li key={idx}>{e}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <MotionPress
                variant="primary"
                onClick={handleBatchImport}
                disabled={!importText.trim()}
              >
                Импортировать
              </MotionPress>
              <MotionPress variant="ghost" onClick={() => setImportModal(false)}>
                Закрыть
              </MotionPress>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
