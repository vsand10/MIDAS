/**
 * MIDAS stock data service
 * -------------------------------------------------------------
 * Every screen gets its data ONLY from the functions in this file.
 * Right now they return SAMPLE data (prices are made up).
 *
 * To connect the real API later:
 *   1. Set USE_MOCK_DATA = false
 *   2. Fill in each "TODO (real API)" block with a fetch call
 *   3. Return data in the same shape as the mock version
 * The pages won't need any changes.
 */

const USE_MOCK_DATA = true;
const USE_REAL_SEARCH = true;    // If true, the Search screen will call the real API
const API_BASE = "/api"; // FastAPI backend (proxied by Vite)

// ------------------------------------------------------------------
// Data shapes (what the real API should return)
// ------------------------------------------------------------------
/**
 * @typedef {Object} StockSummary
 * @property {string} symbol          "AAPL"
 * @property {string} name            "Apple Inc."
 * @property {string} sector          "Tech" | "Energy" | "Finance" | "Health" | ...
 * @property {number} price           324.60
 * @property {number} change          -3.21   (dollars, vs previous close)
 * @property {number} changePercent   -0.98   (percent, vs previous close)
 *
 * @typedef {StockSummary & { stats: KeyStats, about: string }} StockDetail
 *
 * @typedef {Object} KeyStats
 * @property {number} marketCap       dollars
 * @property {number} peRatio
 * @property {number} week52Low
 * @property {number} week52High
 * @property {number} avgVolume       shares per day
 * @property {number} eps             earnings per share, dollars
 * @property {number|null} dividendYield  percent, or null if none
 *
 * @typedef {{ time: string, price: number }} PricePoint   time = ISO date string
 *
 * @typedef {Object} TrendingTheme
 * @property {string} theme           "Robotics"
 * @property {string} description
 * @property {StockSummary[]} stocks
 */

export const RANGES = ["1D", "1W", "1M", "3M", "1Y"];
export const SECTORS = ["All", "Tech", "Energy", "Finance", "Health"];

// ------------------------------------------------------------------
// Public functions used by the pages
// ------------------------------------------------------------------

/** S&P 500 card on Home. Returns { name, value, change, changePercent, history: PricePoint[] } */
export async function getMarketIndex(range = "1D") {
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/market/index/SPX?range=${range}`);
  }
  await wait();
  const value = 7638.09;
  return {
    name: "S&P 500",
    symbol: "SPX",
    value,
    change: -30.92,
    changePercent: -0.4,
    history: mockHistory("SPX", range, value, value - (-30.92)),
  };
}

/** "Top Movers Today" on Home. Returns StockSummary[] (biggest % moves first) */
export async function getTopMovers(limit = 4) {
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/market/movers?limit=${limit}`);
  }
  await wait();
  return Object.values(MOCK_STOCKS)
    .map(toSummary)
    .sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent))
    .slice(0, limit);
}

/** Search screen. Returns StockSummary[] matching the text and sector chip */
export async function searchStocks(query = "", sector = "All") {
  if (USE_REAL_SEARCH) {
    // TODO (real API):
    // return getJson(`/stocks/search?q=${encodeURIComponent(query)}&sector=${sector}`);
    const stocks = await getJson(
    `/stocks/search?q=${encodeURIComponent(query)}&sector=${sector}`
  );

  // If there are no results, return an empty list
  if (!stocks.length) {
    return [];
  }

  // Get realtime prices for all search results in one API call
  const symbols = stocks.map((stock) => stock.symbol).join(",");

  const quotes = await getJson(
    `/stocks/quotes?symbols=${encodeURIComponent(symbols)}`
  );

  // Combine company information with realtime price information
  return stocks
  .map((stock) => {
    const quote = quotes.find(
      (q) => q.symbol === stock.symbol
    );

    if (!quote) {
      return null;
    }

    return {
      ...stock,
      price: quote.price,
      change: quote.change,
      changePercent: quote.changePercent,
    };
  })
  .filter(Boolean);
  }
  
  await wait(150);
  const q = query.trim().toLowerCase();
  return Object.values(MOCK_STOCKS)
    .filter((s) => sector === "All" || s.sector === sector)
    .filter(
      (s) => !q || s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
    )
    .map(toSummary);
}

