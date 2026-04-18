import { useAdmin, useAdminSlotEntries } from './AdminContext'

interface Props {
  context: string
  data?: Record<string, unknown>
}

export function AdminSlot({ context, data }: Props) {
  const { slotRenderers } = useAdmin()
  const entries = useAdminSlotEntries(context)
  if (!entries.length) return null
  const renderer = slotRenderers[context]
  if (!renderer) return null
  return (
    <>
      {entries.map((entry) => (
        <span key={entry.id}>
          {renderer({ data, entry })}
        </span>
      ))}
    </>
  )
}
