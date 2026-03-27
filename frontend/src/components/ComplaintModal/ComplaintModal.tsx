import { useState } from 'react'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import { tg } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'

export function ComplaintModal() {
  const { track, isComplaintOpen, closeComplaint, stop } = usePlayer()
  const [reason, setReason] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!isComplaintOpen || !track) return null

  const handleSubmit = async () => {
    setError('')
    if (reason.trim().length < 10) {
      setError('Укажите причину (минимум 10 символов)')
      return
    }
    if (!userId) {
      setError('Необходима авторизация через Telegram')
      return
    }
    setSubmitting(true)
    try {
      const res = await api.submitComplaint({
        track_id: track.id,
        reported_by_user_id: userId,
        reason: reason.trim(),
        contact_email: email.trim() || null,
      })
      closeComplaint()
      setReason('')
      setEmail('')
      const msg = res.track_hidden
        ? '✅ Жалоба принята. Трек скрыт.'
        : '✅ Жалоба принята и будет рассмотрена.'
      tg.showAlert(msg)
      if (res.track_hidden) stop()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      setError(
        msg === '409'
          ? 'Вы уже подавали жалобу на этот трек'
          : 'Ошибка отправки. Попробуйте позже.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleBackdrop = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) closeComplaint()
  }

  return (
    <div className="modal" onClick={handleBackdrop}>
      <div className="modal-content">
        <div className="modal-header">
          <h3>🚩 Жалоба на нарушение АП</h3>
          <button className="icon-btn" onClick={closeComplaint}>✕</button>
        </div>
        <p className="modal-hint">
          Форма уведомления правообладателя (ст.&nbsp;1253.1 ГК РФ).
          Укажите причину и контакт для обратной связи.
        </p>
        <div className="form-group">
          <label className="form-label">Причина *</label>
          <textarea
            className="form-input"
            rows={4}
            maxLength={1000}
            placeholder="Опишите нарушение (мин. 10 символов)…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Контактный e-mail</label>
          <input
            className="form-input"
            type="email"
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="btn-primary" disabled={submitting} onClick={handleSubmit}>
          Отправить жалобу
        </button>
      </div>
    </div>
  )
}
