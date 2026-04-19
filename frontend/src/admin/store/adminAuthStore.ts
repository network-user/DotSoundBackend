import { create } from 'zustand'

export type AdminAuthStatus =
  | 'loading'
  | 'unauth'
  | 'needs_init'
  | 'needs_login'
  | 'needs_device_approval'
  | 'authenticated'

export interface AdminAuthState {
  status: AdminAuthStatus
  accessToken: string | null
  expiresAt: number | null
  pendingDeviceId: number | null
  capabilities: string[]
  setStatus: (status: AdminAuthStatus) => void
  setSession: (
    token: string,
    expiresInSeconds: number,
  ) => void
  setPendingDevice: (id: number) => void
  setCapabilities: (caps: string[]) => void
  reset: () => void
}

export const useAdminAuth = create<AdminAuthState>(
  (set) => ({
    status: 'loading',
    accessToken: null,
    expiresAt: null,
    pendingDeviceId: null,
    capabilities: [],
    setStatus: (status) => set({ status }),
    setSession: (token, expiresInSeconds) =>
      set({
        status: 'authenticated',
        accessToken: token,
        expiresAt:
          Date.now() + expiresInSeconds * 1000,
        pendingDeviceId: null,
      }),
    setPendingDevice: (id) =>
      set({
        status: 'needs_device_approval',
        pendingDeviceId: id,
      }),
    setCapabilities: (caps) =>
      set({ capabilities: caps }),
    reset: () =>
      set({
        status: 'unauth',
        accessToken: null,
        expiresAt: null,
        pendingDeviceId: null,
        capabilities: [],
      }),
  }),
)
