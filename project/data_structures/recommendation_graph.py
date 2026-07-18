"""Co-purchase graph for "customers also bought" recommendations.

WHY A GRAPH HERE?
"Customers who bought X also bought Y" is inherently a relationship
between PAIRS of products, and pairwise relationships are exactly what
graphs model. Vertices are SKUs; an undirected edge (a, b) exists once
products a and b have appeared in the same order, and the edge WEIGHT
counts how many orders contained both. A recommendation for a product
is then simply its strongest-weighted neighbours.

This is the classic item-to-item collaborative filtering shape used at
production scale by large retailers: it grows with the number of
PRODUCTS (stable, moderate) rather than the number of USERS (huge,
volatile), and it can be served in real time from a lookup.

WHY AN ADJACENCY LIST (NOT A MATRIX)?
The co-purchase graph is extremely sparse — of all possible product
pairs, only a tiny fraction is ever bought together. An adjacency
matrix would allocate n^2 cells to store mostly zeros; the adjacency
list (a dict of dicts) stores only the edges that actually exist,
giving O(V + E) space.

HOW IT IS FED
The fulfilment pipeline calls record_order() for every processed order,
so the recommendation signal improves continuously as a free side
effect of commerce — no batch job, no training step.
"""


class RecommendationGraph:
    """Adjacency-list co-purchase graph.

    Complexity (d = degree of the queried SKU):
        add_copurchase : O(1)
        record_order (m items) : O(m^2) pair updates — fine because real
            orders are small (a handful of items)
        also_bought : O(d log d) for the weight ranking
    Space: O(V + E).
    """

    def __init__(self):
        # sku -> {neighbour_sku: co-purchase count}.  Storing the weight
        # in BOTH directions (a->b and b->a) doubles memory but makes
        # every neighbourhood query a single dict lookup.
        self._adj = {}
        self._edge_count = 0  # number of distinct undirected edges

    def _ensure_vertex(self, sku):
        """Create an empty neighbour map the first time a SKU is seen."""
        if sku not in self._adj:
            self._adj[sku] = {}

    def add_copurchase(self, sku_a, sku_b):
        """Record that two SKUs appeared in the same order. O(1).

        Creates the edge with weight 1 on first sighting, increments
        the weight on every later co-purchase.
        """
        if sku_a == sku_b:
            return  # self-loops carry no recommendation signal
        self._ensure_vertex(sku_a)
        self._ensure_vertex(sku_b)
        # Count a NEW edge only once (checking one direction suffices
        # because both directions are always written together below).
        if sku_b not in self._adj[sku_a]:
            self._edge_count += 1
        # Symmetric update: the relationship is undirected.
        self._adj[sku_a][sku_b] = self._adj[sku_a].get(sku_b, 0) + 1
        self._adj[sku_b][sku_a] = self._adj[sku_b].get(sku_a, 0) + 1

    def record_order(self, skus):
        """Add co-purchase edges for every SKU pair in one order.

        An order with m distinct items contributes m(m-1)/2 pair
        updates. dict.fromkeys() removes duplicates while preserving
        order (buying two of the same item is not a co-purchase).
        """
        unique = list(dict.fromkeys(skus))
        # Classic all-pairs double loop over the (small) order.
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                self.add_copurchase(unique[i], unique[j])

    def also_bought(self, sku, k=5):
        """Top-k neighbours of a SKU by co-purchase weight.

        Returns [(neighbour_sku, weight)] strongest first; empty list
        for a SKU with no purchase history. An unknown SKU is NOT an
        error — a brand-new product simply has no signal yet, and the
        storefront shows an empty panel.
        """
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        neighbours = self._adj.get(sku)
        if not neighbours:
            return []
        # Sort by descending weight; ties broken by SKU so the result
        # is deterministic (important for the tests and the demo).
        ranked = sorted(neighbours.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:k]

    def degree(self, sku):
        """Number of distinct co-purchase partners for a SKU. O(1)."""
        return len(self._adj.get(sku, {}))

    def stats(self):
        """Diagnostics for benchmarking: vertex and edge counts."""
        return {"vertices": len(self._adj), "edges": self._edge_count}
