import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import i18n from '@/lib/i18n'
import { api } from '@/lib/api'
import { getIsAdmin } from '@/lib/telegram'

type SlotConfig = {
  id: string
  label: string
  capability: string
  icon?: string
  action: string
  confirm?: boolean
}

type MenuConfig = {
  id: string
  label: string
  route: string
  icon?: string
  capability?: string | null
}

export type SlotRenderer = (args: {
  data?: Record<string, unknown>
  entry: SlotConfig
}) => ReactNode

interface AdminManifest {
  capabilities: string[]
  menu: MenuConfig[]
  slots: Record<string, SlotConfig[]>
  adminBundleUrl: string
  issuedAt: number
  expiresIn: number
  locale: string
}

interface AdminState {
  manifest: AdminManifest | null
  loading: boolean
  failed: boolean
  slotRenderers: Record<string, SlotRenderer>
  registerSlotRenderer: (
    context: string,
    render: SlotRenderer,
  ) => void
}

const Ctx = createContext<AdminState>({
  manifest: null,
  loading: false,
  failed: false,
  slotRenderers: {},
  registerSlotRenderer: () => {},
})

export function useAdmin() {
  return useContext(Ctx)
}

export function useAdminMenu(): MenuConfig[] {
  return useAdmin().manifest?.menu ?? []
}

export function useAdminSlotEntries(
  context: string,
): SlotConfig[] {
  return useAdmin().manifest?.slots?.[context] ?? []
}

export function AdminProvider({
  children,
}: {
  children: ReactNode
}) {
  const [manifest, setManifest] =
    useState<AdminManifest | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [failed, setFailed] = useState<boolean>(false)
  const [slotRenderers, setSlotRenderers] = useState<
    Record<string, SlotRenderer>
  >({})
  const [authTick, setAuthTick] = useState(0)
  const [langTick, setLangTick] = useState(0)

  const fetchManifest = useCallback(() => {
    setLoading(true)
    setFailed(false)
    api
      .getAdminManifest(i18n.language)
      .then((m) => setManifest(m))
      .catch(() => {
        setManifest(null)
        setFailed(true)
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!getIsAdmin()) return
    if (!api.getToken()) return
    if (authTick === 0) return
    if (loading) return
    if (manifest && manifest.locale === i18n.language) {
      return
    }
    fetchManifest()
  }, [
    fetchManifest,
    loading,
    manifest,
    authTick,
    langTick,
  ])

  useEffect(() => {
    const onAuthReady = () => setAuthTick((t) => t + 1)
    window.addEventListener('app-auth-ready', onAuthReady)
    return () =>
      window.removeEventListener(
        'app-auth-ready',
        onAuthReady,
      )
  }, [])

  useEffect(() => {
    const onLangChange = () =>
      setLangTick((t) => t + 1)
    i18n.on('languageChanged', onLangChange)
    return () => {
      i18n.off('languageChanged', onLangChange)
    }
  }, [])

  const registerSlotRenderer = useMemo(
    () =>
      (context: string, render: SlotRenderer) =>
        setSlotRenderers((s) => ({ ...s, [context]: render })),
    [],
  )

  const value = useMemo<AdminState>(
    () => ({
      manifest,
      loading,
      failed,
      slotRenderers,
      registerSlotRenderer,
    }),
    [
      manifest,
      loading,
      failed,
      slotRenderers,
      registerSlotRenderer,
    ],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
