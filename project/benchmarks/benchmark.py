"""Phase 3 benchmark suite: optimized structures vs naive baselines.

METHODOLOGY
Every experiment follows the same discipline used throughout the course
assignments:
  - wall-clock timing with time.perf_counter (the highest-resolution
    monotonic clock Python exposes);
  - BEST of 5 repeats per measurement — the best run has the least
    OS/GC interference, so it approximates the operation's true cost;
  - memory via tracemalloc (Python-level allocations, peak);
  - identical, seeded datasets for every configuration compared, so
    the only variable is the data structure under test.

Six experiments, all writing results to benchmark_data.json:

  1. catalog   : hash lookups — dynamic resizing vs fixed 1,024 buckets
  2. search    : name prefix search — trie walk vs linear scan
  3. top_k     : top-10 best sellers — heapify+pops vs full sort
  4. range     : price range query — pruned BST traversal vs linear scan
  5. pipeline  : end-to-end order throughput and per-structure memory
                 (tracemalloc) at increasing catalog sizes
  6. bst_shape : BST height/query on random vs monotone (sorted) insert

Run from the project folder:  python3 benchmarks/benchmark.py
"""

import json
import os
import random
import sys
import time
import tracemalloc

# The benchmark lives one level below the project root; make the
# project importable no matter where the interpreter was launched from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_structures import (
    PriceIndex, Product, ProductCatalog, SearchTrie, TopKHeap,
)
from ecommerce_system import ECommerceSystem, OutOfStockError
from benchmarks.generate_dataset import make_products, make_orders

# Catalog sizes: two orders of magnitude, enough to expose growth
# curves without hour-long runs.
SIZES = [1_000, 10_000, 50_000, 100_000]
REPEATS = 5
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "benchmark_data.json")


def timed(fn, repeats=REPEATS):
    """Best-of-repeats wall time for fn(), in seconds.

    Best (not mean) because timing noise is strictly additive — GC
    pauses and scheduler preemption only ever make a run SLOWER, so the
    fastest observation is the closest to the operation's true cost.
    """
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def bench_catalog():
    """Experiment 1 — what is load-factor resizing worth?

    The SAME hash table class is built twice over identical data: once
    with resizing enabled (the optimization) and once frozen at 1,024
    buckets (the naive baseline). 10,000 random successful lookups are
    then timed. With resizing, chains stay O(1) and lookups flat; fixed
    capacity forces chains to grow as n/1024, and lookups with them.
    max_chain is recorded as the visible mechanism of the slowdown.
    """
    rng = random.Random(3)
    results = {"resizing": {}, "fixed": {}, "max_chain": {}}
    for n in SIZES:
        products = make_products(n)
        # Same lookup workload for both configurations (fair comparison).
        lookups = [rng.choice(products)[0] for _ in range(10_000)]
        for label, kwargs in [
            ("resizing", {}),
            ("fixed", {"initial_capacity": 1024, "resize_enabled": False}),
        ]:
            catalog = ProductCatalog(**kwargs)
            for sku, name, price, stock in products:
                catalog.put(Product(sku, name, price, stock))
            total = timed(lambda: [catalog.get(sku) for sku in lookups])
            results[label][n] = total / len(lookups)  # per-lookup seconds
            if label == "fixed":
                results["max_chain"][n] = catalog.stats()["max_chain"]
    return results


def bench_search():
    """Experiment 2 — trie prefix walk vs linear scan.

    The baseline mimics what a store without a trie would do: scan
    every product name and keep those with a word starting with the
    query. Both approaches answer the same 200 queries over identical
    catalogs. Expectation: the scan grows linearly with n; the trie's
    cost tracks only prefix length + result count.
    """
    rng = random.Random(4)
    results = {"trie": {}, "linear": {}}
    # Query mix: short prefixes with many matches ("ba", "sl") and
    # longer, more selective ones ("recha", "mech").
    prefixes = ["wir", "port", "smart", "ultra", "mech", "recha", "ba", "sl"]
    queries = [rng.choice(prefixes) for _ in range(200)]
    for n in SIZES:
        products = make_products(n)
        trie = SearchTrie()
        for sku, name, _, _ in products:
            trie.insert(name, sku)
        # Pre-lowered name list so the baseline pays no case-folding
        # cost inside the timed loop (be fair to the baseline).
        names = [(name.lower(), sku) for sku, name, _, _ in products]

        def linear_scan():
            for q in queries:
                [sku for name, sku in names
                 if any(w.startswith(q) for w in name.split())]

        def trie_walk():
            for q in queries:
                trie.prefix_search(q)

        results["trie"][n] = timed(trie_walk) / len(queries)
        results["linear"][n] = timed(linear_scan) / len(queries)
    return results


