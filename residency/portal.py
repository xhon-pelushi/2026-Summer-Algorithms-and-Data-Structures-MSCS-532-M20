"""Local web portal for the e-commerce backend (stdlib only).

WHAT THIS IS
A single-file HTTP server that puts a browser UI in front of the
ECommerceSystem facade. Every panel on the page maps to exactly one
backend call, and every backend call maps to exactly one data
structure — so the page doubles as a live diagram of the system:

    search box (as you type)   -> search()            trie
    price filter               -> products_in_range() BST
    product table              -> catalog iteration   hash table
    "also bought"              -> recommend_for()     graph
    cart / place / process     -> place_order() +     queue
                                  process_next_order()
    best sellers / low stock / -> best_sellers() etc. heap
    most returned
    returns button             -> process_return()    hash table

No Flask, no JS frameworks: http.server serves one embedded HTML page
plus a small JSON API. This keeps the project's "no third-party
dependencies" claim intact.

THREADING
The server is deliberately SINGLE-THREADED (plain HTTPServer, not
ThreadingHTTPServer). The data structures have no locks — requests are
serialized by the server itself, which is exactly the right trade for a
demo: zero concurrency bugs, throughput irrelevant.

Run from the project folder, then open http://localhost:8000

    python3 portal.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from demo import CATALOG, ORDERS
from ecommerce_system import ECommerceSystem, OutOfStockError

PORT = 8000

# Returns seeded on top of the demo orders so the "most returned"
# dashboard has something to show at first load. Each SKU here was sold
# at least this many times by the ORDERS script (process_return checks).
SEED_RETURNS = ["SKU-1002", "SKU-1002", "SKU-1001", "SKU-1015"]


def build_shop():
    """One ECommerceSystem seeded with the demo catalog, orders, returns.

    Reuses demo.py's data on purpose: the portal shows the same world
    the scripted demo prints, just interactively.
    """
    shop = ECommerceSystem()
    for sku, name, price, stock in CATALOG:
        shop.add_product(sku, name, price, stock)
    for user, skus in ORDERS:
        shop.place_order(user, skus)
    while shop.pending_orders():
        shop.process_next_order()
    for sku in SEED_RETURNS:
        shop.process_return(sku)
    return shop


def product_json(p):
    """Serialize one Product record for the API."""
    return {"sku": p.sku, "name": p.name, "price": p.price,
            "stock": p.stock, "sales": p.sales_count,
            "returns": p.returns_count}


class PortalHandler(BaseHTTPRequestHandler):
    """Routes: GET / for the page, /api/* for JSON."""

    # One shared backend instance for every request (class attribute so
    # each per-request handler object sees the same shop).
    shop = build_shop()

    # ── plumbing ─────────────────────────────────────────────────────

    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status, exc):
        # KeyError str() keeps its quotes; strip for a cleaner message.
        self._send(status, {"error": str(exc).strip("'\"")})

    def _json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    # ── GET: page + read-only queries ────────────────────────────────

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            if url.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif url.path == "/api/products":
                items = sorted(self.shop.catalog, key=lambda p: p.sku)
                self._send(200, [product_json(p) for p in items])
            elif url.path == "/api/search":
                query = q.get("q", [""])[0]
                self._send(200, [product_json(p)
                                 for p in self.shop.search(query)])
            elif url.path == "/api/range":
                low = float(q.get("low", ["0"])[0])
                high = float(q.get("high", ["1e12"])[0])
                self._send(200, [product_json(p)
                                 for p in self.shop.products_in_range(low, high)])
            elif url.path == "/api/recommend":
                sku = q.get("sku", [""])[0]
                self._send(200, {
                    "product": product_json(self.shop.catalog.get(sku)),
                    "also_bought": [
                        {"product": product_json(p), "weight": w}
                        for p, w in self.shop.recommend_for(sku, k=5)],
                })
            elif url.path == "/api/dashboards":
                self._send(200, {
                    "best_sellers": [
                        {"product": product_json(p), "value": v}
                        for p, v in self.shop.best_sellers(5)],
                    "low_stock": [
                        {"product": product_json(p), "value": v}
                        for p, v in self.shop.low_stock(5)],
                    "most_returned": [
                        {"product": product_json(p), "value": v}
                        for p, v in self.shop.most_returned(5)
                        if v > 0],
                })
            elif url.path == "/api/stats":
                cat = self.shop.catalog.stats()
                self._send(200, {
                    "products": cat["size"],
                    "pending_orders": self.shop.pending_orders(),
                    "hash": cat,
                    "trie_nodes": self.shop.search_index.stats()["nodes"],
                    "bst_height": self.shop.price_index.height(),
                    "graph": self.shop.recommendations.stats(),
                })
            else:
                self._send(404, {"error": "not found"})
        except (KeyError, ValueError) as exc:
            self._error(400, exc)

    # ── POST: mutations ──────────────────────────────────────────────

    def do_POST(self):
        try:
            body = self._json_body()
            if self.path == "/api/order":
                order = self.shop.place_order(
                    body.get("user") or "guest", body.get("skus", []))
                self._send(200, {"order_id": order.order_id,
                                 "pending": self.shop.pending_orders()})
            elif self.path == "/api/process":
                order = self.shop.process_next_order()
                self._send(200, {"order_id": order.order_id,
                                 "user": order.user_id,
                                 "skus": order.skus,
                                 "pending": self.shop.pending_orders()})
            elif self.path == "/api/return":
                p = self.shop.process_return(body["sku"])
                self._send(200, product_json(p))
            else:
                self._send(404, {"error": "not found"})
        except OutOfStockError as exc:
            self._error(409, exc)
        except (KeyError, ValueError, IndexError) as exc:
            self._error(400, exc)

    def log_message(self, fmt, *args):
        # One tidy line per request instead of the default noisy format.
        print(f"  {self.command} {self.path} -> {args[1]}")


# ─────────────────────────────────────────────────────────────────────
# The page. Plain string (not an f-string) so CSS/JS braces stay as-is.
# ─────────────────────────────────────────────────────────────────────

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>MSCS-532 Order Platform Portal</title>
<style>
  :root {
    color-scheme: light;
    --surface: #fcfcfb; --panel: #ffffff; --border: #e4e3df;
    --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #8a8984;
    --accent: #2a78d6; --accent-soft: #e3edf9;
    --warn: #b45309; --warn-soft: #fdf0e0;
    --bad: #b3261e; --bad-soft: #fdeceb;
    /* one categorical hue per data structure, used everywhere that
       structure appears: panel band, chip, heading dot, stat tiles */
    --c-trie: #2a78d6;   /* blue    */
    --c-bst: #008300;    /* green   */
    --c-hash: #eb6834;   /* orange  */
    --c-graph: #e87ba4;  /* magenta */
    --c-queue: #1baf7a;  /* aqua    */
    --c-heap: #4a3aa7;   /* violet  */
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --surface: #1a1a19; --panel: #222221; --border: #3a3936;
      --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8a8984;
      --accent: #3987e5; --accent-soft: #24303f;
      --warn: #eda100; --warn-soft: #362a15;
      --bad: #e66767; --bad-soft: #3a2020;
      /* same hues re-stepped for the dark surface */
      --c-trie: #3987e5; --c-bst: #00a000; --c-hash: #d95926;
      --c-graph: #d55181; --c-queue: #199e70; --c-heap: #9085e9;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--surface); color: var(--ink);
    font: 15px/1.45 system-ui, sans-serif;
  }
  header {
    padding: 18px 24px 0;
  }
  header h1 { margin: 0; font-size: 20px; }
  header p { margin: 2px 0 0; color: var(--ink-2); font-size: 13px; }
  /* KPI strip: plain stat tiles, values in ink (never series color) */
  #stats {
    display: flex; flex-wrap: wrap; gap: 10px; padding: 14px 24px;
  }
  .stat {
    background: var(--panel); border: 1px solid var(--border);
    border-top: 3px solid var(--ds, var(--border));
    border-radius: 8px; padding: 8px 14px; min-width: 110px;
  }
  .stat b { display: block; font-size: 18px; }
  .stat span { font-size: 12px; color: var(--ink-2); }
  main {
    display: grid; gap: 14px; padding: 0 24px 24px;
    grid-template-columns: 1fr 1fr;
  }
  @media (max-width: 900px) { main { grid-template-columns: 1fr; } }
  /* each panel carries its structure's hue: --ds is set by the p-*
     class, and the band, tint, dot, chip, and meters all inherit it */
  .p-trie  { --ds: var(--c-trie); }
  .p-bst   { --ds: var(--c-bst); }
  .p-hash  { --ds: var(--c-hash); }
  .p-graph { --ds: var(--c-graph); }
  .p-queue { --ds: var(--c-queue); }
  .p-heap  { --ds: var(--c-heap); }
  section {
    background: color-mix(in srgb, var(--ds, var(--panel)) 4%, var(--panel));
    border: 1px solid var(--border);
    border-top: 4px solid var(--ds, var(--border));
    border-radius: 10px; padding: 14px 16px;
  }
  section.wide { grid-column: 1 / -1; }
  h2 { margin: 0 0 2px; font-size: 15px; }
  h2::before {
    content: ""; display: inline-block; width: 9px; height: 9px;
    border-radius: 3px; background: var(--ds, var(--ink-3));
    margin-right: 7px;
  }
  /* every panel names the data structure answering it; the chip text
     is the hue mixed toward ink so it stays readable on both surfaces */
  .ds {
    float: right; font-size: 11px;
    color: color-mix(in srgb, var(--ds, var(--accent)) 55%, var(--ink));
    background: color-mix(in srgb, var(--ds, var(--accent)) 14%, var(--panel));
    border-radius: 10px; padding: 2px 9px; font-weight: 600;
  }
  .hint { margin: 0 0 10px; font-size: 12px; color: var(--ink-2); }
  input, button {
    font: inherit; border-radius: 7px; border: 1px solid var(--border);
    padding: 6px 10px; background: var(--surface); color: var(--ink);
  }
  input:focus { outline: 2px solid var(--accent); border-color: transparent; }
  button { cursor: pointer; background: var(--panel); }
  button.primary {
    background: var(--accent); border-color: var(--accent); color: #fff;
  }
  button:disabled { opacity: .45; cursor: default; }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
  th, td {
    text-align: left; padding: 5px 8px;
    border-bottom: 1px solid var(--border);
  }
  th { color: var(--ink-2); font-weight: 600; font-size: 12px; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  .badge {
    font-size: 11px; border-radius: 9px; padding: 1px 8px; font-weight: 600;
  }
  .badge.warn { color: var(--warn); background: var(--warn-soft); }
  .badge.bad { color: var(--bad); background: var(--bad-soft); }
  /* dashboard meter: thin single-hue bar, value as visible text */
  .meter-row { display: grid; grid-template-columns: 1fr 46px; gap: 8px;
               align-items: center; padding: 4px 0; }
  .meter-name { font-size: 13px; overflow: hidden; text-overflow: ellipsis;
                white-space: nowrap; }
  .meter-track { grid-column: 1 / -1; display: grid;
                 grid-template-columns: 1fr 46px; gap: 8px;
                 align-items: center; }
  .meter { height: 8px; border-radius: 4px;
           background: var(--ds, var(--accent)); min-width: 4px; }
  .meter-val { font-size: 12px; color: var(--ink-2); text-align: right;
               font-variant-numeric: tabular-nums; }
  #cart-items li { font-size: 13.5px; }
  #cart-items { margin: 6px 0; padding-left: 20px; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
         margin-top: 8px; }
  #log {
    font: 12px/1.5 ui-monospace, monospace; color: var(--ink-2);
    margin-top: 8px; max-height: 96px; overflow-y: auto;
  }
  #log .err { color: var(--bad); }
  .dash-grid { display: grid; gap: 18px;
               grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
  .dash-grid h3 { margin: 0 0 4px; font-size: 13px; }
  .dash-grid p.sub { margin: 0 0 6px; font-size: 11.5px; color: var(--ink-3); }
  /* floating cart button: always-visible feedback for "Add to cart",
     count badge in the queue's color, click scrolls to the cart panel */
  #cart-fab {
    position: fixed; top: 14px; right: 18px; z-index: 50;
    font-size: 20px; line-height: 1; padding: 9px 13px;
    border-radius: 999px; border: 1px solid var(--border);
    background: var(--panel); cursor: pointer;
    box-shadow: 0 2px 8px rgba(0, 0, 0, .10);
  }
  #cart-count {
    position: absolute; top: -7px; right: -7px; min-width: 21px;
    height: 21px; border-radius: 11px; padding: 0 5px;
    background: #0e8a61; color: #fff; font-size: 12.5px;
    font-weight: 700; line-height: 21px; text-align: center;
    display: none;
  }
  #cart-count.show { display: block; }
  #cart-fab.bump { animation: bump .3s ease; }
  @keyframes bump { 30% { transform: scale(1.22); } }
