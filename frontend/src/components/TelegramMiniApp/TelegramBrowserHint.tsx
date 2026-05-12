import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { m, VARIANTS_FADE_UP } from '@/lib/motion'
import { showIsland } from '@/lib/island'
import { haptic } from '@/lib/telegram'
import {
  buildMiniAppAbsoluteUrl,
  dismissTelegramBrowserHint,
  isTelegramBrowserHintSuppressed,
} from '@/lib/telegramBrowserHint'
import { isTelegram, tg } from '@/lib/telegram'

const DELAY_MS = 120_000

export function TelegramBrowserHint() {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!isTelegram()) return
    if (isTelegramBrowserHintSuppressed()) return
    const id = window.setTimeout(() => {
      if (isTelegramBrowserHintSuppressed()) return
      setVisible(true)
    }, DELAY_MS)
    return () => window.clearTimeout(id)
  }, [])

  if (!visible) return null

  const url = buildMiniAppAbsoluteUrl()

  const openExternal = () => {
    haptic('light')
    try {
      const wa = tg as {
        openLink?: (u: string) => void
      }
      wa.openLink?.(url)
    } catch {
      /* ignore */
    }
    dismissTelegramBrowserHint()
    setVisible(false)
  }

  const onDismiss = () => {
    haptic('light')
    dismissTelegramBrowserHint()
    setVisible(false)
  }

  const onCopy = async () => {
    haptic('light')
    try {
      await navigator.clipboard.writeText(url)
      showIsland({
        kind: 'toast',
        title: t('redesign.telegramBrowserHint.copied'),
        durationMs: 2200,
      })
    } catch {
      showIsland({
        kind: 'toast',
        title: t('redesign.telegramBrowserHint.copyFail'),
        durationMs: 2400,
      })
    }
  }

  return (
    <div className="telegram-browser-hint-portal">
      <m.aside
        className="telegram-browser-hint rb-install glass--medium"
        role="region"
        aria-label={t('redesign.telegramBrowserHint.title')}
        initial="hidden"
        animate="visible"
        variants={VARIANTS_FADE_UP}
      >
        <div className="telegram-browser-hint__icon" aria-hidden>
          <Icon name="maximize" size={22} />
        </div>
        <div className="telegram-browser-hint__body">
          <div className="telegram-browser-hint__title">
            {t('redesign.telegramBrowserHint.title')}
          </div>
          <p className="telegram-browser-hint__text">
            {t('redesign.telegramBrowserHint.body')}
          </p>
          <button
            type="button"
            className="telegram-browser-hint__copy"
            onClick={() => void onCopy()}
          >
            {t('redesign.telegramBrowserHint.copy')}
          </button>
        </div>
        <div className="telegram-browser-hint__actions">
          <MotionPress
            variant="primary"
            className="telegram-browser-hint__btn telegram-browser-hint__btn--primary"
            haptic="medium"
            onClick={openExternal}
          >
            {t('redesign.telegramBrowserHint.open')}
          </MotionPress>
          <MotionPress
            variant="ghost"
            className="telegram-browser-hint__btn telegram-browser-hint__btn--ghost"
            haptic="light"
            onClick={onDismiss}
          >
            {t('redesign.telegramBrowserHint.dismiss')}
          </MotionPress>
        </div>
      </m.aside>
    </div>
  )
}