/** "Trending Now" on Search. Returns TrendingTheme[] */
export async function getTrendingThemes() {
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/market/trending`);
  }
  await wait();
  return MOCK_THEMES.map((t) => ({
    ...t,
    stocks: t.symbols.map((sym) => toSummary(MOCK_STOCKS[sym])),
  }));
}

/** Specific Stock screen. Returns StockDetail, or throws NotFoundError */
export async function getStock(symbol) {
  const sym = symbol.toUpperCase();
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/stocks/${sym}`);
  }
  await wait();
  const stock = MOCK_STOCKS[sym];
  if (!stock) throw new NotFoundError(`No stock found for "${sym}"`);
  return structuredClone(stock);
}

/** Price chart. Returns PricePoint[] oldest to newest */
export async function getPriceHistory(symbol, range = "1D") {
  const sym = symbol.toUpperCase();
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/stocks/${sym}/history?range=${range}`);
  }
  await wait(200);
  const stock = MOCK_STOCKS[sym];
  if (!stock) throw new NotFoundError(`No stock found for "${sym}"`);
  return mockHistory(sym, range, stock.price, stock.price - stock.change);
}

// ---------------- Watchlist ----------------
// Mock version keeps the list in memory. The real version will call the
// backend (which stores it in Firestore under the logged-in user).

/** "My Watchlist" on Home. Returns StockSummary[] */
export async function getWatchlist() {
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/watchlist`);
  }
  await wait();
  return mockWatchlist.map((sym) => toSummary(MOCK_STOCKS[sym])).filter(Boolean);
}

export async function isInWatchlist(symbol) {
  if (!USE_MOCK_DATA) {
    // TODO (real API): const list = await getJson(`/watchlist`); return list.some(...)
  }
  await wait(100);
  return mockWatchlist.includes(symbol.toUpperCase());
}

export async function addToWatchlist(symbol) {
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/watchlist`, { method: "POST", body: { symbol } });
  }
  await wait();
  const sym = symbol.toUpperCase();
  if (!mockWatchlist.includes(sym)) mockWatchlist.unshift(sym); // newest first
}

export async function removeFromWatchlist(symbol) {
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/watchlist/${symbol}`, { method: "DELETE" });
  }
  await wait();
  mockWatchlist = mockWatchlist.filter((s) => s !== symbol.toUpperCase());
}

// ---------------- Price alerts ----------------
/**
 * @typedef {Object} Alert
 * @property {string} id
 * @property {string} symbol          "NVDA"
 * @property {string} message         "NVDA crossed $875"
 * @property {"up"|"down"} direction  price moved up through, or dropped below, the level
 * @property {string} time            ISO date string of when it triggered
 * @property {string|null} reason     short "why", e.g. "Earnings catalyst"
 */

/** "Recent Alerts" on the Watchlist screen. Returns Alert[] newest first */
export async function getAlerts(limit = 10) {
  if (!USE_MOCK_DATA) {
    // TODO (real API): return getJson(`/alerts?limit=${limit}`);
  }
  await wait();
  return MOCK_ALERTS.slice(0, limit);
}

// ---------------- Recent searches (kept on this device) ----------------
const RECENT_KEY = "midas_recent_searches";

/** Returns StockSummary[] for the last few stocks the user opened from Search */
export async function getRecentSearches(limit = 10) {
  const symbols = readRecent().slice(0, limit);
  if (!symbols.length) return [];
  if (USE_REAL_SEARCH) {
    // TODO (real API): fetch quotes for these symbols, e.g.
    // return getJson(`/stocks/quotes?symbols=${symbols.join(",")}`);
    const stockInfo = await Promise.all(
      symbols.map(async (symbol) => {
        const matches = await getJson(
          `/stocks/search?q=${encodeURIComponent(symbol)}&sector=All`
        );

        return (
          matches.find(
            (stock) =>
              stock.symbol?.toUpperCase() === symbol.toUpperCase()
          ) || null
        );
      })
    );

    // Get realtime prices and percent changes
    const quotes = await getJson(
      `/stocks/quotes?symbols=${encodeURIComponent(symbols.join(","))}`
    );

    // Combine stock information with realtime quote information
    return stockInfo
      .filter(Boolean)
      .map((stock) => {
        const quote = quotes.find(
          (q) => q.symbol === stock.symbol
        );

        return {
          ...stock,
          price: quote?.price ?? null,
          change: quote?.change ?? null,
          changePercent: quote?.changePercent ?? null,
        };
      });
  }
  await wait(100);
  return symbols.map((s) => MOCK_STOCKS[s]).filter(Boolean).map(toSummary);
}

