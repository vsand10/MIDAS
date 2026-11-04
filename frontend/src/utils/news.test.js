// Run with: npm test   (uses Node's built-in test runner, nothing to install)
import assert from "node:assert/strict";
import { test } from "node:test";
import { filterArticles } from "./news.js";

const ARTICLES = [
  { id: "1", title: "Apple earnings beat forecasts", summary: "Quarterly results.", source: "Reuters" },
  { id: "2", title: "New chip announced", summary: "Strong earnings outlook for the year.", source: "Bloomberg" },
  { id: "3", title: "Supplier update", summary: "Demand looks steady.", source: "Earnings Daily" },
  { id: "4", title: "Store opens in Tokyo", summary: "", source: "AP" },
];
const ids = (list) => list.map((a) => a.id);

test("matching keyword keeps only matching articles (AC 1)", () => {
  assert.deepEqual(ids(filterArticles(ARTICLES, "earnings")), ["1", "2", "3"]);
});

test("matches headline, summary and source", () => {
  assert.deepEqual(ids(filterArticles(ARTICLES, "tokyo")), ["4"]); // headline
  assert.deepEqual(ids(filterArticles(ARTICLES, "steady")), ["3"]); // summary
  assert.deepEqual(ids(filterArticles(ARTICLES, "bloomberg")), ["2"]); // source
});

test("ignores case and surrounding spaces", () => {
  assert.deepEqual(ids(filterArticles(ARTICLES, "  EARNINGS  ")), ["1", "2", "3"]);
});

test("non-matching keyword gives an empty list (AC 2)", () => {
  assert.deepEqual(filterArticles(ARTICLES, "zzzxyz"), []);
});

test("clearing the search restores the full list (AC 3)", () => {
  assert.equal(filterArticles(ARTICLES, "").length, ARTICLES.length);
  assert.equal(filterArticles(ARTICLES, "   ").length, ARTICLES.length);
  assert.equal(filterArticles(ARTICLES, undefined).length, ARTICLES.length);
});

test("handles missing fields and missing list", () => {
  const sparse = [{ id: "a", title: "Only a title" }, { id: "b", summary: null, source: null, title: "x" }];
  assert.deepEqual(ids(filterArticles(sparse, "title")), ["a"]);
  assert.deepEqual(filterArticles(null, "x"), []);
  assert.deepEqual(filterArticles(undefined, ""), []);
});

test("does not change the original list", () => {
  const copy = [...ARTICLES];
  filterArticles(ARTICLES, "earnings");
  assert.deepEqual(ARTICLES, copy);
});
