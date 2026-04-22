import { useEffect, useState } from 'react'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'

interface MyComplaintItem {
  id: number
  track_id: number
  reason: string
  reason_type: string
  is_resolved: boolean
  track_hidden?: boolean
  created_at: string
  resolution_note?: string | null
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

function statusLabel(it: MyComplaintItem): {
  text: string
  cls: string
} {
  if (it.track_hidden) {
    return { text: 'Трек скрыт', cls: 'hidden' }
  }
  if (it.is_resolved) {
    return { text: 'Рассмотрена', cls: 'resolved' }
  }
  return { text: 'В работе', cls: '' }
}

export function MyComplaintsList() {
  const [items, setItems] = useState<
    MyComplaintItem[] | null
  >(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(
    null,
  )

  useEffect(() => {
    setLoading(true)
    api
      .getMyComplaints()
      .then((res) => {
        setItems(res.items || [])
        setError(null)
      })
      .catch((e) => {
        const msg =
          e instanceof Error ? e.message : '0'
        if (msg === '404') {
          setError('not_implemented')
        } else if (msg === '401') {
          setError('not_implemented')
        } else {
          setError('Не удалось загрузить жалобы')
        }
        setItems([])
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="my-complaints-empty">
        Загрузка…
      </div>
    )
  }

  if (error === 'not_implemented') {
    return (
      <div className="my-complaints-empty">
        <Icon
          name="info"
          size={28}
          className="offline-list-empty-icon"
        />
        <div>Раздел появится позже.</div>
      </div>
    )
  }

  if (!items || items.length === 0) {
    return (
      <div className="my-complaints-empty">
        <Icon
          name="flag"
          size={28}
          className="offline-list-empty-icon"
        />
        <div className="offline-list-empty-title">
          Жалоб пока нет
        </div>
        <div className="offline-list-empty-hint">
          Когда вы пожалуетесь на трек или
          отправите уведомление правообладателя,
          статус появится здесь.
        </div>
      </div>
    )
  }

  return (
    <div className="my-complaints">
      {items.map((it) => {
        const st = statusLabel(it)
        return (
          <div
            className="my-complaint-item"
            key={it.id}
          >
            <div className="my-complaint-row">
              <span>
                Трек #{it.track_id}
              </span>
              <span
                className={`my-complaint-status ${st.cls}`}
              >
                {st.text}
              </span>
            </div>
            <div className="my-complaint-reason">
              {it.reason}
            </div>
            {it.resolution_note && (
              <div className="my-complaint-meta">
                Комментарий модератора:{' '}
                {it.resolution_note}
              </div>
            )}
            <div className="my-complaint-meta">
              {fmtDate(it.created_at)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
