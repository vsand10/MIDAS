/**
 * Keeps the articles whose headline, summary or source contains the search text.
 * Ignores upper/lower case and spaces around the text. An empty search returns
 * every article, which is how clearing the search box restores the full list.
 */
export function filterArticles(articles, query) {
  const list = articles ?? [];
  const q = (query ?? "").trim().toLowerCase();
  if (!q) return list;
  return list.filter((a) =>
    [a.title, a.summary, a.source].some((text) => text?.toLowerCase().includes(q))
  );
}
