"""Unit tests for the six core data structures and the integration facade.

TESTING PHILOSOPHY
Each structure's tests target its SPECIFIC failure modes, not just the
happy path:
  - the hash table is grown through multiple resizes and every record
    re-verified (a resize that loses or misplaces records is the classic
    hash-table bug);
  - the circular queue is drained across its wraparound boundary (the
    modulo arithmetic is exactly where off-by-one errors hide);
  - the BST range query is cross-checked against a brute-force scan on
    random data (property-based confidence, not hand-picked examples);
  - the heap's top-k is compared against a full sort (the sort is the
    trivially correct oracle);
  - the facade's tests verify ATOMICITY: a failed order must leave every
    other line item's stock untouched.

Run from the project folder:  python3 -m unittest discover -s tests -v
"""

import os
import random
import sys
import unittest

# Make the project root importable when tests run from the tests/ dir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_structures import (
    Order,
    OrderQueue,
    PriceIndex,
    Product,
    ProductCatalog,
    RecommendationGraph,
    SearchTrie,
    TopKHeap,
)
from ecommerce_system import ECommerceSystem, OutOfStockError


class TestProductCatalog(unittest.TestCase):
    """Hash table: chaining, resizing, updates, and error paths."""

    def test_put_get_roundtrip(self):
        """The most basic contract: what goes in comes back out."""
        catalog = ProductCatalog()
        catalog.put(Product("SKU-1", "Mouse", 9.99, 5))
        self.assertEqual(catalog.get("SKU-1").name, "Mouse")
        self.assertEqual(len(catalog), 1)

    def test_get_missing_sku_raises(self):
        """Unknown SKUs must raise, not return None silently."""
        with self.assertRaises(KeyError):
            ProductCatalog().get("SKU-404")

    def test_put_same_sku_updates_in_place(self):
        """Re-putting a SKU is an update: size must NOT grow."""
        catalog = ProductCatalog()
        catalog.put(Product("SKU-1", "Mouse", 9.99, 5))
        catalog.put(Product("SKU-1", "Better Mouse", 19.99, 3))
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog.get("SKU-1").name, "Better Mouse")

    def test_remove(self):
        """Remove returns the record; removing twice is an error."""
        catalog = ProductCatalog()
        catalog.put(Product("SKU-1", "Mouse", 9.99, 5))
        removed = catalog.remove("SKU-1")
        self.assertEqual(removed.sku, "SKU-1")
        self.assertEqual(len(catalog), 0)
        with self.assertRaises(KeyError):
            catalog.remove("SKU-1")

    def test_resize_keeps_all_records(self):
        """Grow from 4 buckets through many doublings; nothing may be
        lost or misfiled, and the load factor must end below MAX_LOAD."""
        catalog = ProductCatalog(initial_capacity=4)
        for i in range(500):
            catalog.put(Product(f"SKU-{i}", f"Item {i}", float(i), i))
        self.assertEqual(len(catalog), 500)
        for i in range(500):  # every single record must still resolve
            self.assertEqual(catalog.get(f"SKU-{i}").price, float(i))
        self.assertLessEqual(catalog.stats()["load_factor"],
                             ProductCatalog.MAX_LOAD)

    def test_disabled_resize_grows_chains(self):
        """The benchmark configuration: capacity frozen, chains grow.
        This asserts the degradation the Phase 3 charts measure."""
        catalog = ProductCatalog(initial_capacity=4, resize_enabled=False)
        for i in range(100):
            catalog.put(Product(f"SKU-{i}", f"Item {i}", 1.0, 1))
        self.assertEqual(catalog.stats()["capacity"], 4)  # never resized
        self.assertGreater(catalog.stats()["max_chain"], 10)

    def test_negative_price_rejected(self):
        """Boundary validation lives in Product itself."""
        with self.assertRaises(ValueError):
            Product("SKU-1", "Broken", -1.0, 5)


