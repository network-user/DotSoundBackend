import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { setInternalUserId } from '@/lib/telegram'
import { connectWS } from '@/lib/ws'
import { useBrandLabel } from '@/lib/brand'
import { AmbientStage } from '@/components/ui/AmbientStage'
import { KenBurnsCover } from '@/components/ui/KenBurnsCover'
import { MotionPress } from '@/components/ui/MotionPress'
import {
  dismissIsland,
  showIsland,
} from '@/lib/island'

const AUTH_KB_SRC =
  'data:image/svg+xml,' +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24'>" +
      "<rect width='24' height='24' fill='%23242424'/></svg>",
  )

function notifyAuthReady(token: string | null): void {
  if (token) {
    try {
      connectWS(token)
    } catch {
      /* ignore */
    }
  }
  try {
    window.dispatchEvent(
      new Event('app-auth-ready'),
    )
  } catch {
    /* ignore */
  }
}

type Step =
  | 'email'
  | 'check_inbox'
  | 'totp'
  | 'success'

interface Props {
  onAuth: () => void
  onBack: () => void
}

export function EmailAuth({
  onAuth,
  onBack,
}: Props) {
  const { t } = useTranslation()
  const brandLabel = useBrandLabel()
  const progressRef = useRef<string | null>(null)
  const successTimer = useRef<ReturnType<
    typeof setTimeout
  > | null>(null)
  const [step, setStep] =
    useState<Step>('email')
  const [email, setEmail] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [sessionToken, setSessionToken] =
    useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [
    fallbackMode,
    setFallbackMode,
  ] = useState(false)

  useEffect(() => {
    if (!loading) {
      if (progressRef.current) {
        dismissIsland(progressRef.current)
        progressRef.current = null
      }
      return
    }
    const id = showIsland({
      kind: 'progress',
      title: t(
        'redesign.nav.authWorking',
        'Signing in…',
      ),
    })
    progressRef.current = id
    return () => {
      dismissIsland(id)
      if (progressRef.current === id) {
        progressRef.current = null
      }
    }
  }, [loading, t])
  const [fallbackSent, setFallbackSent] =
    useState(false)

  useEffect(() => {
    const params = new URLSearchParams(
      window.location.search,
    )
    const token = params.get('token')
    if (token) {
      window.history.replaceState(
        {},
        '',
        window.location.pathname,
      )
      handleVerifyToken(token)
    }
    return () => {
      if (successTimer.current)
        clearTimeout(successTimer.current)
    }
  }, [])

  const handleRequestLink = async () => {
    if (!email.trim() || !email.includes('@')) {
      setError(t('auth.email.invalidEmail'))
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.requestMagicLink(email.trim())
      setStep('check_inbox')
    } catch {
      setError(
        t('auth.email.sendLinkError'),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyToken = async (
    token: string,
  ) => {
    setLoading(true)
    setError('')
    try {
      const res =
        await api.verifyMagicLink(token)
      if (res.requires_2fa && res.session_token) {
        setSessionToken(res.session_token)
        setStep('totp')
      } else if (res.user_id) {
        setInternalUserId(res.user_id)
        notifyAuthReady(res.access_token)
        setStep('success')
        successTimer.current = setTimeout(
          onAuth,
          1500,
        )
      }
    } catch {
      setError(
        t('auth.email.linkExpired'),
      )
      setStep('email')
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyTotp = async () => {
    const digits = totpCode.replace(/\s/g, '')
    if (digits.length !== 6) {
      setError(t('auth.email.totpLengthError'))
      return
    }
    setLoading(true)
    setError('')
    try {
      let res
      if (fallbackMode) {
        res =
          await api.verify2FAEmailFallback(
            sessionToken,
            digits,
          )
      } else {
        res = await api.verify2FA(
          sessionToken,
          digits,
        )
      }
      if (res.user_id) {
        setInternalUserId(res.user_id)
        notifyAuthReady(res.access_token)
        setStep('success')
        successTimer.current = setTimeout(
          onAuth,
          1500,
        )
      }
    } catch {
      setError(t('auth.email.totpWrong'))
    } finally {
      setLoading(false)
    }
  }

  const handleRequestFallback = async () => {
    setError('')
    try {
      await api.request2FAEmailFallback(
        sessionToken,
      )
      setFallbackMode(true)
      setFallbackSent(true)
      setTotpCode('')
    } catch {
      setError(
        t('auth.email.fallbackSendError'),
      )
    }
  }

  return (
    <div className="auth-screen rb-auth-screen">
      <AmbientStage
        coverUrl={null}
        className="rb-auth__stage"
      >
        <KenBurnsCover
          src={AUTH_KB_SRC}
          alt=""
          duration={22}
          className="rb-auth__kb"
        />
      </AmbientStage>
      <div className="auth-card rb-auth__card glass--strong">
        <div className="auth-logo">{brandLabel}</div>

        {step === 'email' && (
          <>
            <h2 className="auth-title">
              {t('auth.email.title')}
            </h2>
            <p className="auth-hint">
              {t('auth.email.enterHintLine1')}
              <br />
              {t('auth.email.enterHintLine2')}
            </p>
            <input
              className="form-input"
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
              onKeyDown={(e) =>
                e.key === 'Enter' &&
                handleRequestLink()
              }
              autoFocus
            />
            {error && (
              <div className="form-error">
                {error}
              </div>
            )}
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary auth-tg-btn"
              onClick={handleRequestLink}
              disabled={loading}
            >
              {loading
                ? t('auth.email.sending')
                : t('auth.email.getLink')}
            </MotionPress>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary auth-back"
              onClick={onBack}
            >
              {t('auth.email.back')}
            </MotionPress>
          </>
        )}

        {step === 'check_inbox' && (
          <>
            <h2 className="auth-title">
              {t('auth.email.checkInboxTitle')}
            </h2>
            <p className="auth-hint">
              {t('auth.email.checkInboxLine1')}
              <br />
              <strong>{email}</strong>
              <br />
              {t('auth.email.checkInboxLine2')}
            </p>
            <MotionPress
              type="button"
              variant="ghost"
              haptic="light"
              className="btn-secondary auth-back"
              onClick={() => {
                setStep('email')
                setError('')
              }}
            >
              {t('auth.email.resend')}
            </MotionPress>
          </>
        )}

        {step === 'totp' && (
          <>
            <h2 className="auth-title">
              {fallbackMode
                ? t('auth.email.totpFallbackTitle')
                : t('auth.email.totpTitle')}
            </h2>
            <p className="auth-hint">
              {fallbackMode
                ? t('auth.email.totpFallbackHint')
                : t('auth.email.totpHint')}
            </p>
            <input
              className="form-input auth-code-input"
              type="text"
              inputMode="numeric"
              maxLength={fallbackMode ? 7 : 6}
              placeholder={
                fallbackMode
                  ? '000 000'
                  : '000000'
              }
              value={totpCode}
              onChange={(e) =>
                setTotpCode(
                  fallbackMode
                    ? e.target.value.replace(
                        /[^\d ]/g,
                        '',
                      )
                    : e.target.value.replace(
                        /\D/g,
                        '',
                      ),
                )
              }
              onKeyDown={(e) =>
                e.key === 'Enter' &&
                handleVerifyTotp()
              }
              autoFocus
            />
            {error && (
              <div className="form-error">
                {error}
              </div>
            )}
            <MotionPress
              type="button"
              variant="primary"
              haptic="medium"
              className="btn-primary"
              onClick={handleVerifyTotp}
              disabled={loading}
            >
              {loading
                ? t('auth.email.checking')
                : t('auth.email.confirm')}
            </MotionPress>
            {!fallbackMode && (
              <MotionPress
                type="button"
                variant="ghost"
                haptic="light"
                className="btn-secondary auth-back"
                onClick={handleRequestFallback}
                disabled={fallbackSent}
              >
                {fallbackSent
                  ? t('auth.email.fallbackSentLabel')
                  : t('auth.email.getFallbackCode')}
              </MotionPress>
            )}
          </>
        )}

        {step === 'success' && (
          <>
            <div className="auth-success-icon" />

            <h2 className="auth-title">
              {t('auth.email.successTitle')}
            </h2>
            <p className="auth-hint">
              {t('auth.email.successHint', { brand: brandLabel })}
            </p>
          </>
        )}
      </div>
    </div>
  )
}
