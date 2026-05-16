import { isTelegram } from '@/lib/telegram'
import { isStandalone } from '@/lib/pwaInstall'

export const PWA_ONBOARDING_SEEN_KEY = 'pwa-onb-seen'
export const PWA_INSTALL_DISMISS_KEY = 'pwa-install-dismissed-at'

export function shouldShowPwaOnboardingModal(): boolean {
  if (isTelegram()) return false
  if (isStandalone()) return false
  try {
    return !localStorage.getItem(PWA_ONBOARDING_SEEN_KEY)
  } catch {
    return false
  }
}
