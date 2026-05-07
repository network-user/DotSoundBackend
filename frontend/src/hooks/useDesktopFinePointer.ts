import { useMatchMedia } from '@/hooks/useMatchMedia'

export const DESKTOP_FINE_MEDIA =
  '(min-width: 561px) and (pointer: fine)'

export function useDesktopFinePointer(): boolean {
  return useMatchMedia(DESKTOP_FINE_MEDIA)
}
