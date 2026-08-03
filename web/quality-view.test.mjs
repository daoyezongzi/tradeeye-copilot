import test from "node:test";
import assert from "node:assert/strict";

import {
  comparabilityWarningText,
  createRadarPoints,
  qualityStatusKey,
  qualityStatusMeta,
  qualitySummaryText,
  radarAxisLabel,
} from "./quality-view.js";

test("qualityStatusKey falls back to not evaluated", () => {
  assert.equal(qualityStatusKey({ status: "NORMAL" }), "NORMAL");
  assert.equal(qualityStatusKey({ status: "UNKNOWN" }), "NOT_EVALUATED");
  assert.equal(qualityStatusKey(null), "NOT_EVALUATED");
});

test("qualityStatusMeta exposes readable labels and classes", () => {
  assert.equal(qualityStatusMeta("ANOMALY").label, "异常");
  assert.equal(qualityStatusMeta("WATCH").cls, "yellow");
  assert.equal(qualityStatusMeta("NORMAL").cls, "ok");
});

test("qualitySummaryText uses overview summary without scores", () => {
  assert.equal(
    qualitySummaryText({ summary: "异常 1 项 / 关注 1 项 / 正常 4 项" }),
    "异常 1 项 / 关注 1 项 / 正常 4 项",
  );
  assert.equal(qualitySummaryText(null), "暂无经营质量因子");
});

test("comparabilityWarningText explains exploratory comparisons", () => {
  assert.equal(comparabilityWarningText({ comparability: "STRICT", warnings: [] }), "严格可比");
  assert.equal(
    comparabilityWarningText({ comparability: "EXPLORATORY", warnings: ["期间不一致，仅供探索，不作为严格横向比较"] }),
    "期间不一致，仅供探索，不作为严格横向比较",
  );
});

test("radarAxisLabel shortens factor labels for readable axis text", () => {
  assert.equal(radarAxisLabel({ label: "收入兑现质量" }), "收入兑现");
  assert.equal(radarAxisLabel({ label: "现金质量" }), "现金质量");
  assert.equal(radarAxisLabel({ factor_id: "cashflow_quality" }), "现金质量");
});


test("createRadarPoints maps statuses to bands", () => {
  const points = createRadarPoints([
    { status: "NORMAL" },
    { status: "WATCH" },
    { status: "ANOMALY" },
    { status: "NOT_EVALUATED" },
  ]);

  assert.equal(points[0].radius, 42);
  assert.equal(points[1].radius, 30);
  assert.equal(points[2].radius, 18);
  assert.equal(points[3].radius, 0);
});
