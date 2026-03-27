import WebApp from '@twa-dev/sdk'

WebApp.ready()
WebApp.expand()

export const tg = WebApp
export const userId: number | null = WebApp.initDataUnsafe?.user?.id ?? null
