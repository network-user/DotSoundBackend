interface SCWidgetInstance {
  bind(event: string, callback: (e?: SCPlayProgressEvent) => void): void
  unbind(event: string): void
  play(): void
  pause(): void
  toggle(): void
  seekTo(ms: number): void
  getPosition(cb: (pos: number) => void): void
  getDuration(cb: (dur: number) => void): void
}

interface SCPlayProgressEvent {
  currentPosition: number
  duration: number
  loadedProgress: number
  relativePosition: number
}

declare const SC: {
  Widget: {
    (iframe: HTMLIFrameElement): SCWidgetInstance
    Events: {
      PLAY: string
      PAUSE: string
      FINISH: string
      PLAY_PROGRESS: string
      READY: string
      ERROR: string
    }
  }
}
