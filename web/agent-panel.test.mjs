import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  agentActionTitle,
  agentDisabledGuidance,
  agentLauncherLabel,
  agentRobotIconParts,
  clampPanelState,
  defaultPanelState,
  formatAgentCard,
  formatAgentReference,
  isNearRightDock,
  readPanelState,
  shouldAutoScroll,
  writePanelState,
} from "./agent-panel.js";

globalThis.__agentPanelSource = readFileSync(new URL("./agent-panel.js", import.meta.url), "utf8");

test("browser global exposes helpers used by app.js", () => {
  const source = globalThis.__agentPanelSource || "";
  assert.equal(source.includes("window.TradeEyeAgentPanel = { createAgentPanel, agentDisabledGuidance, formatAgentReference };"), true);
});

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

test("formatAgentReference renders readable fields and raw JSON", () => {
  const formatted = formatAgentReference({
    rule_id: "cashflow_quality",
    source: "cashflow",
    field: "n_cashflow_act",
    period: "20250630",
    value: 12.34,
    evidence_id: "ev-1",
  });

  assert.deepEqual(formatted.rows, [
    { label: "类型或规则", value: "cashflow_quality" },
    { label: "来源", value: "cashflow" },
    { label: "字段", value: "n_cashflow_act" },
    { label: "期间", value: "20250630" },
    { label: "数值", value: "12.34" },
  ]);
  assert.equal(formatted.raw.includes('"evidence_id": "ev-1"'), true);
});

test("formatAgentReference uses missing marker without fabricating values", () => {
  const formatted = formatAgentReference({ title: "事实引用" });

  assert.deepEqual(formatted.rows, [
    { label: "类型或规则", value: "事实引用" },
    { label: "来源", value: "未提供" },
    { label: "字段", value: "未提供" },
    { label: "期间", value: "未提供" },
    { label: "数值", value: "未提供" },
  ]);
});

test("agentActionTitle keeps action buttons in Chinese", () => {
  assert.equal(agentActionTitle({ action: "refetch_company" }), "重新抓取单票研判卡");
  assert.equal(agentActionTitle({ action: "rescan_disclosure_day" }), "重扫披露日");
  assert.equal(agentActionTitle({ action: "unknown_action" }), "执行建议动作");
});


test("agentDisabledGuidance explains LLM configuration", () => {
  assert.equal(
    agentDisabledGuidance,
    "Agent 问答需要配置外部 LLM API 后启用；当前仍可查看公司卡、依据弹窗和确定性 finding。",
  );
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