</style>
</head>
<body>
<button id="cart-fab" title="Cart — jump to Cart &amp; fulfilment">
  &#128722;<span id="cart-count">0</span>
</button>

<header>
  <h1>Order Platform Portal</h1>
  <p>MSCS-532 course project &mdash; six from-scratch data structures behind one storefront.
     Each panel is labeled with the structure that answers it.</p>
</header>

<div id="stats"></div>

<main>
  <section class="p-trie">
    <span class="ds">trie</span>
    <h2>Search</h2>
    <p class="hint">Autocomplete as you type &mdash; one prefix walk per word,
       multi-word queries intersect.</p>
    <input id="search-box" placeholder='try "wire", then "wireless key"'
           style="width:100%">
    <table><tbody id="search-results"></tbody></table>
  </section>

  <section class="p-bst">
    <span class="ds">binary search tree</span>
    <h2>Price filter</h2>
    <p class="hint">Pruned in-order range query &mdash; results arrive already
       sorted by price.</p>
    <div class="row">
      $ <input id="price-low" type="number" value="15" style="width:80px">
      to $ <input id="price-high" type="number" value="50" style="width:80px">
      <button id="price-go" class="primary">Filter</button>
    </div>
    <table><tbody id="price-results"></tbody></table>
  </section>

  <section class="wide p-hash">
    <span class="ds">hash table</span>
    <h2>Catalog</h2>
    <p class="hint">The single source of truth: every other panel resolves SKUs
       through this table in O(1). Returns restock here and feed the
       most-returned dashboard.</p>
    <table>
      <thead><tr><th>SKU</th><th>Product</th><th class="num">Price</th>
        <th class="num">Stock</th><th class="num">Sold</th>
        <th class="num">Returned</th><th></th></tr></thead>
      <tbody id="catalog"></tbody>
    </table>
  </section>

  <section class="p-graph">
    <span class="ds">graph</span>
    <h2>Customers also bought</h2>
    <p class="hint">Weighted co-purchase neighbours, strongest first. Click
       &ldquo;also bought&rdquo; on any catalog row.</p>
    <div id="recs"><p class="hint">No product selected yet.</p></div>
  </section>

  <section class="p-queue">
    <span class="ds">queue</span>
    <h2>Cart &amp; fulfilment</h2>
    <p class="hint">Orders queue FIFO at checkout; fulfilment pops the oldest,
       updates stock/sales, and feeds the recommendation graph.</p>
    <ul id="cart-items"></ul>
    <div class="row">
      <input id="cart-user" placeholder="customer name" style="width:150px">
      <button id="place" class="primary">Place order</button>
      <button id="clear-cart">Clear</button>
    </div>
    <div class="row">
      <button id="process">Process next order</button>
      <span id="pending" class="hint"></span>
    </div>
    <div id="log"></div>
  </section>

  <section class="wide p-heap">
    <span class="ds">max-heap</span>
    <h2>Dashboards</h2>
    <p class="hint">Three questions, one structure: O(n) heapify over the
       catalog, then k pops each.</p>
    <div class="dash-grid">
      <div><h3>Best sellers</h3><p class="sub">units sold</p>
        <div id="dash-best"></div></div>
      <div><h3>Low stock</h3><p class="sub">units left (negated-priority
        min-heap trick)</p><div id="dash-low"></div></div>
      <div><h3>Most returned</h3><p class="sub">units returned</p>
        <div id="dash-ret"></div></div>
    </div>
  </section>
