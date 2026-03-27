import { reactive, watch } from 'vue'

const DRAWER_KEY = 'pr_agents_debug_drawer'

function readStorage(key, fallback) {
  try {
    const value = window.localStorage.getItem(key)
    return value ? JSON.parse(value) : fallback
  } catch {
    return fallback
  }
}

export function useDebugDrawerState() {
  const initial = typeof window !== 'undefined'
    ? readStorage(DRAWER_KEY, {
      drawerOpen: false,
      panels: {
        toolCalls: true,
        promptSnapshot: false,
        memoryState: false,
        executionControls: true,
      },
    })
    : {
      drawerOpen: false,
      panels: {
        toolCalls: true,
        promptSnapshot: false,
        memoryState: false,
        executionControls: true,
      },
    }

  const state = reactive(initial)

  function toggleDrawer() {
    state.drawerOpen = !state.drawerOpen
  }

  function togglePanel(panelKey) {
    state.panels[panelKey] = !state.panels[panelKey]
  }

  if (typeof window !== 'undefined') {
    watch(
      () => ({ drawerOpen: state.drawerOpen, panels: state.panels }),
      (value) => window.localStorage.setItem(DRAWER_KEY, JSON.stringify(value)),
      { deep: true },
    )
  }

  return {
    state,
    toggleDrawer,
    togglePanel,
  }
}
