import WebApp from '@twa-dev/sdk'

WebApp.ready()
WebApp.expand()

export const tg = WebApp
export const telegramId: number | null =
  WebApp.initDataUnsafe?.user?.id ?? null

let _internalUserId: number | null = null

export function setInternalUserId(id: number): void {
  _internalUserId = id
}

export function getInternalUserId(): number | null {
  return _internalUserId
}

export const userId: number | null = telegramId