def bench_top_k():
    """Experiment 3 — heap top-10 vs full sort (the honest one).

    Asymptotically the heap should win: O(n + k log n) vs O(n log n).
    In practice Python's sorted() runs Timsort in C while our sift-down
    comparisons run in the interpreter — this experiment measures
    whether the asymptotic advantage survives those constant factors.
    (Spoiler, discussed in the reports: it ties, and that finding is
    part of the analysis.)
    """
    rng = random.Random(5)
    results = {"heap": {}, "sort": {}}
    for n in SIZES:
        counts = [(rng.randrange(1000), f"SKU-{i}") for i in range(n)]
        results["heap"][n] = timed(
            lambda: TopKHeap(counts).top_k(10))
        results["sort"][n] = timed(
            lambda: sorted(counts, reverse=True)[:10])
    return results


def bench_range():
    """Experiment 4 — pruned BST range query vs linear scan.

    The $100-$125 window covers ~5% of the uniform $1-$500 price range,
    so ~95% of the catalog is OUTSIDE the band — exactly the work the
    BST's pruning skips and the scan cannot. The baseline also sorts
    its hits, because the BST returns sorted results and the comparison
    must produce equivalent output.
    """
    results = {"bst": {}, "linear": {}, "hits": {}}
    for n in SIZES:
        products = make_products(n)
        index = PriceIndex()
        for sku, _, price, _ in products:
            index.insert(price, sku)
        pairs = [(price, sku) for sku, _, price, _ in products]
        low, high = 100.0, 125.0  # ~5% of the 1-500 uniform price range

        results["bst"][n] = timed(lambda: index.range_query(low, high))
        results["linear"][n] = timed(
            lambda: sorted((p, s) for p, s in pairs if low <= p <= high))
        results["hits"][n] = len(index.range_query(low, high))
    return results


def bench_pipeline():
    """Experiment 5 — the whole system, end to end.

    Builds the full ECommerceSystem at each catalog size (tracemalloc
    captures the peak memory of the build), then pushes 20,000 orders
    through place_order + process_next_order and reports throughput.
    Failed (out-of-stock) orders are counted, not hidden: at n=1,000
    the skewed demand deliberately exhausts popular products, which is
    the flash-sale stress test discussed in the reports.
    """
    results = {"orders_per_sec": {}, "build_sec": {}, "memory_mb": {}}
    n_orders = 20_000
    for n in SIZES:
        products = make_products(n)
        orders = make_orders(products, n_orders)

        # Measure the build (all six structures populated) with
        # tracemalloc running to capture peak allocation.
        tracemalloc.start()
        shop = ECommerceSystem()
        start = time.perf_counter()
        for sku, name, price, stock in products:
            shop.add_product(sku, name, price, stock)
        results["build_sec"][n] = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results["memory_mb"][n] = peak / 1024 / 1024

        # Throughput: one place+process cycle per order, timed as a
        # whole (this is what "orders per second" means end to end).
        start = time.perf_counter()
        fulfilled = failed = 0
        for user, skus in orders:
            shop.place_order(user, skus)
            try:
                shop.process_next_order()
                fulfilled += 1
            except OutOfStockError:
                failed += 1
        elapsed = time.perf_counter() - start
        results["orders_per_sec"][n] = n_orders / elapsed
        results.setdefault("fulfilled", {})[n] = fulfilled
        results.setdefault("failed", {})[n] = failed
        results.setdefault("graph_edges", {})[n] = (
            shop.recommendations.stats()["edges"])
    return results


def bench_bst_shape():
    """Experiment 6 — the BST's documented worst case, on purpose.

    The same prices are inserted twice: shuffled (expected height
    ~2 log2 n) and strictly ascending (degenerate height = n, a linked
    list down the right spine). Build time and range-query time are
    recorded for both shapes. Sizes are kept small because the sorted
    build is O(n^2) total — which is precisely the point being shown.
    """
    results = {}
    for n in [1_000, 2_000, 4_000]:
        prices = [round(1 + i * 0.01, 2) for i in range(n)]  # ascending
        shuffled = prices[:]
        random.Random(6).shuffle(shuffled)

        random_index, sorted_index = PriceIndex(), PriceIndex()
        for i, price in enumerate(shuffled):
            random_index.insert(price, f"S{i}")
        start = time.perf_counter()
        for i, price in enumerate(prices):
            sorted_index.insert(price, f"S{i}")  # each walks the spine
        sorted_build = time.perf_counter() - start

        results[n] = {
            "random_height": random_index.height(),
            "sorted_height": sorted_index.height(),
            "sorted_build_sec": sorted_build,
            "random_query_sec": timed(
                lambda: random_index.range_query(5, 10)),
            "sorted_query_sec": timed(
                lambda: sorted_index.range_query(5, 10)),
        }
    return results


def main():
    """Run all six experiments and write benchmark_data.json.

    The JSON is the single source for every chart and every number in
    the Deliverable 3 and final reports — figures are generated from
    this file, never typed by hand.
    """
    data = {}
    for name, fn in [
        ("catalog", bench_catalog),
        ("search", bench_search),
        ("top_k", bench_top_k),
        ("range", bench_range),
        ("pipeline", bench_pipeline),
        ("bst_shape", bench_bst_shape),
    ]:
        print(f"running {name} ...", flush=True)
        start = time.perf_counter()
        data[name] = fn()
        print(f"  done in {time.perf_counter() - start:.1f}s", flush=True)
    data["sizes"] = SIZES
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
