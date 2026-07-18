"""Hash table product catalog: SKU -> product record.

WHY A HASH TABLE HERE?
The catalog is the most frequently touched structure in the platform:
every product page view, cart operation, stock check, and fulfilment step
must resolve a SKU to its product record. A hash table provides expected
O(1) insertion, lookup, and deletion, so the cost of this "resolve" step
never grows with the size of the store.

DESIGN DECISIONS
- The catalog is the SINGLE SOURCE OF TRUTH: every other structure in the
  system (trie, BST, graph, heap, queue) stores only SKU strings and
  resolves them here. Product data is never duplicated, so the indexes
  can never disagree with each other.
- Collisions are handled with SEPARATE CHAINING (each bucket holds a
  Python list of the products that hashed there). Chaining was chosen
  over open addressing because it degrades gracefully as the table fills
  and makes deletion trivial (just remove from the list).
- Keys are hashed with FNV-1a, a simple, well-known byte-mixing function,
  implemented by hand so the mechanics are visible rather than hidden
  behind Python's built-in hash().
- The bucket array DOUBLES whenever the load factor (records / buckets)
  exceeds MAX_LOAD = 0.75. Keeping the load factor bounded keeps the
  average chain length constant, which is what makes lookups O(1).
  Resizing can be disabled via a constructor flag so the benchmarks can
  measure exactly how badly a fixed-size table degrades (the O(n/m)
  chain-growth effect).
"""


class Product:
    """A product record stored in the catalog.

    This is a plain data holder; all indexing intelligence lives in the
    surrounding structures. __slots__ fixes the attribute set, which both
    prevents typo-attributes and reduces per-object memory (important
    when the benchmarks build 100,000 of these).
    """

    __slots__ = ("sku", "name", "price", "stock", "sales_count",
                 "returns_count")

    def __init__(self, sku, name, price, stock):
        # Validate at the boundary: a negative price or stock is a caller
        # bug, and rejecting it here stops bad data from ever entering
        # any index that references this record.
        if price < 0:
            raise ValueError(f"price must be non-negative, got {price}")
        if stock < 0:
            raise ValueError(f"stock must be non-negative, got {stock}")
        self.sku = sku
        self.name = name
        self.price = price
        self.stock = stock
        # Every product starts with zero sales; fulfilment increments
        # this, and the best-seller heap ranks on it.
        self.sales_count = 0
        # Likewise for returns: process_return() increments this, and
        # the most-returned dashboard heap ranks on it.
        self.returns_count = 0

    def __repr__(self):
        return (f"Product(sku={self.sku!r}, name={self.name!r}, "
                f"price={self.price:.2f}, stock={self.stock})")


class ProductCatalog:
    """Separate-chaining hash table mapping SKU strings to Product records.

    Average-case complexity with resizing enabled:
        put / get / remove / contains : O(1)
    Worst case (all keys collide into one chain): O(n).
    Space: O(n + m) for n records and m buckets.
    """

    # FNV-1a constants for 64-bit hashing (published, standard values).
    _FNV_OFFSET = 0xCBF29CE484222325
    _FNV_PRIME = 0x100000001B3

    # Resize threshold: when size/buckets exceeds this, the bucket array
    # doubles. 0.75 is the classic compromise between wasted memory
    # (low threshold) and long chains (high threshold).
    MAX_LOAD = 0.75

    def __init__(self, initial_capacity=64, resize_enabled=True):
        if initial_capacity < 1:
            raise ValueError("initial_capacity must be >= 1")
        # One empty list ("chain") per bucket. A chain holds every
        # product whose hash landed in that bucket.
        self._buckets = [[] for _ in range(initial_capacity)]
        self._size = 0  # number of stored records (not buckets)
        # Benchmark hook: with resizing off, the table keeps its initial
        # capacity forever and chains grow as O(n/m).
        self.resize_enabled = resize_enabled

    def _hash(self, key):
        """FNV-1a hash of the key string, reduced modulo bucket count.

        FNV-1a walks the key byte by byte, XOR-ing each byte in and then
        multiplying by a large prime. The XOR-then-multiply order gives
        good "avalanche" behaviour: similar SKUs like SKU-1001 and
        SKU-1002 land in unrelated buckets.
        """
        h = self._FNV_OFFSET
        for byte in key.encode("utf-8"):
            h ^= byte                       # mix the byte into the state
            h = (h * self._FNV_PRIME) & 0xFFFFFFFFFFFFFFFF  # keep 64 bits
        # Map the 64-bit hash onto an actual bucket index.
        return h % len(self._buckets)

    def put(self, product):
        """Insert or update a product record. Average O(1).

        If the SKU already exists we REPLACE the record in place (an
        update), so the table never holds two records for one SKU.
        """
        if not isinstance(product, Product):
            raise TypeError("put() expects a Product instance")
        chain = self._buckets[self._hash(product.sku)]
        # Scan the (short) chain for an existing record with this SKU.
        for i, existing in enumerate(chain):
            if existing.sku == product.sku:
                chain[i] = product          # update: overwrite in place
                return
        # Not found: append as a new record.
        chain.append(product)
        self._size += 1
        # Grow the table if it is getting crowded. Doubling keeps the
        # amortized cost of insertion O(1) even counting the rebuilds.
        if self.resize_enabled and self._size / len(self._buckets) > self.MAX_LOAD:
            self._resize(len(self._buckets) * 2)

    def get(self, sku):
        """Return the product for a SKU. Average O(1).

        Raises KeyError if the SKU is not in the catalog — callers are
        expected to treat an unknown SKU as an error, not a silent miss.
        """
        # Hash to the right bucket, then linearly scan its short chain.
        for product in self._buckets[self._hash(sku)]:
            if product.sku == sku:
                return product
        raise KeyError(f"unknown SKU: {sku}")

    def remove(self, sku):
        """Delete and return a product record. Average O(1).

        This is where chaining pays off: deletion is a simple list.pop
        from the chain, with none of the tombstone bookkeeping that
        open-addressing schemes require.
        """
        chain = self._buckets[self._hash(sku)]
        for i, product in enumerate(chain):
            if product.sku == sku:
                self._size -= 1
                return chain.pop(i)
        raise KeyError(f"unknown SKU: {sku}")

    def _resize(self, new_capacity):
        """Rebuild every chain into a larger bucket array. O(n).

        Every record must be re-hashed because the bucket index depends
        on the table size (hash % len(buckets)). This full rebuild is
        the "resize pause" discussed in the reports: expensive when it
        happens, but amortized to O(1) per insert because capacity
        doubles each time.
        """
        old_buckets = self._buckets
        self._buckets = [[] for _ in range(new_capacity)]
        for chain in old_buckets:
            for product in chain:
                # Re-hash against the NEW bucket count.
                self._buckets[self._hash(product.sku)].append(product)

    def __contains__(self, sku):
        """Membership test (`sku in catalog`). Average O(1)."""
        try:
            self.get(sku)
            return True
        except KeyError:
            return False

    def __len__(self):
        return self._size

    def __iter__(self):
        """Yield every stored product (used by the dashboard heaps)."""
        for chain in self._buckets:
            yield from chain

    def stats(self):
        """Diagnostics for benchmarking: load factor and chain lengths.

        max_chain is the key health metric: with resizing it stays tiny
        (1-3); with resizing disabled it grows linearly with n.
        """
        lengths = [len(c) for c in self._buckets]
        return {
            "size": self._size,
            "capacity": len(self._buckets),
            "load_factor": self._size / len(self._buckets),
            "max_chain": max(lengths),
            "nonempty_buckets": sum(1 for length in lengths if length),
        }
