const STORAGE_KEY = "tradeeye.agentPanel";
const MIN_WIDTH = 320;
const MAX_WIDTH = 560;
const MIN_HEIGHT = 360;
const MAX_HEIGHT = 720;
const DOCK_THRESHOLD = 24;
const VISIBLE_MIN_WIDTH = 120;
const VISIBLE_MIN_HEIGHT = 80;

export const defaultPanelState = {
  mode: "docked",
  open: false,
  left: 0,
  top: 72,
  width: 400,
  height: 520,
};

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export function isNearRightDock({ left, width, viewportWidth, threshold = DOCK_THRESHOLD }) {
  return viewportWidth - (left + width) <= threshold;
}

export function clampPanelState(state, viewport) {
  const merged = { ...defaultPanelState, ...state };
  const width = clamp(Number(merged.width) || defaultPanelState.width, MIN_WIDTH, MAX_WIDTH);
  if (merged.mode === "docked") {
    return { ...defaultPanelState, ...merged, mode: "docked", width, height: defaultPanelState.height };
  }

  const height = clamp(Number(merged.height) || defaultPanelState.height, MIN_HEIGHT, Math.min(MAX_HEIGHT, viewport.height));
  const maxLeft = Math.max(0, viewport.width - VISIBLE_MIN_WIDTH);
  const maxTop = Math.max(0, viewport.height - VISIBLE_MIN_HEIGHT);
  return {
    ...defaultPanelState,
    ...merged,
    mode: "floating",
    width,
    height,
    left: clamp(Number(merged.left) || 0, 0, maxLeft),
    top: clamp(Number(merged.top) || 0, 0, maxTop),
  };
}

export function readPanelState(storage = window.localStorage) {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return { ...defaultPanelState };
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return { ...defaultPanelState };
    return { ...defaultPanelState, ...parsed };
  } catch {
    return { ...defaultPanelState };
  }
}

export function writePanelState(storage = window.localStorage, state) {
  storage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      mode: state.mode,
      open: Boolean(state.open),
      left: Number(state.left),
      top: Number(state.top),
      width: Number(state.width),
      height: Number(state.height),
    }),
  );
}

export function shouldAutoScroll({ scrollHeight, scrollTop, clientHeight }, threshold = 40) {
  return scrollHeight - scrollTop - clientHeight < threshold;
}

export function createAgentPanel() {
  throw new Error("createAgentPanel DOM implementation is added in Task 5");
}

if (typeof window !== "undefined") {
  window.TradeEyeAgentPanel = { createAgentPanel };
}