class TestSearchTrie(unittest.TestCase):
    """Trie: word indexing, case folding, limits, and removal."""

    def setUp(self):
        # Three products whose names share prefixes on purpose:
        # "wire" is a prefix of both "wired" and "wireless".
        self.trie = SearchTrie()
        self.trie.insert("Wireless Mouse", "SKU-1")
        self.trie.insert("Wireless Keyboard", "SKU-2")
        self.trie.insert("Wired Mouse", "SKU-3")

    def test_prefix_matches_multiple_words(self):
        """A short prefix matches everything below it; a longer prefix
        narrows the subtree ('wirel' excludes 'wired')."""
        self.assertEqual(set(self.trie.prefix_search("wire")),
                         {"SKU-1", "SKU-2", "SKU-3"})
        self.assertEqual(set(self.trie.prefix_search("wirel")),
                         {"SKU-1", "SKU-2"})

    def test_search_is_case_insensitive(self):
        """Queries are lowercased on the way in."""
        self.assertEqual(set(self.trie.prefix_search("WIRELESS")),
                         {"SKU-1", "SKU-2"})

    def test_second_word_is_indexed(self):
        """Every word of a name is indexed, so 'mou' finds both mice."""
        self.assertEqual(set(self.trie.prefix_search("mou")),
                         {"SKU-1", "SKU-3"})

    def test_no_match_returns_empty(self):
        """Dead-end prefixes and empty queries return [] (not errors)."""
        self.assertEqual(self.trie.prefix_search("zzz"), [])
        self.assertEqual(self.trie.prefix_search(""), [])

    def test_limit_caps_results(self):
        """The autocomplete early-exit: stop once `limit` SKUs found."""
        self.assertEqual(len(self.trie.prefix_search("wire", limit=2)), 2)

    def test_remove_unindexes_sku(self):
        """Removal must clear ONLY the removed SKU; siblings survive."""
        self.trie.remove("Wireless Mouse", "SKU-1")
        self.assertNotIn("SKU-1", self.trie.prefix_search("wireless"))
        self.assertIn("SKU-2", self.trie.prefix_search("wireless"))

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            self.trie.insert("", "SKU-9")


class TestPriceIndex(unittest.TestCase):
    """BST: ordered range queries, duplicates, and a brute-force oracle."""

    def setUp(self):
        # Mixed insertion order (not sorted!) so the tree is bushy.
        # Two SKUs share price 24.99 to exercise the shared-node case.
        self.index = PriceIndex()
        for price, sku in [(24.99, "A"), (49.99, "B"), (12.99, "C"),
                           (9.99, "D"), (24.99, "E"), (89.99, "F")]:
            self.index.insert(price, sku)

    def test_range_query_inclusive_and_sorted(self):
        """Both endpoints are inclusive and results ascend by price."""
        self.assertEqual(self.index.range_query(12.99, 49.99),
                         ["C", "A", "E", "B"])

    def test_duplicate_prices_share_a_node(self):
        """A point query (low == high) returns every SKU at that price."""
        self.assertEqual(self.index.range_query(24.99, 24.99), ["A", "E"])

    def test_empty_range_and_no_hits(self):
        """A band above all prices, and a query on an empty tree."""
        self.assertEqual(self.index.range_query(100, 200), [])
        self.assertEqual(PriceIndex().range_query(0, 100), [])

    def test_invalid_range_raises(self):
        """low > high is a caller bug, rejected at the boundary."""
        with self.assertRaises(ValueError):
            self.index.range_query(50, 10)

    def test_discard(self):
        """Discard removes one SKU; discarding an absent SKU is a no-op."""
        self.index.discard(24.99, "A")
        self.assertEqual(self.index.range_query(24.99, 24.99), ["E"])
        self.index.discard(24.99, "ghost")  # absent SKU is a no-op
        self.assertEqual(len(self.index), 5)

    def test_matches_brute_force_on_random_data(self):
        """The oracle test: on 1,000 random prices, the pruned tree
        traversal must agree exactly with a filter-and-sort scan. If the
        pruning rules were even slightly wrong, this would catch it."""
        random.seed(42)
        index = PriceIndex()
        pairs = [(round(random.uniform(1, 500), 2), f"S{i}")
                 for i in range(1000)]
        for price, sku in pairs:
            index.insert(price, sku)
        expected = sorted((p, s) for p, s in pairs if 100 <= p <= 200)
        self.assertEqual(index.range_query(100, 200),
                         [s for _, s in expected])


class TestRecommendationGraph(unittest.TestCase):
    """Graph: weighted edges, ranking, and degenerate inputs."""

    def test_record_order_builds_weighted_edges(self):
        """Two orders containing (A, B) must give edge weight 2, ranking
        B above the once-co-purchased C."""
        graph = RecommendationGraph()
        graph.record_order(["A", "B"])
        graph.record_order(["A", "B", "C"])
        top = graph.also_bought("A", k=2)
        self.assertEqual(top[0], ("B", 2))
        self.assertEqual(top[1], ("C", 1))

    def test_unknown_sku_has_no_recommendations(self):
        """A product never ordered returns [] — not an error."""
        self.assertEqual(RecommendationGraph().also_bought("ghost"), [])

    def test_self_loops_and_duplicates_ignored(self):
        """Buying two of the same item is not a co-purchase: the order
        [A, A, B] must create only the A-B edge."""
        graph = RecommendationGraph()
        graph.record_order(["A", "A", "B"])
        self.assertEqual(graph.degree("A"), 1)
        self.assertEqual(graph.also_bought("A"), [("B", 1)])

    def test_invalid_k_raises(self):
        with self.assertRaises(ValueError):
            RecommendationGraph().also_bought("A", k=0)


