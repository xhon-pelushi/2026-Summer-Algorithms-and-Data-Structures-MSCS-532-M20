"""Integration layer: one e-commerce backend wired from six data structures.

THE FACADE PATTERN
This class is the only thing the rest of an application would ever
touch. Its public methods are BUSINESS ACTIONS (add a product, place an
order, search), not data-structure calls — each action fans out to the
right combination of underlying structures and keeps them consistent.

THE ONE INTEGRATION RULE
The catalog hash table OWNS the product records. Every other structure
stores only SKU strings and resolves them back through the catalog in
O(1) at query time:

    add_product        -> catalog + trie + price index    (three writes)
    search             -> trie, then catalog              (resolve)
    products_in_range  -> price BST, then catalog         (resolve)
    place_order        -> order queue                     (validated first)
    process_next_order -> catalog (stock/sales) + graph   (side effects)
    recommend_for      -> graph, then catalog             (resolve)
    process_return     -> catalog (stock/returns)         (one write)
    best_sellers/low_stock/most_returned -> heap over catalog, resolve

Because data lives in exactly one place, the indexes can never disagree
with each other — removing a product from the catalog and its indexes
in one method keeps the whole system consistent.
"""

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


class OutOfStockError(Exception):
    """Raised when an order requests more units than the catalog holds."""


