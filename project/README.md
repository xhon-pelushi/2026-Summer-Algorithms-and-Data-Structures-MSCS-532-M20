# Course Project — E-Commerce Order Platform Backend

**MSCS-532 — Algorithms and Data Structures**
Developing and Optimizing Data Structures for Real-World Applications Using Python.

Six data structures, implemented from scratch, power one integrated e-commerce
backend covering the full customer journey: search → price filter →
recommendations → order → fulfilment → dashboards.

| Subsystem | Structure | File |
|-----------|-----------|------|
| Product catalog (SKU lookup) | Hash table (chaining, FNV-1a, dynamic resizing) | `data_structures/product_catalog.py` |
| Search / autocomplete | Trie (prefix tree) | `data_structures/search_trie.py` |
| Price range queries | Binary search tree | `data_structures/price_index.py` |
| "Customers also bought" | Weighted co-purchase graph (adjacency list) | `data_structures/recommendation_graph.py` |
| Best sellers / low stock | Binary max-heap | `data_structures/top_k_heap.py` |
| Order fulfilment pipeline | Circular-buffer FIFO queue | `data_structures/order_queue.py` |

The catalog hash table is the single source of truth: every other structure
stores only SKUs and resolves them through the catalog in O(1).

A browser portal (`portal.py`, stdlib `http.server` — still zero dependencies)
puts a live UI over the facade: every panel is labeled and color-coded by the
data structure that answers it (see `PORTAL_GUIDE.md` for a panel-by-panel
walkthrough with screenshots). It also exercises the returns workflow — `process_return()`
restocks through the catalog and a "most returned" dashboard reuses the same
max-heap as best sellers.

## Layout

```
project/
├── ecommerce_system.py        # facade wiring the six structures together
├── demo.py                    # scripted end-to-end customer journey
├── portal.py                  # local web portal over the facade (stdlib)
├── data_structures/           # the six from-scratch implementations
├── tests/                     # 42 unit tests (unittest)
├── benchmarks/                # Phase 3 dataset generator + benchmark suite
├── charts/                    # benchmark charts used in the reports
├── screenshots/               # demo / test / benchmark terminal output
└── deliverables/              # one folder per deliverable
    ├── Deliverable 1/         #   design report
    ├── Deliverable 2/         #   proof-of-concept report
    ├── Deliverable 3/         #   optimization & scaling report
    └── Deliverable 4/         #   final report, presentation, script
```

## Running

```bash
python3 demo.py                            # end-to-end demonstration
python3 portal.py                          # web portal on http://localhost:8000
python3 -m unittest discover -s tests      # unit tests (42 tests)
python3 benchmarks/benchmark.py            # full benchmark suite (~3 min)
```

No third-party dependencies; Python 3.10+.

## Benchmark highlights (100,000-product catalog)

- Hash table lookups stay ~2 µs with dynamic resizing vs 10 µs when
  capacity is fixed (max chain length 111).
- Trie prefix search answers in ~1.8 ms vs ~82 ms for a linear scan (45×).
- Pruned BST range query beats a full scan 5.7× for a ~5% price window.
- The integrated pipeline fulfils ~44,000 orders/second end-to-end while
  the whole system fits in ~65 MB.
