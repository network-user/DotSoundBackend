import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'

export function useNavigateToArtistByName(): (
  name: string | null | undefined,
) => Promise<void> {
  const navigate = useNavigate()

  return useCallback(
    async (name: string | null | undefined) => {
      const trimmed = name?.trim()
      if (!trimmed) return
      const res = await api.resolveArtistByName(trimmed)
      if (res) {
        navigate(`/artist/${res.id}`)
      }
    },
    [navigate],
  )
}
