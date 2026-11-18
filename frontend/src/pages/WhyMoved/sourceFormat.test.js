import assert from "node:assert/strict";
import { test } from "node:test";
import {
  comparisonItems,
  formatChange,
  formatSourceDate,
  sourceCount,
  sourceLine,
} from "./sourceFormat.js";

test("formats a date", () => {
  assert.equal(formatSourceDate("2026-11-09T18:07:12+00:00"), "Nov 9, 2026");
});

test("a missing or invalid date gives an empty string", () => {
  assert.equal(formatSourceDate(""), "");
  assert.equal(formatSourceDate(undefined), "");
  assert.equal(formatSourceDate("not a date"), "");
});

test("source line shows publisher and date", () => {
  const src = { source: "Reuters", publishedAt: "2026-11-09T18:07:12+00:00" };
  assert.equal(sourceLine(src), "Reuters · Nov 9, 2026");
});

test("source line leaves out what is missing", () => {
  assert.equal(sourceLine({ source: "Reuters" }), "Reuters");
  assert.equal(sourceLine({ publishedAt: "2026-11-09T18:07:12+00:00" }), "Nov 9, 2026");
  assert.equal(sourceLine({}), "");
});

test("counts sources", () => {
  assert.equal(sourceCount(1), "1 source");
  assert.equal(sourceCount(5), "5 sources");
});

test("formats a percent change with its sign", () => {
  assert.equal(formatChange(1.2), "+1.20%");
  assert.equal(formatChange(-0.15), "-0.15%");
  assert.equal(formatChange(0), "0.00%");
  assert.equal(formatChange(undefined), "");
});

test("comparison chips list the indexes, then the sector", () => {
  const comparison = {
    indexes: [{ name: "S&P 500", changePercent: 0.42 }],
    sector: { name: "Technology", etf: "XLK", changePercent: 1.2 },
  };
  assert.deepEqual(comparisonItems(comparison), [
    { label: "S&P 500", change: 0.42 },
    { label: "Technology sector", change: 1.2 },
  ]);
});

test("comparison chips cope with missing parts", () => {
  assert.deepEqual(comparisonItems(null), []);
  assert.deepEqual(comparisonItems({ indexes: [], sector: null }), []);
});
