"""Binary search tree price index: price -> SKU set.

WHY A BST HERE?
The storefront's "show products between $20 and $50" filter is an
ORDERED RANGE QUERY — the one workload a hash table fundamentally
cannot serve, because hashing deliberately destroys key order. A binary
search tree keeps prices ordered by construction (everything smaller in
the left subtree, everything larger in the right), so a range query can
walk the tree in order, PRUNE whole subtrees that fall outside the
requested band, and emit results already sorted by price.

Complexity: O(h + k) per range query, for tree height h and k results,
versus O(n) for scanning the whole catalog.

DESIGN DECISIONS
- Duplicate prices share ONE node holding a set of SKUs, so the tree
  has one node per DISTINCT price point (many products cost $19.99).
- All operations are ITERATIVE (explicit loops/stacks, no recursion).
  This matters because the tree's documented worst case — inserting
  prices in sorted order — degenerates it into a linked list of height
  n, and a recursive walk over that would overflow Python's call stack.
  The Phase 3 stress tests build exactly that degenerate tree.
- The tree is deliberately UNBALANCED. With random insertion order the
  expected height is O(log n); the monotone-insertion worst case is
  accepted, measured in the benchmarks, and left to future work
  (AVL/red-black rotations) as documented in the reports.
"""


class _PriceNode:
    """One node per distinct price; holds every SKU at that price."""

    __slots__ = ("price", "skus", "left", "right")

    def __init__(self, price):
        self.price = price
        self.skus = set()   # all SKUs whose product costs exactly `price`
        self.left = None    # subtree of strictly smaller prices
        self.right = None   # subtree of strictly larger prices


class PriceIndex:
    """Unbalanced BST keyed by price, one node per distinct price.

    Complexity (h = height, expected O(log n) on random input):
        insert / discard : O(h)
        range_query : O(h + k) for k reported SKUs
    """

    def __init__(self):
        self._root = None
        self._size = 0  # number of (price, sku) pairs indexed

    def insert(self, price, sku):
        """Index a SKU under its price. O(h).

        Standard iterative BST descent: go left for smaller, right for
        larger, stop when we find the price's node or create it at the
        bottom of the search path.
        """
        if price < 0:
            raise ValueError(f"price must be non-negative, got {price}")
        if self._root is None:
            # First insertion ever: this price becomes the root.
            self._root = _PriceNode(price)
            node = self._root
        else:
            node = self._root
            while True:
                if price == node.price:
                    break  # price already has a node; just add the SKU
                elif price < node.price:
                    if node.left is None:
                        # Empty left slot: the new price lives here.
                        node.left = _PriceNode(price)
                        node = node.left
                        break
                    node = node.left
                else:
                    if node.right is None:
                        node.right = _PriceNode(price)
                        node = node.right
                        break
                    node = node.right
        # Only count the pair if this SKU wasn't already at this price.
        if sku not in node.skus:
            node.skus.add(sku)
            self._size += 1

    def discard(self, price, sku):
        """Remove one SKU from its price node, if present. O(h).

        The node itself stays in the tree even if its SKU set becomes
        empty — queries simply skip empty nodes. Full structural node
        deletion (the three-case BST delete) is not needed by the
        application and would complicate the code for no benefit.
        """
        node = self._root
        while node is not None:
            if price == node.price:
                if sku in node.skus:
                    node.skus.remove(sku)
                    self._size -= 1
                return
            # Descend toward where the price must live.
            node = node.left if price < node.price else node.right

    def range_query(self, low, high):
        """Return SKUs with low <= price <= high, ascending by price.

        This is an iterative in-order traversal with two PRUNING rules
        that keep it O(h + k) instead of O(n):

          1. Going down: the left subtree holds strictly smaller prices,
             so we only descend left while the current node's price is
             still above `low` — anything further left is out of range.
          2. Coming back up: in-order traversal visits prices in
             ascending order, so the first node above `high` proves
             every remaining node is also above `high`, and we stop.
        """
        if low > high:
            raise ValueError(f"invalid range: low={low} > high={high}")
        results = []
        stack = []          # explicit stack replaces recursion
        node = self._root
        while stack or node is not None:
            # Slide down the left spine, applying pruning rule 1.
            while node is not None:
                stack.append(node)
                # Prune: left subtree holds strictly smaller prices, so it
                # can only matter while the current price exceeds `low`
                node = node.left if node.price > low else None
            node = stack.pop()  # next node in ascending price order
            if low <= node.price <= high:
                # sorted() makes output deterministic when several SKUs
                # share one price point.
                results.extend(sorted(node.skus))
            if node.price > high:
                break  # rule 2: everything after this is even larger
            node = node.right  # continue in-order into larger prices
        return results

    def __len__(self):
        return self._size

    def height(self):
        """Tree height via iterative level-order walk (benchmark diagnostic).

        Health check for the reports: expected ~2·log2(n) after random
        insertions, but exactly n after sorted insertions — the
        degeneration the stress tests demonstrate.
        """
        if self._root is None:
            return 0
        depth = 0
        level = [self._root]
        while level:
            depth += 1
            # Replace the current level with all of its children; the
            # number of iterations is exactly the tree height.
            level = [child
                     for n in level
                     for child in (n.left, n.right)
                     if child is not None]
        return depth
