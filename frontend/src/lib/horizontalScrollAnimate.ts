const rafByScroller = new WeakMap<HTMLElement, number>()

export const HORIZONTAL_PAGE_SCROLL_MS = 320

function easeOutCubic(t: number): number {
  const u = 1 - t
  return 1 - u * u * u
}

export function cancelHorizontalScrollAnimation(
  scroller: HTMLElement,
): void {
  const id = rafByScroller.get(scroller)
  if (id != null) {
    cancelAnimationFrame(id)
    rafByScroller.delete(scroller)
  }
}

export function animateScrollLeftTo(
  scroller: HTMLElement,
  targetLeft: number,
  options: { durationMs: number; instant: boolean },
): void {
  cancelHorizontalScrollAnimation(scroller)
  const from = scroller.scrollLeft
  const to = targetLeft
  if (options.instant || options.durationMs <= 0) {
    scroller.scrollLeft = to
    return
  }
  if (Math.abs(to - from) < 0.5) {
    scroller.scrollLeft = to
    return
  }
  const start = performance.now()
  const delta = to - from
  const tick = (now: number) => {
    const t = Math.min(
      1,
      (now - start) / options.durationMs,
    )
    const eased = easeOutCubic(t)
    scroller.scrollLeft = from + delta * eased
    if (t < 1) {
      rafByScroller.set(
        scroller,
        requestAnimationFrame(tick),
      )
    } else {
      rafByScroller.delete(scroller)
      scroller.scrollLeft = to
    }
  }
  rafByScroller.set(scroller, requestAnimationFrame(tick))
}

export function snapHorizontalScrollerToNearestPage(
  scroller: HTMLElement,
  options: { durationMs: number; instant: boolean },
): void {
  const w = scroller.clientWidth
  if (w <= 0) return
  const maxScroll = Math.max(
    0,
    scroller.scrollWidth - w,
  )
  const page = Math.round(scroller.scrollLeft / w)
  const target = Math.max(0, Math.min(page * w, maxScroll))
  animateScrollLeftTo(scroller, target, {
    durationMs: options.durationMs,
    instant: options.instant,
  })
}

export function scrollHorizontalByOnePage(
  scroller: HTMLElement,
  dir: 1 | -1,
  options: { durationMs: number; instant: boolean },
): void {
  const w = scroller.clientWidth
  if (w <= 0) return
  const maxScroll = Math.max(
    0,
    scroller.scrollWidth - w,
  )
  const next = Math.max(
    0,
    Math.min(scroller.scrollLeft + dir * w, maxScroll),
  )
  animateScrollLeftTo(scroller, next, {
    durationMs: options.durationMs,
    instant: options.instant,
  })
}