class TestTopKHeap(unittest.TestCase):
    """Heap: ordering, heapify correctness, and non-destructive top-k."""

    def test_pops_in_priority_order(self):
        """Pushed in scrambled order, popped in strictly descending
        priority — the heap property end to end."""
        heap = TopKHeap()
        for priority in [5, 1, 9, 3, 7]:
            heap.push(priority, f"item{priority}")
        self.assertEqual([heap.pop()[0] for _ in range(5)], [9, 7, 5, 3, 1])

    def test_heapify_matches_sorted(self):
        """The oracle test: bottom-up heapify + top_k(25) on 2,000
        random entries must equal what a full descending sort says."""
        random.seed(7)
        entries = [(random.randrange(10000), i) for i in range(2000)]
        heap = TopKHeap(entries)
        expected = sorted(entries, reverse=True)[:25]
        self.assertEqual(heap.top_k(25), expected)

    def test_top_k_is_non_destructive(self):
        """A dashboard query must not consume the live heap."""
        heap = TopKHeap([(1, "a"), (2, "b")])
        heap.top_k(2)
        self.assertEqual(len(heap), 2)          # nothing was removed
        self.assertEqual(heap.peek(), (2, "b"))  # max still on top

    def test_empty_heap_errors(self):
        with self.assertRaises(IndexError):
            TopKHeap().pop()
        with self.assertRaises(IndexError):
            TopKHeap().peek()


class TestOrderQueue(unittest.TestCase):
    """Circular buffer: FIFO order, growth, and wraparound."""

    def test_fifo_order_preserved_across_growth(self):
        """Start at capacity 2 and force several doublings; the 50
        orders must still come out in exactly the order they went in."""
        queue = OrderQueue(initial_capacity=2)
        for i in range(50):
            queue.enqueue(Order(i, "u", ["SKU-1"]))
        self.assertEqual([queue.dequeue().order_id for _ in range(50)],
                         list(range(50)))

    def test_wraparound_reuse(self):
        """The modulo case: dequeue two, then enqueue three so the tail
        wraps past the end of the array into the freed slots. FIFO
        order must survive the wrap."""
        queue = OrderQueue(initial_capacity=4)
        for i in range(3):
            queue.enqueue(Order(i, "u", ["S"]))
        queue.dequeue()
        queue.dequeue()
        for i in range(3, 6):
            queue.enqueue(Order(i, "u", ["S"]))
        self.assertEqual([queue.dequeue().order_id for _ in range(4)],
                         [2, 3, 4, 5])

    def test_empty_queue_errors(self):
        queue = OrderQueue()
        with self.assertRaises(IndexError):
            queue.dequeue()
        with self.assertRaises(IndexError):
            queue.peek()

    def test_empty_order_rejected(self):
        """An order with no items is invalid at construction time."""
        with self.assertRaises(ValueError):
            Order(1, "u", [])


