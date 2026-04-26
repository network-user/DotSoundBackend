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
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { DataTable } from '../components/widgets/DataTable'
import { StatusPill } from '../components/widgets/StatusPill'

interface TrackRow {
  id: number
  title: string
  artist: string | null
  source: string | null
  is_active: boolean
  uploaded_by_id: number | null
  created_at: string
}

export function TracksRoute() {
  const { t } = useTranslation()
  const { showConfirm, showAlert } = useAdminPrompt()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [playingId, setPlayingId] = useState<number | null>(
    null,
  )
  const [busyId, setBusyId] = useState<number | null>(null)
  const { data, isFetching } = useQuery({
    queryKey: ['admin', 'tracks', page, search],
    queryFn: () =>
      adminApi.listTracks({
        page,
        size: 25,
        search: search || undefined,
      }),
    placeholderData: keepPreviousData,
  })
  const total = data?.total || 0
  const totalPages = Math.max(
    1,
    Math.ceil(total / 25),
  )

  const refresh = () =>
    qc.invalidateQueries({
      queryKey: ['admin', 'tracks'],
    })

  const handleDelete = async (id: number, title: string) => {
    const ok = await showConfirm(
      t('admin.tracks.confirmDelete', { id, title }),
      { danger: true },
    )
    if (!ok) return
    setBusyId(id)
    try {
      await adminApi.deleteTrack(id)
      refresh()
    } catch (err) {
      await showAlert(
        t('admin.tracks.deleteFailed', {
          message: (err as Error).message,
        }),
      )
    } finally {
      setBusyId(null)
    }
  }

  const handleToggleVisibility = async (
    id: number,
    isActive: boolean,
  ) => {
    setBusyId(id)
    try {
      await adminApi.setTrackVisibility(id, !isActive)
      refresh()
    } catch {}
    finally {
      setBusyId(null)
    }
  }

  const handleOpen = (id: number) => {
    window.open(`/mini_app/track/${id}`, '_blank')
  }

  const handleTogglePlay = (id: number) => {
    setPlayingId((prev) => (prev === id ? null : id))
  }

  const columns: ColumnDef<TrackRow>[] = [
    {
      header: t('admin.tracks.colId'),
      accessorKey: 'id',
      cell: (i) => (
        <span className="admin-mono">
          {i.getValue<number>()}
        </span>
      ),
    },
    {
      header: t('admin.tracks.colTitle'),
      accessorKey: 'title',
      cell: (i) => (
        <button
          type="button"
          className="admin-link"
          onClick={() => handleOpen(i.row.original.id)}
        >
          {i.row.original.title}
        </button>
      ),
    },
    {
      header: t('admin.tracks.colArtist'),
      accessorKey: 'artist',
    },
    {
      header: t('admin.tracks.colSource'),
      accessorKey: 'source',
    },
    {
      header: t('admin.tracks.colStatus'),
      accessorKey: 'is_active',
      cell: (i) =>
        i.row.original.is_active ? (
          <StatusPill kind="ok">
            {t('admin.tracks.visible')}
          </StatusPill>
        ) : (
          <StatusPill kind="warn">
            {t('admin.tracks.hidden')}
          </StatusPill>
        ),
    },
    {
      header: t('admin.tracks.colUploaded'),
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
        const { id, title, is_active } = i.row.original
        const busy = busyId === id
        const isPlaying = playingId === id
        return (
          <div
            style={{
              display: 'flex',
              gap: 6,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <Press
              variant="ghost"
              onClick={() => handleTogglePlay(id)}
              disabled={busy}
            >
              {isPlaying
                ? t('admin.tracks.actionPause')
                : t('admin.tracks.actionPlay')}
            </Press>
            {isPlaying && (
              <audio
                src={`/api/v1/tracks/${id}/audio`}
                controls
                autoPlay
                style={{ height: 28, maxWidth: 180 }}
              />
            )}
            <Press
              variant="ghost"
              onClick={() =>
                handleToggleVisibility(id, is_active)
              }
              disabled={busy}
            >
              {is_active
                ? t('admin.tracks.actionHide')
                : t('admin.tracks.actionShow')}
            </Press>
            <Press
              variant="ghost"
              onClick={() => handleOpen(id)}
              disabled={busy}
            >
              {t('admin.tracks.actionOpen')}
            </Press>
            <Press
              variant="ghost"
              onClick={() => handleDelete(id, title)}
              disabled={busy}
            >
              {t('admin.tracks.actionDelete')}
            </Press>
          </div>
        )
      },
    },
  ]
  return (
    <div>
      <h1>{t('admin.tracks.title')}</h1>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t(
            'admin.tracks.searchPlaceholder',
          )}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
      </div>
      <DataTable
        columns={columns}
        rows={(data?.items || []) as unknown as TrackRow[]}
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
    </div>
  )
}