</main>

<script>
"use strict";
const $ = id => document.getElementById(id);
const money = v => "$" + v.toFixed(2);
let cart = [];      // SKUs picked from the catalog, in click order

async function api(path, body) {
  const opts = body ? {method: "POST", body: JSON.stringify(body)} : {};
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function log(msg, isErr) {
  const line = document.createElement("div");
  if (isErr) line.className = "err";
  line.textContent = msg;
  $("log").prepend(line);
}

// ── render helpers ───────────────────────────────────────────────────

function productRows(items, tbody) {
  tbody.innerHTML = "";
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="hint">no matches</td></tr>';
    return;
  }
  for (const p of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${p.name}</td><td class="num">${money(p.price)}</td>
                    <td class="num">${p.stock} in stock</td>`;
    tbody.appendChild(tr);
  }
}

function meters(rows, host) {
  host.innerHTML = "";
  if (!rows.length) {
    host.innerHTML = '<p class="hint">nothing yet</p>';
    return;
  }
  const max = Math.max(...rows.map(r => r.value), 1);
  for (const r of rows) {
    const div = document.createElement("div");
    div.className = "meter-row";
    div.innerHTML = `
      <div class="meter-name">${r.product.name}</div><div></div>
      <div class="meter-track">
        <div><div class="meter" style="width:${100 * r.value / max}%"></div></div>
        <div class="meter-val">${r.value}</div>
      </div>`;
    host.appendChild(div);
  }
}

// ── panels ───────────────────────────────────────────────────────────

async function refreshStats() {
  const s = await api("/api/stats");
  // third field ties each tile to its structure's hue (same coding
  // as the panels below)
  const tiles = [
    [s.products, "products", "hash"],
    [s.pending_orders, "pending orders", "queue"],
    [s.hash.load_factor.toFixed(2), "hash load factor", "hash"],
    [s.hash.max_chain, "max chain", "hash"],
    [s.trie_nodes, "trie nodes", "trie"],
    [s.bst_height, "BST height", "bst"],
    [s.graph.edges, "graph edges", "graph"],
  ];
  $("stats").innerHTML = tiles.map(
    ([v, label, ds]) => `<div class="stat" style="--ds:var(--c-${ds})">
       <b>${v}</b><span>${label}</span></div>`
  ).join("");
  $("pending").textContent = s.pending_orders + " order(s) pending";
  $("process").disabled = !s.pending_orders;
}

async function refreshCatalog() {
  const items = await api("/api/products");
  const tbody = $("catalog");
  tbody.innerHTML = "";
  for (const p of items) {
    const tr = document.createElement("tr");
    const stockBadge = p.stock === 0
      ? ' <span class="badge bad">out</span>'
      : p.stock <= 5 ? ' <span class="badge warn">&#9888; low</span>' : "";
    tr.innerHTML = `
      <td>${p.sku}</td><td>${p.name}</td>
      <td class="num">${money(p.price)}</td>
      <td class="num">${p.stock}${stockBadge}</td>
      <td class="num">${p.sales}</td><td class="num">${p.returns}</td>
      <td style="white-space:nowrap">
        <button data-cart="${p.sku}" ${p.stock ? "" : "disabled"}
          title="${p.stock ? `${p.stock} in stock`
                           : "out of stock — restock or process a return"}"
          >Add to cart</button>
        <button data-rec="${p.sku}">Also bought</button>
        <button data-ret="${p.sku}" ${p.sales > p.returns ? "" : "disabled"}
          title="${p.sales > p.returns
                  ? `${p.sales - p.returns} sold unit(s) can come back`
                  : "no sold units left to return"}">Return</button>
      </td>`;
    tbody.appendChild(tr);
  }
}

async function refreshDashboards() {
  const d = await api("/api/dashboards");
  meters(d.best_sellers, $("dash-best"));
  meters(d.low_stock, $("dash-low"));
  meters(d.most_returned, $("dash-ret"));
}

function refreshCart() {
  const ul = $("cart-items");
  ul.innerHTML = cart.length ? "" : '<li class="hint">cart is empty</li>';
  for (const sku of cart) {
    const li = document.createElement("li");
    li.textContent = sku;
    ul.appendChild(li);
  }
  $("place").disabled = !cart.length;
  const badge = $("cart-count");
  badge.textContent = cart.length;
  badge.classList.toggle("show", cart.length > 0);
}

// one call after every mutation keeps every panel consistent with the
// backend — the browser mirrors the "single source of truth" rule
function refreshAll() {
  return Promise.all([refreshStats(), refreshCatalog(), refreshDashboards()]);
}

// ── wiring ───────────────────────────────────────────────────────────

$("search-box").addEventListener("input", async e => {
  const q = e.target.value.trim();
  productRows(q ? await api("/api/search?q=" + encodeURIComponent(q)) : [],
              $("search-results"));
});

$("price-go").addEventListener("click", async () => {
  const low = $("price-low").value || 0, high = $("price-high").value || 1e12;
  productRows(await api(`/api/range?low=${low}&high=${high}`),
              $("price-results"));
});

document.addEventListener("click", async e => {
  const b = e.target.closest("button");
  if (!b) return;
  try {
    if (b.dataset.cart) {
      cart.push(b.dataset.cart);
      refreshCart();
      const fab = $("cart-fab");        // visible feedback up top
      fab.classList.remove("bump");
      void fab.offsetWidth;             // restart the animation
      fab.classList.add("bump");
    } else if (b.dataset.rec) {
      const d = await api("/api/recommend?sku=" + b.dataset.rec);
      $("recs").innerHTML = `<p class="hint">bought with
        <b>${d.product.name}</b>:</p>` + (d.also_bought.length
        ? d.also_bought.map(r => `<div class="meter-row">
            <div class="meter-name">${r.product.name}</div>
            <div class="meter-val">&times;${r.weight}</div></div>`).join("")
        : '<p class="hint">no co-purchases recorded yet</p>');
    } else if (b.dataset.ret) {
      const p = await api("/api/return", {sku: b.dataset.ret});
      log(`return accepted: ${p.name} (stock ${p.stock}, returns ${p.returns})`);
      await refreshAll();
    }
  } catch (err) { log(err.message, true); }
});

$("clear-cart").addEventListener("click", () => { cart = []; refreshCart(); });

$("cart-fab").addEventListener("click", () =>
  document.querySelector(".p-queue")
          .scrollIntoView({behavior: "smooth", block: "center"}));

$("place").addEventListener("click", async () => {
  try {
    const r = await api("/api/order",
                        {user: $("cart-user").value.trim(), skus: cart});
    log(`order #${r.order_id} queued (${cart.length} item(s))`);
    cart = [];
    refreshCart();
    await refreshStats();
  } catch (err) { log(err.message, true); }
});