class TestECommerceSystem(unittest.TestCase):
    """Facade: the structures working together, including atomicity."""

    def setUp(self):
        # SKU-1 gets stock 2 on purpose: the atomicity test below needs
        # a product that runs out on the third order.
        self.shop = ECommerceSystem()
        self.shop.add_product("SKU-1", "Wireless Mouse", 24.99, 2)
        self.shop.add_product("SKU-2", "Wireless Keyboard", 49.99, 5)
        self.shop.add_product("SKU-3", "USB Cable", 9.99, 10)

    def test_duplicate_sku_rejected(self):
        with self.assertRaises(ValueError):
            self.shop.add_product("SKU-1", "Clone", 1.0, 1)

    def test_order_flow_updates_stock_sales_and_graph(self):
        """One order through the whole pipeline: stock down, sales up,
        and the co-purchase edge immediately visible in recommend_for."""
        self.shop.place_order("alice", ["SKU-1", "SKU-2"])
        order = self.shop.process_next_order()
        self.assertEqual(order.status, "fulfilled")
        self.assertEqual(self.shop.catalog.get("SKU-1").stock, 1)
        self.assertEqual(self.shop.catalog.get("SKU-1").sales_count, 1)
        recs = self.shop.recommend_for("SKU-1")
        self.assertEqual(recs[0][0].sku, "SKU-2")

    def test_out_of_stock_order_fails_atomically(self):
        """The atomicity guarantee: order c fails on SKU-1 (stock
        exhausted by a and b), and SKU-3 — also in order c — must be
        completely untouched by the failed attempt."""
        self.shop.place_order("a", ["SKU-1"])
        self.shop.place_order("b", ["SKU-1"])
        self.shop.place_order("c", ["SKU-1", "SKU-3"])
        self.shop.process_next_order()
        self.shop.process_next_order()
        with self.assertRaises(OutOfStockError):
            self.shop.process_next_order()
        # SKU-3 stock untouched by the failed order
        self.assertEqual(self.shop.catalog.get("SKU-3").stock, 10)

    def test_order_with_unknown_sku_rejected_at_checkout(self):
        """Validation happens at place_order, before queueing."""
        with self.assertRaises(KeyError):
            self.shop.place_order("alice", ["SKU-404"])

    def test_multi_word_search_intersects_prefixes(self):
        """'wireless key' must match ONLY the keyboard (intersection),
        an impossible word must kill the whole query, and a blank
        query must return nothing."""
        matches = [p.name for p in self.shop.search("wireless key")]
        self.assertEqual(matches, ["Wireless Keyboard"])
        self.assertEqual(self.shop.search("wireless zzz"), [])
        self.assertEqual(self.shop.search("   "), [])

    def test_search_and_range_resolve_through_catalog(self):
        """Both query paths must return full Product records (resolved
        through the catalog), not bare SKUs."""
        names = {p.name for p in self.shop.search("wireless")}
        self.assertEqual(names, {"Wireless Mouse", "Wireless Keyboard"})
        in_range = [p.sku for p in self.shop.products_in_range(9, 25)]
        self.assertEqual(in_range, ["SKU-3", "SKU-1"])

    def test_remove_product_clears_all_indexes(self):
        """remove_product must clean EVERY structure that knew the SKU —
        a stale index entry would resolve to a KeyError later."""
        self.shop.remove_product("SKU-1")
        self.assertNotIn("SKU-1",
                         [p.sku for p in self.shop.search("wireless")])
        self.assertNotIn("SKU-1",
                         [p.sku for p in self.shop.products_in_range(0, 100)])

    def test_dashboards(self):
        """Best sellers ranked by fulfilled sales; low stock surfaces
        the product with the fewest units (SKU-1, seeded with 2)."""
        self.shop.place_order("a", ["SKU-3"])
        self.shop.place_order("b", ["SKU-3"])
        self.shop.place_order("c", ["SKU-2"])
        for _ in range(3):
            self.shop.process_next_order()
        best = self.shop.best_sellers(2)
        self.assertEqual(best[0][0].sku, "SKU-3")
        self.assertEqual(best[0][1], 2)
        low = self.shop.low_stock(1)
        self.assertEqual(low[0][0].sku, "SKU-1")  # stock 2 is the lowest

    def test_return_restocks_and_ranks_most_returned(self):
        """A return puts the unit back in stock, increments the returns
        counter (leaving sales_count alone — demand and dissatisfaction
        are separate signals), and drives the most_returned ranking."""
        self.shop.place_order("a", ["SKU-2", "SKU-3"])
        self.shop.place_order("b", ["SKU-2"])
        self.shop.process_next_order()
        self.shop.process_next_order()
        self.shop.process_return("SKU-2")
        self.shop.process_return("SKU-2")
        product = self.shop.catalog.get("SKU-2")
        self.assertEqual(product.stock, 5)         # 5 - 2 sold + 2 back
        self.assertEqual(product.returns_count, 2)
        self.assertEqual(product.sales_count, 2)   # unchanged by returns
        top = self.shop.most_returned(2)
        self.assertEqual(top[0][0].sku, "SKU-2")
        self.assertEqual(top[0][1], 2)

    def test_return_of_never_sold_or_excess_rejected(self):
        """Returns are capped by units actually sold — cumulatively, so
        the same unit can never be returned twice — and a product that
        never sold cannot be returned at all."""
        with self.assertRaises(ValueError):
            self.shop.process_return("SKU-1")      # zero sold so far
        self.shop.place_order("a", ["SKU-1"])
        self.shop.process_next_order()
        with self.assertRaises(ValueError):
            self.shop.process_return("SKU-1", quantity=2)  # only 1 sold
        self.shop.process_return("SKU-1")          # the one sold unit
        with self.assertRaises(ValueError):
            self.shop.process_return("SKU-1")      # already came back
        with self.assertRaises(KeyError):
            self.shop.process_return("SKU-404")    # unknown SKU


if __name__ == "__main__":
    unittest.main()
