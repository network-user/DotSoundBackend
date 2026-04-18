import { useEffect, useState, type MouseEvent } from 'react'
import { api } from '@/lib/api'
import { tg } from '@/lib/telegram'
import { usePlayer } from '@/store/PlayerContext'
import { Icon } from '@/components/Icon/Icon'

type ReasonType =
  | 'other'
  | 'copyright'
  | 'neighboring_rights'

type ComplaintMode = 'user' | 'rightsholder'

export function ComplaintModal() {
  const { track, isComplaintOpen, closeComplaint, stop } =
    usePlayer()
  const [reason, setReason] = useState('')
  const [mode, setMode] =
    useState<ComplaintMode>('user')
  const [reasonType, setReasonType] =
    useState<ReasonType>('copyright')
  const [email, setEmail] = useState('')
  const [rightsholderName, setRightsholderName] =
    useState('')
  const [proofUrl, setProofUrl] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!isComplaintOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeComplaint()
    }
    window.addEventListener('keydown', onKey)
    return () =>
      window.removeEventListener('keydown', onKey)
  }, [isComplaintOpen, closeComplaint])

  if (!isComplaintOpen || !track) return null

  const isRightsholderNotice = mode === 'rightsholder'

  const reset = () => {
    setReason('')
    setMode('user')
    setReasonType('copyright')
    setEmail('')
    setRightsholderName('')
    setProofUrl('')
    setError('')
  }

  const handleSubmit = async () => {
    setError('')
    if (reason.trim().length < 10) {
      setError('Укажите причину (минимум 10 символов)')
      return
    }
    if (isRightsholderNotice && !email.trim()) {
      setError('Укажите контактный e-mail для уведомления')
      return
    }
    if (
      isRightsholderNotice &&
      !rightsholderName.trim()
    ) {
      setError(
        'Укажите правообладателя или представителя',
      )
      return
    }
    if (isRightsholderNotice && !proofUrl.trim()) {
      setError('Добавьте ссылку на подтверждение прав')
      return
    }

    setSubmitting(true)
    try {
      const res = await api.submitComplaint({
        track_id: track.id,
        reason: reason.trim(),
        reason_type: isRightsholderNotice
          ? reasonType
          : 'other',
        contact_email: email.trim() || null,
        rightsholder_name:
          rightsholderName.trim() || null,
        proof_url: proofUrl.trim() || null,
      })
      closeComplaint()
      reset()
      const msg = res.track_hidden
        ? 'Жалоба принята. Доступ к треку ограничен.'
        : 'Жалоба принята и будет рассмотрена.'
      tg.showAlert(msg)
      if (res.track_hidden) stop()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      setError(
        msg === '409'
          ? 'Вы уже подавали жалобу на этот трек'
          : msg === '401'
            ? 'Требуется авторизация'
            : 'Ошибка отправки. Попробуйте позже.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleBackdrop = (
    e: MouseEvent<HTMLDivElement>,
  ) => {
    if (e.target === e.currentTarget) closeComplaint()
  }

  return (
    <div className="modal" onClick={handleBackdrop}>
      <div className="modal-content">
        <div className="modal-header">
          <h3>
            {isRightsholderNotice
              ? 'Уведомление правообладателя'
              : 'Жалоба на контент'}
          </h3>
          <button
            className="icon-btn"
            onClick={closeComplaint}
            aria-label="Закрыть"
          >
            <Icon name="x" size={18} />
          </button>
        </div>
        <p className="modal-hint">
          {isRightsholderNotice
            ? 'Если вы правообладатель или представитель, заполните уведомление максимально подробно. Требования и порядок рассмотрения: '
            : 'Используйте этот режим для обычной пользовательской жалобы на контент. Для официального уведомления правообладателя переключитесь в режим ниже.'}
          {isRightsholderNotice && (
            <a
              href="/legal/copyright"
              target="_blank"
              rel="noreferrer"
            >
              страница для правообладателей
            </a>
          )}
          {isRightsholderNotice && '.'}
        </p>
        <div className="form-group">
          <label className="form-label">Режим обращения</label>
          <div className="legal-doc-list">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setMode('user')}
            >
              Обычная жалоба
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setMode('rightsholder')}
            >
              Правообладатель
            </button>
          </div>
        </div>
        {isRightsholderNotice && (
          <div className="form-group">
            <label className="form-label">
              Тип прав
            </label>
            <select
              className="form-input"
              value={reasonType}
              onChange={(e) =>
                setReasonType(
                  e.target.value as ReasonType,
                )
              }
            >
              <option value="copyright">
                Авторские права
              </option>
              <option value="neighboring_rights">
                Смежные права
              </option>
            </select>
          </div>
        )}
        <div className="form-group">
          <label className="form-label">Причина *</label>
          <textarea
            className="form-input"
            rows={4}
            maxLength={1000}
            placeholder="Опишите нарушение (мин. 10 символов)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">
            Контактный e-mail
          </label>
          <input
            className="form-input"
            type="email"
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        {isRightsholderNotice && (
          <>
            <div className="form-group">
              <label className="form-label">
                Правообладатель / представитель *
              </label>
              <input
                className="form-input"
                type="text"
                placeholder="ФИО или название организации"
                value={rightsholderName}
                onChange={(e) =>
                  setRightsholderName(e.target.value)
                }
              />
            </div>
            <div className="form-group">
              <label className="form-label">
                Ссылка на подтверждение прав *
              </label>
              <input
                className="form-input"
                type="url"
                placeholder="https://example.com/proof"
                value={proofUrl}
                onChange={(e) =>
                  setProofUrl(e.target.value)
                }
              />
            </div>
          </>
        )}
        {error && <div className="form-error">{error}</div>}
        <button
          className="btn-primary"
          disabled={submitting}
          onClick={handleSubmit}
        >
          {isRightsholderNotice
            ? 'Отправить уведомление'
            : 'Отправить жалобу'}
        </button>
      </div>
    </div>
  )
}