export function addRecentSearch(symbol) {
  const sym = symbol.toUpperCase();
  const list = [sym, ...readRecent().filter((s) => s !== sym)].slice(0, 10);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch {
    /* storage unavailable (private mode) - recent searches just won't persist */
  }
}

export function clearRecentSearches() {
  try {
    localStorage.removeItem(RECENT_KEY);
  } catch {
    /* ignore */
  }
}

function readRecent() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY)) || [];
  } catch {
    return [];
  }
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
export class NotFoundError extends Error {}

// Used once USE_MOCK_DATA = false. Attach the Firebase login token here, e.g.
//   const token = await auth.currentUser?.getIdToken();
//   headers.Authorization = `Bearer ${token}`;
// eslint-disable-next-line no-unused-vars
async function getJson(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 404) throw new NotFoundError("Not found");
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.status === 204 ? null : res.json();
}

function wait(ms = 300) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function toSummary(s) {
  if (!s) return null;
  const { symbol, name, sector, price, change, changePercent } = s;
  return { symbol, name, sector, price, change, changePercent };
}

// ------------------------------------------------------------------
// MOCK DATA - delete this section once the real API is connected
// (prices and stats are made up for layout purposes)
// ------------------------------------------------------------------
const MOCK_STOCKS = Object.fromEntries(
  [
    ["AAPL", "Apple Inc.", "Tech", 324.6, -3.21, 4.82e12, 38.4, 212.4, 338.9, 54.2e6, 8.45, 0.42,
      "Designs consumer electronics, software and services, including iPhone, Mac, iPad and wearables."],
    ["NVDA", "NVIDIA Corp.", "Tech", 875.4, 31.12, 21.4e12, 52.1, 402.1, 912.3, 41.8e6, 16.8, 0.02,
      "Makes graphics processors and AI computing platforms used in data centers, gaming and cars."],
    ["MSFT", "Microsoft Corp.", "Tech", 512.33, 4.87, 3.81e12, 35.2, 401.2, 530.1, 22.1e6, 14.55, 0.65,
      "Builds software, cloud computing (Azure), productivity tools and gaming platforms."],
    ["TSLA", "Tesla Inc.", "Tech", 421.06, -18.94, 1.35e12, 98.7, 182.0, 488.5, 96.4e6, 4.27, null,
      "Produces electric vehicles, batteries and energy storage, and develops self-driving software."],
    ["AMZN", "Amazon.com Inc.", "Tech", 238.12, 2.05, 2.52e12, 41.6, 161.4, 245.0, 44.7e6, 5.72, null,
      "Runs a global online marketplace and AWS, the largest cloud computing provider."],
    ["GOOGL", "Alphabet Inc.", "Tech", 241.88, 3.4, 2.95e12, 27.3, 150.2, 250.1, 28.3e6, 8.86, 0.34,
      "Parent company of Google Search, YouTube, Android and Google Cloud."],
    ["ISRG", "Intuitive Surgical", "Health", 558.2, 9.81, 0.2e12, 82.4, 380.5, 590.0, 1.6e6, 6.77, null,
      "Makes the da Vinci robotic surgical systems used in minimally invasive surgery."],
    ["XOM", "Exxon Mobil Corp.", "Energy", 118.45, -1.62, 0.51e12, 14.2, 98.6, 126.3, 15.9e6, 8.34, 3.3,
      "One of the world's largest oil and gas companies, also producing chemicals and fuels."],
    ["CVX", "Chevron Corp.", "Energy", 161.3, -0.88, 0.29e12, 15.8, 135.4, 170.2, 8.7e6, 10.21, 4.1,
      "Integrated energy company exploring for, producing and refining oil and natural gas."],
    ["JPM", "JPMorgan Chase & Co.", "Finance", 298.75, 1.97, 0.83e12, 15.1, 202.3, 305.6, 9.2e6, 19.8, 1.9,
      "The largest U.S. bank, offering consumer banking, investment banking and asset management."],
    ["V", "Visa Inc.", "Finance", 352.1, 0.64, 0.68e12, 33.9, 268.0, 360.4, 6.4e6, 10.39, 0.7,
      "Operates one of the world's largest electronic payment networks."],
    ["UNH", "UnitedHealth Group", "Health", 342.5, -5.13, 0.31e12, 18.7, 280.1, 610.0, 10.3e6, 18.3, 2.5,
      "Provides health insurance and healthcare services through UnitedHealthcare and Optum."],
    ["ABBV", "AbbVie Inc.", "Health", 214.9, 2.31, 0.38e12, 61.2, 160.4, 220.8, 6.1e6, 3.51, 3.0,
      "Develops prescription medicines for immunology, cancer and neuroscience."],
  ].map(
    ([symbol, name, sector, price, change, marketCap, peRatio, week52Low, week52High, avgVolume, eps, dividendYield, about]) => [
      symbol,
      {
        symbol,
        name,
        sector,
        price,
        change,
        changePercent: round((change / (price - change)) * 100),
        stats: { marketCap, peRatio, week52Low, week52High, avgVolume, eps, dividendYield },
        about,
      },
    ]
  )
);

