import test from "node:test";
import assert from "node:assert/strict";

import {
  agentLauncherLabel,
  agentRobotIconParts,
  clampPanelState,
  defaultPanelState,
  formatAgentCard,
  isNearRightDock,
  readPanelState,
  shouldAutoScroll,
  writePanelState,
} from "./agent-panel.js";

test("formatAgentCard renders name first and code subtitle", () => {
  assert.deepEqual(
    formatAgentCard({ title: "石大胜华", subtitle: "603026.SH · 2025 半年报", ts_code: "603026.SH", period: "20250630" }),
    { title: "石大胜华", subtitle: "603026.SH · 2025 半年报" },
  );
  assert.deepEqual(
    formatAgentCard({ ts_code: "603026.SH", period: "20250630" }),
    { title: "603026.SH", subtitle: "20250630" },
  );
});

test("agent launcher uses accessible robot icon without visible text", () => {
  assert.equal(agentLauncherLabel, "打开 Agent 问答");
  assert.deepEqual(agentRobotIconParts, ["antenna", "head", "eye-left", "eye-right", "mouth"]);
  assert.equal(agentRobotIconParts.includes("Agent"), false);
});
test("isNearRightDock returns true within threshold", () => {
  assert.equal(isNearRightDock({ left: 956, width: 320, viewportWidth: 1280, threshold: 24 }), true);
  assert.equal(isNearRightDock({ left: 900, width: 320, viewportWidth: 1280, threshold: 24 }), false);
});

test("clampPanelState keeps floating window visible and sized", () => {
  const state = clampPanelState(
    { mode: "floating", open: true, left: -500, top: -200, width: 999, height: 99 },
    { width: 1280, height: 720 },
  );

  assert.equal(state.width, 560);
  assert.equal(state.height, 360);
  assert.equal(state.left, 0);
  assert.equal(state.top, 0);
});

test("clampPanelState clamps docked width only", () => {
  const state = clampPanelState(
    { mode: "docked", open: true, left: 12, top: 12, width: 999, height: 999 },
    { width: 1280, height: 720 },
  );

  assert.equal(state.mode, "docked");
  assert.equal(state.width, 560);
  assert.equal(state.height, defaultPanelState.height);
});

test("readPanelState falls back to defaults for invalid JSON", () => {
  const storage = new Map([["tradeeye.agentPanel", "not json"]]);

  assert.deepEqual(readPanelState({ getItem: (key) => storage.get(key) }), defaultPanelState);
});

test("writePanelState serializes stable state", () => {
  const storage = new Map();

  writePanelState(
    { setItem: (key, value) => storage.set(key, value) },
    { mode: "floating", open: true, left: 12, top: 24, width: 420, height: 500 },
  );

  assert.equal(
    storage.get("tradeeye.agentPanel"),
    JSON.stringify({ mode: "floating", open: true, left: 12, top: 24, width: 420, height: 500 }),
  );
});

test("shouldAutoScroll only returns true near bottom", () => {
  assert.equal(shouldAutoScroll({ scrollHeight: 1000, scrollTop: 760, clientHeight: 220 }), true);
  assert.equal(shouldAutoScroll({ scrollHeight: 1000, scrollTop: 600, clientHeight: 220 }), false);
});
