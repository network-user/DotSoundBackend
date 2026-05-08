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

interface PlaylistRow {
  id: number
  name: string
  owner_id: number
  is_public: boolean
  playlist_type: string
  is_featured: boolean
  description: string | null
  source_url: string | null
  created_at: string
  track_count: number
}

type AdminTab = 'list' | 'import' | 'create'

const PLAYLIST_TYPE_LABELS: Record<string, string> = {
  user: 'Пользовательский',
  editorial: 'Редакционный',
  imported_sc: 'Из SoundCloud',
  imported_bc: 'Из Bandcamp',
  auto_weekly_top: 'Авто: топ недели',
  auto_genre_mix: 'Авто: жанровый',
  auto_daily_mix: 'Авто: дневной',
}

export function PlaylistsListRoute() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<AdminTab>('list')

  /* ── Import form state ─────────────────────────────────── */
  const [importUrl, setImportUrl] = useState('')
  const [importName, setImportName] = useState('')
  const [importFeatured, setImportFeatured] = useState(false)
  const [importPublic, setImportPublic] = useState(true)
  const [importError, setImportError] = useState<string | null>(null)

  /* ── Create editorial form state ───────────────────────── */
  const [createName, setCreateName] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [createFeatured, setCreateFeatured] = useState(false)
  const [createPublic, setCreatePublic] = useState(true)
  const [createError, setCreateError] = useState<string | null>(null)

  const { data, isFetching } = useQuery({
    queryKey: ['admin', 'playlists', page, search],
    queryFn: () =>
      adminApi.listAdminPlaylists({
        page,
        size: 25,
        search: search || undefined,
      }),
    placeholderData: keepPreviousData,
  })

  const importMutation = useMutation({
    mutationFn: () =>
      adminApi.importAdminPlaylist({
        source_url: importUrl.trim(),
        name: importName.trim() || undefined,
        make_featured: importFeatured,
        make_public: importPublic,
      }),
    onSuccess: () => {
      setImportUrl('')
      setImportName('')
      setImportFeatured(false)
      setImportError(null)
      setTab('list')
      void qc.invalidateQueries({ queryKey: ['admin', 'playlists'] })
    },
    onError: (err: Error) => {
      setImportError(err.message || 'Ошибка импорта')
    },
  })

  const createMutation = useMutation({
    mutationFn: () =>
      adminApi.createEditorialPlaylist({
        name: createName.trim(),
        description: createDesc.trim() || undefined,
        is_featured: createFeatured,
        is_public: createPublic,
      }),
    onSuccess: (res) => {
      setCreateName('')
      setCreateDesc('')
      setCreateFeatured(false)
      setCreateError(null)
      setTab('list')
      void qc.invalidateQueries({ queryKey: ['admin', 'playlists'] })
      if (res && typeof res === 'object' && 'id' in res) {
        navigate(
          getAdminPanelRoute(
            `/playlists/${(res as { id: number }).id}`,
          ),
        )
      }
    },
    onError: (err: Error) => {
      setCreateError(err.message || 'Ошибка создания')
    },
  })

  const setFeaturedMutation = useMutation({
    mutationFn: ({
      id,
      is_featured,
    }: {
      id: number
      is_featured: boolean
    }) => adminApi.patchAdminPlaylist(id, { is_featured }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'playlists'] })
    },
  })

  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / 25))
  const rows = (data?.items ?? []) as PlaylistRow[]

  const columns: ColumnDef<PlaylistRow>[] = [
    {
      accessorKey: 'id',
      header: t('admin.playlists.colId'),
      cell: ({ row }) => row.original.id,
    },
    {
      accessorKey: 'name',
      header: t('admin.playlists.colName'),
      cell: ({ row }) => (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {row.original.name}
          {row.original.is_featured && (
            <StatusPill kind="ok">Featured</StatusPill>
          )}
        </span>
      ),
    },
    {
      id: 'type',
      header: 'Тип',
      cell: ({ row }) =>
        PLAYLIST_TYPE_LABELS[row.original.playlist_type] ??
        row.original.playlist_type,
    },
    {
      accessorKey: 'owner_id',
      header: t('admin.playlists.colOwner'),
      cell: ({ row }) => row.original.owner_id,
    },
    {
      accessorKey: 'track_count',
      header: t('admin.playlists.colTracks'),
      cell: ({ row }) => row.original.track_count,
    },
    {
      id: 'pub',
      header: t('admin.playlists.colPublic'),
      cell: ({ row }) =>
        row.original.is_public ? (
          <StatusPill kind="ok">
            {t('admin.playlists.public')}
          </StatusPill>
        ) : (
          <StatusPill kind="warn">
            {t('admin.playlists.private')}
          </StatusPill>
        ),
    },
    {
      id: 'featured',
      header: 'Featured',
      cell: ({ row }) => (
        <MotionPress
          variant="ghost"
          onClick={() =>
            setFeaturedMutation.mutate({
              id: row.original.id,
              is_featured: !row.original.is_featured,
            })
          }
        >
          {row.original.is_featured ? '★ Убрать' : '☆ Сделать Featured'}
        </MotionPress>
      ),
    },
    {
      id: 'open',
      header: '',
      cell: ({ row }) => (
        <MotionPress
          variant="ghost"
          onClick={() =>
            navigate(
              getAdminPanelRoute(
                `/playlists/${row.original.id}`,
              ),
            )
          }
        >
          {t('admin.playlists.open')}
        </MotionPress>
      ),
    },
  ]

  return (
    <section className="admin-card">
      <h1>{t('admin.playlists.title')}</h1>
      <p className="admin-card__sub">
        {t('admin.playlists.listHint')}
      </p>
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder={t('admin.playlists.searchPlaceholder')}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        emptyHint={t('admin.playlists.empty')}
      />
      <div className="admin-pagination">
        <MotionPress
          variant="ghost"
          disabled={page <= 1 || isFetching}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          {t('admin.common.prev')}
        </MotionPress>
        <span>
          {page} / {totalPages} ·{' '}
          {t('admin.common.total', { count: total })}
        </span>
        <MotionPress
          variant="ghost"
          disabled={page >= totalPages || isFetching}
          onClick={() =>
            setPage((p) => Math.min(totalPages, p + 1))
          }
        >
          {t('admin.common.next')}
        </MotionPress>
      </div>

      {/* ── Tab: List ──────────────────────────────────────── */}
      {tab === 'list' && (
        <>
          <p className="admin-card__sub">
            {t('admin.playlists.listHint')}
          </p>
          <div className="admin-toolbar">
            <input
              type="search"
              placeholder={t('admin.playlists.searchPlaceholder')}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
          </div>
          <DataTable
            columns={columns}
            rows={rows}
            emptyHint={t('admin.playlists.empty')}
          />
          <div className="admin-pagination">
            <MotionPress
              variant="ghost"
              disabled={page <= 1 || isFetching}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              {t('admin.common.prev')}
            </MotionPress>
            <span>
              {page} / {totalPages} ·{' '}
              {t('admin.common.total', { count: total })}
            </span>
            <MotionPress
              variant="ghost"
              disabled={page >= totalPages || isFetching}
              onClick={() =>
                setPage((p) => Math.min(totalPages, p + 1))
              }
            >
              {t('admin.common.next')}
            </MotionPress>
          </div>
        </>
      )}

      {/* ── Tab: Import ────────────────────────────────────── */}
      {tab === 'import' && (
        <div style={{ maxWidth: 520 }}>
          <p
            style={{
              color: 'var(--admin-text-muted)',
              marginBottom: 16,
              fontSize: 13,
            }}
          >
            Вставьте URL плейлиста SoundCloud. Треки будут
            импортированы в систему автоматически.
          </p>
          <div className="admin-form-group">
            <label className="admin-label">URL плейлиста *</label>
            <input
              className="admin-input"
              type="url"
              placeholder="https://soundcloud.com/user/sets/playlist-name"
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
            />
          </div>
          <div className="admin-form-group">
            <label className="admin-label">
              Название (необязательно)
            </label>
            <input
              className="admin-input"
              placeholder="Будет взято из SoundCloud если не указано"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
            />
          </div>
          <div
            style={{
              display: 'flex',
              gap: 20,
              marginBottom: 16,
            }}
          >
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              <input
                type="checkbox"
                checked={importFeatured}
                onChange={(e) =>
                  setImportFeatured(e.target.checked)
                }
              />
              Показать как Featured
            </label>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              <input
                type="checkbox"
                checked={importPublic}
                onChange={(e) => setImportPublic(e.target.checked)}
              />
              Публичный
            </label>
          </div>
          {importError && (
            <p
              style={{
                color: 'var(--admin-error)',
                marginBottom: 12,
                fontSize: 13,
              }}
            >
              {importError}
            </p>
          )}
          <MotionPress
            variant="primary"
            disabled={
              !importUrl.trim() || importMutation.isPending
            }
            onClick={() => importMutation.mutate()}
          >
            {importMutation.isPending
              ? 'Импортируется...'
              : 'Импортировать'}
          </MotionPress>
          {importMutation.isPending && (
            <p
              style={{
                color: 'var(--admin-text-muted)',
                marginTop: 8,
                fontSize: 12,
              }}
            >
              Импорт может занять несколько минут в зависимости
              от размера плейлиста
            </p>
          )}
        </div>
      )}

      {/* ── Tab: Create Editorial ──────────────────────────── */}
      {tab === 'create' && (
        <div style={{ maxWidth: 520 }}>
          <p
            style={{
              color: 'var(--admin-text-muted)',
              marginBottom: 16,
              fontSize: 13,
            }}
          >
            Создайте курированный плейлист — вы сможете добавить
            треки на странице редактирования.
          </p>
          <div className="admin-form-group">
            <label className="admin-label">Название *</label>
            <input
              className="admin-input"
              placeholder="Название плейлиста"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
            />
          </div>
          <div className="admin-form-group">
            <label className="admin-label">Описание</label>
            <textarea
              className="admin-input"
              placeholder="Краткое описание плейлиста"
              rows={3}
              value={createDesc}
              onChange={(e) => setCreateDesc(e.target.value)}
              style={{ resize: 'vertical' }}
            />
          </div>
          <div
            style={{
              display: 'flex',
              gap: 20,
              marginBottom: 16,
            }}
          >
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              <input
                type="checkbox"
                checked={createFeatured}
                onChange={(e) =>
                  setCreateFeatured(e.target.checked)
                }
              />
              Показать как Featured
            </label>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              <input
                type="checkbox"
                checked={createPublic}
                onChange={(e) => setCreatePublic(e.target.checked)}
              />
              Публичный
            </label>
          </div>
          {createError && (
            <p
              style={{
                color: 'var(--admin-error)',
                marginBottom: 12,
                fontSize: 13,
              }}
            >
              {createError}
            </p>
          )}
          <MotionPress
            variant="primary"
            disabled={
              !createName.trim() || createMutation.isPending
            }
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? 'Создание...' : 'Создать'}
          </MotionPress>
        </div>
      )}
    </section>
  )
}