class ECommerceSystem:
    """Facade over the six core data structures."""

    def __init__(self):
        # One instance of each structure; the facade coordinates them.
        self.catalog = ProductCatalog()            # SKU -> record (truth)
        self.search_index = SearchTrie()           # name words -> SKUs
        self.price_index = PriceIndex()            # price -> SKUs
        self.recommendations = RecommendationGraph()  # co-purchase edges
        self.orders = OrderQueue()                 # FIFO fulfilment
        self._next_order_id = 1                    # simple id sequence

    # ── Catalog management ────────────────────────────────────────────────

    def add_product(self, sku, name, price, stock):
        """Register a product in the catalog, search index, and price index.

        One business action, three structure writes — this is the
        "fan-out" the design report describes. Duplicate SKUs are
        rejected up front so no index is ever half-written.
        """
        if sku in self.catalog:
            raise ValueError(f"duplicate SKU: {sku}")
        product = Product(sku, name, price, stock)
        self.catalog.put(product)                  # 1. source of truth
        self.search_index.insert(name, sku)        # 2. searchable by name
        self.price_index.insert(price, sku)        # 3. filterable by price
        return product

    def remove_product(self, sku):
        """Delete a product from every structure that references it.

        The reverse of add_product: the catalog record carries the name
        and price we need to find and clean the index entries.
        """
        product = self.catalog.remove(sku)
        self.search_index.remove(product.name, sku)
        self.price_index.discard(product.price, sku)
        return product

    def restock(self, sku, quantity):
        """Increase a product's stock level. O(1) catalog update.

        Only the catalog changes — stock is not indexed anywhere else,
        which is exactly why the single-source-of-truth rule exists.
        """
        if quantity < 1:
            raise ValueError(f"restock quantity must be >= 1, got {quantity}")
        self.catalog.get(sku).stock += quantity

    # ── Queries ───────────────────────────────────────────────────────────

    def search(self, query, limit=10):
        """Autocomplete: products matching every word-prefix in the query.

        Each query word is one trie prefix walk. A multi-word query
        INTERSECTS the per-word SKU sets, so "wireless key" matches
        only products having a word starting with "wireless" AND a word
        starting with "key" (i.e. the Wireless Keyboard, not every
        wireless product). The first word's result order is preserved;
        the remaining words act as filters via set membership (O(1)
        per check).
        """
        words = query.lower().split()
        if not words:
            return []  # blank query: suggest nothing, not everything
        skus = self.search_index.prefix_search(words[0])
        for word in words[1:]:
            matches = set(self.search_index.prefix_search(word))
            skus = [sku for sku in skus if sku in matches]
        # Resolve SKUs to full records through the catalog (O(1) each).
        return [self.catalog.get(sku) for sku in skus[:limit]]

    def products_in_range(self, low, high):
        """Products priced within [low, high], ascending by price.

        The BST's pruned in-order traversal returns SKUs already sorted
        by price, so no re-sorting is needed here.
        """
        skus = self.price_index.range_query(low, high)
        return [self.catalog.get(sku) for sku in skus]

    def recommend_for(self, sku, k=5):
        """'Customers also bought' — co-purchase neighbours, strongest first.

        The `other in self.catalog` guard skips neighbours that were
        removed from the catalog after the edge was recorded — the graph
        deliberately keeps history, the catalog decides what still exists.
        """
        pairs = self.recommendations.also_bought(sku, k=k)
        return [(self.catalog.get(other), weight)
                for other, weight in pairs
                if other in self.catalog]

    def best_sellers(self, k=5):
        """Top-k products by units sold.

        Builds a max-heap over (sales_count, sku) for every product —
        O(n) bottom-up heapify — then pops k entries at O(log n) each.
        """
        heap = TopKHeap((p.sales_count, p.sku) for p in self.catalog)
        return [(self.catalog.get(sku), count) for count, sku in heap.top_k(k)]

    def low_stock(self, k=5):
        """The k products closest to running out.

        Same heap, min-heap trick: pushing NEGATED stock levels makes
        the max-heap surface the smallest stock first; the negation is
        undone in the result tuples.
        """
        heap = TopKHeap((-p.stock, p.sku) for p in self.catalog)
        return [(self.catalog.get(sku), -neg) for neg, sku in heap.top_k(k)]

    def most_returned(self, k=5):
        """Top-k products by units returned — the quality watchlist.

        Structurally identical to best_sellers: one O(n) heapify over
        the catalog, k pops. A product that sells a lot AND returns a
        lot appears on both dashboards, which is exactly the signal a
        merchandiser wants to see side by side.
        """
        heap = TopKHeap((p.returns_count, p.sku) for p in self.catalog)
        return [(self.catalog.get(sku), count) for count, sku in heap.top_k(k)]

    # ── Order pipeline ────────────────────────────────────────────────────

    def place_order(self, user_id, skus):
        """Validate SKUs and enqueue an order for fulfilment.

        Validation happens at CHECKOUT (here): an order naming an
        unknown SKU is rejected before it ever enters the queue, so the
        fulfilment loop only sees orders that could plausibly succeed.
        (Stock is NOT checked here — it can change while the order
        waits in the queue; fulfilment does the authoritative check.)
        """
        for sku in skus:
            if sku not in self.catalog:
                raise KeyError(f"unknown SKU in order: {sku}")
        order = Order(self._next_order_id, user_id, skus)
        self._next_order_id += 1
        self.orders.enqueue(order)
        return order

    def process_next_order(self):
        """Fulfil the oldest pending order.

        This is the single point where queue, catalog, and graph
        interact, and it follows a strict VALIDATE-THEN-COMMIT order:

          1. dequeue the oldest order (FIFO fairness);
          2. check EVERY line item against stock BEFORE touching
             anything — if any item falls short, the order is marked
             'failed' and OutOfStockError is raised with NO stock
             mutated (atomic failure, verified by the tests);
          3. only after all checks pass: decrement stock, increment
             sales counts;
          4. feed the co-purchase graph, so this order immediately
             improves future recommendations.
        """
        order = self.orders.dequeue()
        products = [self.catalog.get(sku) for sku in order.skus]
        # Phase 1: validate everything first (count handles an order
        # containing the same SKU more than once).
        for product in products:
            if product.stock < order.skus.count(product.sku):
                order.status = "failed"
                raise OutOfStockError(
                    f"order {order.order_id}: {product.sku} out of stock")
        # Phase 2: all checks passed — now it is safe to commit.
        for product in products:
            product.stock -= 1
            product.sales_count += 1
        # Phase 3: strengthen the recommendation signal.
        self.recommendations.record_order(order.skus)
        order.status = "fulfilled"
        return order

    def process_return(self, sku, quantity=1):
        """Accept a customer return: stock goes back up, returns count up.

        Sales counts are deliberately NOT decremented — best_sellers
        measures demand (units that sold), most_returned measures
        dissatisfaction (units that came back). Folding returns into
        sales would blur both signals.
        """
        if quantity < 1:
            raise ValueError(f"return quantity must be >= 1, got {quantity}")
        product = self.catalog.get(sku)
        # Cumulative cap: total returns may never exceed total units
        # sold, so the same unit cannot be returned twice.
        returnable = product.sales_count - product.returns_count
        if quantity > returnable:
            raise ValueError(
                f"cannot return {quantity} of {sku}: "
                f"{product.sales_count} sold, {product.returns_count} "
                f"already returned")
        product.stock += quantity
        product.returns_count += quantity
        return product

    def pending_orders(self):
        """Number of orders waiting in the fulfilment queue."""
        return len(self.orders)
