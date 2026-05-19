import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { MotionPress } from '@/components/ui/MotionPress'
import { getAdminPanelRoute } from '@/lib/adminPath'
import { adminApi } from '../lib/adminApi'
import { useAdminPrompt } from '../components/layout/AdminPromptContext'
import { StatusPill } from '../components/widgets/StatusPill'

type EntityType = 'artist' | 'track' | 'playlist' | 'album'
type Surface = 'hero' | 'section' | 'in_feed' | 'search_pin'

const SURFACE_OPTIONS: Array<{ value: Surface; label: string }> = [
  { value: 'hero', label: 'Hero (баннер)' },
  { value: 'section', label: 'Секция (карусель)' },
  { value: 'in_feed', label: 'В ленте' },
  { value: 'search_pin', label: 'Поиск (закреп)' },
]

const ENTITY_OPTIONS: Array<{ value: EntityType; label: string }> = [
  { value: 'artist', label: 'Артист' },
  { value: 'track', label: 'Трек' },
  { value: 'playlist', label: 'Плейлист' },
  { value: 'album', label: 'Альбом' },
]

function toLocalInputValue(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const offset = d.getTimezoneOffset() * 60000
    return new Date(d.getTime() - offset)
      .toISOString()
      .slice(0, 16)
  } catch {
    return ''
  }
}

function fromLocalInputValue(local: string): string | null {
  if (!local) return null
  try {
    return new Date(local).toISOString()
  } catch {
    return null
  }
}

