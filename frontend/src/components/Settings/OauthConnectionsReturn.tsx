import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useToast } from '@/components/ui/Toast'

const providerLabels: Record<string, string> = {
  spotify: 'Spotify',
  vk: 'VK',
  soundcloud: 'SoundCloud',
}

const RETURN_ONCE_PREFIX = 'dotsound:oauthConnectionsReturn:'

/**
 * OAuth redirect target from the backend (linked-accounts callback).
 * Shows a short toast and sends the user back to the app shell.
 */
export function OauthConnectionsReturn() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    const query = searchParams.toString()
    const onceKey = `${RETURN_ONCE_PREFIX}${query || '_'}`
    if (query && sessionStorage.getItem(onceKey)) {
      navigate('/profile', { replace: true })
      return
    }
    if (query) sessionStorage.setItem(onceKey, '1')

    const err = searchParams.get('error')
    const providerParam = searchParams.get('provider') || ''
    const connected = searchParams.get('connected')

    if (err === 'oauth_failed') {
      const name = providerLabels[providerParam] || 'сервис'
      toast.error(`Не удалось подключить ${name}`)
      navigate('/profile', { replace: true })
      return
    }
    if (connected) {
      const name = providerLabels[connected] || connected
      toast.success(`Аккаунт ${name} подключён`)
      navigate('/profile', { replace: true })
      return
    }
    navigate('/', { replace: true })
  }, [navigate, searchParams, toast])

  return (
    <div
      className="loader"
      style={{ margin: '40vh auto' }}
      role="status"
      aria-label="Возврат из авторизации"
    />
  )
}