$("process").addEventListener("click", async () => {
  try {
    const r = await api("/api/process", {});
    log(`order #${r.order_id} fulfilled for ${r.user}: ${r.skus.join(", ")}`);
  } catch (err) { log(err.message, true); }
  await refreshAll();
});

refreshAll();
refreshCart();

// deep links for demos: ?q=... pre-runs a search, ?rec=SKU-... opens
// the recommendation panel, ?cart=SKU-...,SKU-... prefills the cart
const params = new URLSearchParams(location.search);
if (params.get("cart")) {
  cart = params.get("cart").split(",").filter(Boolean);
  refreshCart();
}
if (params.get("q")) {
  $("search-box").value = params.get("q");
  $("search-box").dispatchEvent(new Event("input"));
}
if (params.get("rec")) {
  api("/api/recommend?sku=" + params.get("rec")).then(d => {
    $("recs").innerHTML = `<p class="hint">bought with
      <b>${d.product.name}</b>:</p>` + d.also_bought.map(r =>
      `<div class="meter-row"><div class="meter-name">${r.product.name}</div>
       <div class="meter-val">&times;${r.weight}</div></div>`).join("");
  });
}
</script>
</body>
</html>
"""


def main():
    server = HTTPServer(("127.0.0.1", PORT), PortalHandler)
    print("E-Commerce Portal (stdlib http.server, single-threaded)")
    print(f"  catalog seeded: {len(PortalHandler.shop.catalog)} products, "
          f"{len(ORDERS)} orders fulfilled, {len(SEED_RETURNS)} returns")
    print(f"  serving on http://localhost:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


if __name__ == "__main__":
    main()