export function PromotionDetailRoute() {
  const navigate = useNavigate()
  const { promotionId: rawId } = useParams()
  const isNew = rawId === 'new'
  const promotionId = isNew ? null : Number.parseInt(rawId ?? '', 10)
  const { showAlert, showConfirm } = useAdminPrompt()
  const qc = useQueryClient()

  const [entityType, setEntityType] = useState<EntityType>('artist')
  const [entityId, setEntityId] = useState<string>('')
  const [surfaces, setSurfaces] = useState<Set<Surface>>(
    new Set(['hero']),
  )
  const [priority, setPriority] = useState<string>('0')
  const [startsAt, setStartsAt] = useState<string>('')
  const [endsAt, setEndsAt] = useState<string>('')
  const [isActive, setIsActive] = useState<boolean>(true)
  const [titleOverride, setTitleOverride] = useState<string>('')
  const [subtitleOverride, setSubtitleOverride] = useState<string>('')
  const [ctaOverride, setCtaOverride] = useState<string>('')
  const [coverOverride, setCoverOverride] = useState<string>('')

  const detailQuery = useQuery({
    queryKey: ['admin', 'promotion', promotionId],
    queryFn: () =>
      promotionId !== null
        ? adminApi.getAdminPromotion(promotionId)
        : null,
    enabled:
      !isNew && Number.isFinite(promotionId) && (promotionId ?? 0) > 0,
  })

  const statsQuery = useQuery({
    queryKey: ['admin', 'promotion-stats', promotionId],
    queryFn: () =>
      promotionId !== null
        ? adminApi.getAdminPromotionStats(promotionId, 30)
        : null,
    enabled:
      !isNew && Number.isFinite(promotionId) && (promotionId ?? 0) > 0,
  })

  useEffect(() => {
    const d = detailQuery.data
    if (!d) return
    setEntityType(d.entity_type)
    setEntityId(String(d.entity_id))
    setSurfaces(new Set(d.surfaces))
    setPriority(String(d.priority))
    setStartsAt(toLocalInputValue(d.starts_at))
    setEndsAt(toLocalInputValue(d.ends_at))
    setIsActive(d.is_active)
    setTitleOverride(d.title_override ?? '')
    setSubtitleOverride(d.subtitle_override ?? '')
    setCtaOverride(d.cta_label_override ?? '')
    setCoverOverride(d.cover_url_override ?? '')
  }, [detailQuery.data])

  const createMutation = useMutation({
    mutationFn: () =>
      adminApi.createAdminPromotion({
        entity_type: entityType,
        entity_id: Number.parseInt(entityId, 10),
        surfaces: Array.from(surfaces),
        priority: Number.parseInt(priority, 10) || 0,
        starts_at: fromLocalInputValue(startsAt),
        ends_at: fromLocalInputValue(endsAt),
        is_active: isActive,
        title_override: titleOverride || null,
        subtitle_override: subtitleOverride || null,
        cta_label_override: ctaOverride || null,
        cover_url_override: coverOverride || null,
      }),
    onSuccess: (res) => {
      void qc.invalidateQueries({ queryKey: ['admin', 'promotions'] })
      navigate(
        getAdminPanelRoute(`/promotions/${(res as { id: number }).id}`),
      )
    },
    onError: (err: Error) => {
      void showAlert(err.message || 'Не удалось создать запись', {
        title: 'Ошибка создания',
      })
    },
  })

  const patchMutation = useMutation({
    mutationFn: () =>
      adminApi.patchAdminPromotion(promotionId as number, {
        surfaces: Array.from(surfaces),
        priority: Number.parseInt(priority, 10) || 0,
        starts_at: fromLocalInputValue(startsAt),
        ends_at: fromLocalInputValue(endsAt),
        is_active: isActive,
        title_override: titleOverride || null,
        subtitle_override: subtitleOverride || null,
        cta_label_override: ctaOverride || null,
        cover_url_override: coverOverride || null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['admin', 'promotion', promotionId],
      })
      void qc.invalidateQueries({ queryKey: ['admin', 'promotions'] })
    },
    onError: (err: Error) => {
      void showAlert(err.message || 'Не удалось сохранить запись', {
        title: 'Ошибка сохранения',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () =>
      adminApi.deleteAdminPromotion(promotionId as number),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'promotions'] })
      navigate(getAdminPanelRoute('/promotions'))
    },
  })

  const toggleSurface = (surface: Surface) => {
    setSurfaces((prev) => {
      const next = new Set(prev)
      if (next.has(surface)) next.delete(surface)
      else next.add(surface)
      return next
    })
  }

  const isReady = useMemo(() => {
    const eid = Number.parseInt(entityId, 10)
    return (
      Number.isFinite(eid) &&
      eid > 0 &&
      surfaces.size > 0
    )
  }, [entityId, surfaces])

  return (
    <section className="admin-card" style={{ maxWidth: 720 }}>
      <h1>
        {isNew
          ? 'Новая запись продвижения'
          : `Запись #${promotionId}`}
      </h1>

      {!isNew && detailQuery.data && (
        <div
          style={{
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            marginBottom: 16,
          }}
        >
          <StatusPill
            kind={
              detailQuery.data.availability === 'available'
                ? 'ok'
                : detailQuery.data.availability === 'hidden'
                  ? 'warn'
                  : 'error'
            }
          >
            {detailQuery.data.availability === 'available'
              ? 'Сущность доступна'
              : detailQuery.data.availability === 'hidden'
                ? 'Сущность скрыта — в выдаче не появится'
                : 'Сущность удалена — в выдаче не появится'}
          </StatusPill>
        </div>
      )}

      <div className="admin-form-group">
        <label className="admin-label">Тип сущности *</label>
        <select
          className="admin-input"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value as EntityType)}
          disabled={!isNew}
        >
          {ENTITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="admin-form-group">
        <label className="admin-label">ID сущности *</label>
        <input
          className="admin-input"
          type="number"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          disabled={!isNew}
        />
        {!isNew && detailQuery.data?.entity_label && (
          <p
            style={{
              fontSize: 12,
              color: 'var(--admin-text-muted)',
              marginTop: 4,
            }}
          >
            {detailQuery.data.entity_label}
          </p>
        )}
      </div>

      <div className="admin-form-group">
        <label className="admin-label">Поверхности *</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {SURFACE_OPTIONS.map((o) => (
            <label
              key={o.value}
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
                checked={surfaces.has(o.value)}
                onChange={() => toggleSurface(o.value)}
              />
              {o.label}
            </label>
          ))}
        </div>
      </div>

      <div className="admin-form-group">
        <label className="admin-label">Приоритет</label>
        <input
          className="admin-input"
          type="number"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
        />
        <p
          style={{
            fontSize: 12,
            color: 'var(--admin-text-muted)',
            marginTop: 4,
          }}
        >
          Больше число — выше в выдаче. Допустимо: −1000…1000.
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
        }}
      >
        <div className="admin-form-group">
          <label className="admin-label">Старт</label>
          <input
            className="admin-input"
            type="datetime-local"
            value={startsAt}
            onChange={(e) => setStartsAt(e.target.value)}
          />
        </div>
        <div className="admin-form-group">
          <label className="admin-label">Окончание</label>
          <input
            className="admin-input"
            type="datetime-local"
            value={endsAt}
            onChange={(e) => setEndsAt(e.target.value)}
          />
        </div>
      </div>

      <div className="admin-form-group">
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
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Включено
        </label>
      </div>

      <h2 style={{ marginTop: 24 }}>Переопределения карточки</h2>
      <p
        style={{
          color: 'var(--admin-text-muted)',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        Пусто — берём значения из самой сущности.
      </p>

      <div className="admin-form-group">
        <label className="admin-label">Заголовок</label>
        <input
          className="admin-input"
          value={titleOverride}
          onChange={(e) => setTitleOverride(e.target.value)}
          maxLength={256}
        />
      </div>
      <div className="admin-form-group">
        <label className="admin-label">Подзаголовок</label>
        <input
          className="admin-input"
          value={subtitleOverride}
          onChange={(e) => setSubtitleOverride(e.target.value)}
          maxLength={512}
        />
      </div>
      <div className="admin-form-group">
        <label className="admin-label">Текст CTA-кнопки</label>
        <input
          className="admin-input"
          value={ctaOverride}
          onChange={(e) => setCtaOverride(e.target.value)}
          maxLength={64}
        />
      </div>
      <div className="admin-form-group">
        <label className="admin-label">URL обложки</label>
        <input
          className="admin-input"
          value={coverOverride}
          onChange={(e) => setCoverOverride(e.target.value)}
          maxLength={1024}
        />
      </div>

      {!isNew && statsQuery.data && (
        <>
          <h2 style={{ marginTop: 24 }}>Метрики (30 дней)</h2>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
            }}
          >
            <div className="admin-stat">
              <div style={{ fontSize: 12 }}>Показы</div>
              <div style={{ fontSize: 22 }}>
                {statsQuery.data.impressions}
              </div>
            </div>
            <div className="admin-stat">
              <div style={{ fontSize: 12 }}>Клики</div>
              <div style={{ fontSize: 22 }}>
                {statsQuery.data.clicks}
              </div>
            </div>
            <div className="admin-stat">
              <div style={{ fontSize: 12 }}>Плеи</div>
              <div style={{ fontSize: 22 }}>
                {statsQuery.data.plays}
              </div>
            </div>
            <div className="admin-stat">
              <div style={{ fontSize: 12 }}>CTR</div>
              <div style={{ fontSize: 22 }}>
                {(statsQuery.data.ctr * 100).toFixed(2)}%
              </div>
            </div>
          </div>
        </>
      )}

      <div
        style={{
          display: 'flex',
          gap: 8,
          marginTop: 24,
          flexWrap: 'wrap',
        }}
      >
        {isNew ? (
          <MotionPress
            variant="primary"
            disabled={!isReady || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? 'Создание...' : 'Создать'}
          </MotionPress>
        ) : (
          <MotionPress
            variant="primary"
            disabled={!isReady || patchMutation.isPending}
            onClick={() => patchMutation.mutate()}
          >
            {patchMutation.isPending ? 'Сохранение...' : 'Сохранить'}
          </MotionPress>
        )}
        <MotionPress
          variant="ghost"
          onClick={() => navigate(getAdminPanelRoute('/promotions'))}
        >
          Назад
        </MotionPress>
        {!isNew && (
          <MotionPress
            variant="danger"
            disabled={deleteMutation.isPending}
            onClick={async () => {
              const ok = await showConfirm('Действие необратимо.', {
                title: 'Удалить запись?',
                danger: true,
              })
              if (ok) deleteMutation.mutate()
            }}
          >
            Удалить
          </MotionPress>
        )}
      </div>
    </section>
  )
}