const MOCK_THEMES = [
  {
    theme: "Robotics",
    description: "Companies building robots, automation and AI hardware",
    symbols: ["ISRG", "NVDA", "TSLA"],
  },
  {
    theme: "Cloud & AI",
    description: "The biggest names in cloud computing and AI software",
    symbols: ["MSFT", "AMZN", "GOOGL"],
  },
];

let mockWatchlist = ["AMZN", "NVDA", "AAPL", "TSLA", "MSFT"];

const hoursAgo = (h) => new Date(Date.now() - h * 3600e3).toISOString();
const MOCK_ALERTS = [
  {
    id: "a1",
    symbol: "NVDA",
    message: "NVDA crossed $875",
    direction: "up",
    time: hoursAgo(2),
    reason: "Earnings catalyst",
  },
  {
    id: "a2",
    symbol: "AAPL",
    message: "AAPL dropped below $325",
    direction: "down",
    time: hoursAgo(26),
    reason: "Supply chain news",
  },
  {
    id: "a3",
    symbol: "TSLA",
    message: "TSLA fell 4% today",
    direction: "down",
    time: hoursAgo(50),
    reason: null,
  },
];

/**
 * Fake but repeatable price history that ends at the current price.
 * For "1D" it also starts at the previous close, so the chart matches today's change.
 */
function mockHistory(symbol, range, endPrice, previousClose) {
  const points = { "1D": 78, "1W": 35, "1M": 22, "3M": 63, "1Y": 52 }[range] ?? 50;
  const stepMs = {
    "1D": 5 * 60e3,
    "1W": 60 * 60e3 * 4,
    "1M": 86400e3,
    "3M": 86400e3,
    "1Y": 7 * 86400e3,
  }[range] ?? 86400e3;
  const volatility = { "1D": 0.0018, "1W": 0.004, "1M": 0.009, "3M": 0.011, "1Y": 0.022 }[range] ?? 0.01;

  const rand = seededRandom(`${symbol}-${range}`);
  const prices = [endPrice];
  for (let i = 1; i < points; i++) {
    const prev = prices[i - 1];
    prices.push(prev * (1 + (rand() - 0.5) * 2 * volatility));
  }
  prices.reverse();

  if (range === "1D" && previousClose) {
    // Tilt the walk so it starts exactly at the previous close
    const gap = previousClose - prices[0];
    for (let i = 0; i < points; i++) prices[i] += gap * (1 - i / (points - 1));
  }

  const now = Date.now();
  return prices.map((price, i) => ({
    time: new Date(now - (points - 1 - i) * stepMs).toISOString(),
    price: round(price),
  }));
}

function seededRandom(seedText) {
  let seed = [...seedText].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  return () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function round(n) {
  return Math.round(n * 100) / 100;
}