import { onMounted, onBeforeUnmount, nextTick } from 'vue'

const SELECTOR = '[data-tv-focus]:not([disabled]):not([aria-hidden="true"])'

function center(rect) {
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

function findNext(current, direction) {
  const originRect = current.getBoundingClientRect()
  const origin = center(originRect)
  const candidates = [...document.querySelectorAll(SELECTOR)].filter(el => el !== current && el.offsetParent !== null)

  let best = null
  let bestScore = Infinity
  for (const candidate of candidates) {
    const point = center(candidate.getBoundingClientRect())
    const dx = point.x - origin.x
    const dy = point.y - origin.y
    const valid = direction === 'left' ? dx < -8
      : direction === 'right' ? dx > 8
        : direction === 'up' ? dy < -8
          : dy > 8
    if (!valid) continue

    const primary = direction === 'left' || direction === 'right' ? Math.abs(dx) : Math.abs(dy)
    const secondary = direction === 'left' || direction === 'right' ? Math.abs(dy) : Math.abs(dx)
    const score = primary + secondary * 2.5
    if (score < bestScore) {
      bestScore = score
      best = candidate
    }
  }
  return best
}

function focusElement(element) {
  if (!element) return
  element.focus({ preventScroll: true })
  element.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
}

export function focusFirst(selector = SELECTOR) {
  nextTick(() => focusElement(document.querySelector(selector)))
}

function focusInitial() {
  nextTick(() => {
    const active = document.activeElement
    if (active?.matches?.(SELECTOR) && active.offsetParent !== null) return

    const currentRoute = document.querySelector('.router-link-exact-active[data-tv-focus]')
    focusElement(currentRoute || document.querySelector(SELECTOR))
  })
}

export function useSpatialNavigation({ onBack } = {}) {
  function keyHandler(event) {
    const directions = {
      ArrowLeft: 'left',
      ArrowRight: 'right',
      ArrowUp: 'up',
      ArrowDown: 'down',
    }

    if (directions[event.key]) {
      const active = document.activeElement?.matches?.(SELECTOR)
        ? document.activeElement
        : document.querySelector(SELECTOR)
      const next = active && findNext(active, directions[event.key])
      if (next) {
        event.preventDefault()
        focusElement(next)
      }
      return
    }

    if (event.key === 'Enter' && document.activeElement?.matches?.(SELECTOR)) {
      if (event.repeat) event.preventDefault()
      return
    }

    if (event.key === ' ' && document.activeElement?.matches?.(SELECTOR)) {
      event.preventDefault()
      if (!event.repeat) document.activeElement.click()
      return
    }

    if (event.key === 'Escape') {
      event.preventDefault()
      onBack?.()
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', keyHandler)
    focusInitial()
  })
  onBeforeUnmount(() => window.removeEventListener('keydown', keyHandler))
}
