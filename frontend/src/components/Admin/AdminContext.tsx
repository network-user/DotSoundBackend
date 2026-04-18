import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
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

function importByHint(hint: string) {
  /* @vite-ignore */
  return import(/* @vite-ignore */ hint)
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

  useEffect(() => {
    if (!getIsAdmin()) return
    if (manifest || loading || failed) return
    setLoading(true)
    api
      .getAdminManifest()
      .then(async (m) => {
        setManifest(m)
        if (m?.adminBundleUrl) {
          try {
            await importByHint(m.adminBundleUrl)
          } catch {
            setFailed(true)
          }
        }
      })
      .catch(() => {
        setFailed(true)
      })
      .finally(() => setLoading(false))
  }, [manifest, loading, failed])

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
