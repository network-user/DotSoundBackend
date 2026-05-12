export function coverProxyUrl(imageKey: string): string {
  return (
    '/api/v1/tracks/cover_proxy?key='
    + encodeURIComponent(imageKey)
  )
}
