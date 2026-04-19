import { useAdmin } from '@/components/Admin/AdminContext'

/**
 * Returns ``true`` when the current admin has the requested
 * capability inside the manifest. Use to conditionally render
 * privileged actions so non-privileged admins don't see buttons
 * that would just return 403 from the backend.
 */
export function useCapability(
  capability: string,
): boolean {
  const ctx = useAdmin()
  const caps =
    ctx.manifest?.capabilities ?? []
  return caps.includes(capability)
}

export function useCapabilities(): string[] {
  const ctx = useAdmin()
  return ctx.manifest?.capabilities ?? []
}

interface IfCanProps {
  capability: string
  children: React.ReactNode
  fallback?: React.ReactNode
}

export function IfCan({
  capability,
  children,
  fallback = null,
}: IfCanProps): React.ReactNode {
  const allowed = useCapability(capability)
  return allowed ? children : fallback
}
