"""End-to-end demonstration of the e-commerce backend.

Runs one scripted customer journey — seed catalog, search, price filter,
order, fulfil, recommend, dashboards — printing the state changes that
each data structure contributes. Each numbered step below exercises a
different structure, and the ordering is deliberate: the fulfilment step
(6) feeds the co-purchase graph, which is what makes the recommendation
step (7) return results. That causal link — commerce improving the
recommendations — is the core integration claim of the project, shown
live.

Run from the project folder:

    python3 demo.py
"""

from ecommerce_system import ECommerceSystem, OutOfStockError

# A small, hand-picked catalog. The names deliberately share word
# prefixes ("Wireless Mouse" / "Wireless Keyboard" / "Wired Mouse") so
# the trie searches in steps 2-3 have interesting matches, and
# SKU-1015 gets stock 3 on purpose so step 10 can exhaust it.
CATALOG = [
    ("SKU-1001", "Wireless Mouse", 24.99, 40),
    ("SKU-1002", "Wireless Keyboard", 49.99, 25),
    ("SKU-1003", "Wired Mouse", 12.99, 60),
    ("SKU-1004", "USB-C Charging Cable", 9.99, 120),
    ("SKU-1005", "USB-C Wall Charger", 19.99, 80),
    ("SKU-1006", "Laptop Stand", 34.99, 18),
    ("SKU-1007", "Laptop Sleeve 14in", 22.50, 35),
    ("SKU-1008", "Mechanical Keyboard", 89.99, 12),
    ("SKU-1009", "Webcam 1080p", 59.99, 20),
    ("SKU-1010", "Noise Cancelling Headphones", 129.99, 15),
    ("SKU-1011", "Bluetooth Speaker", 45.00, 30),
    ("SKU-1012", "Monitor 27in", 219.99, 8),
    ("SKU-1013", "Monitor Arm", 39.99, 14),
    ("SKU-1014", "Desk Mat XL", 17.99, 50),
    ("SKU-1015", "Wireless Earbuds", 79.99, 3),
]

# The scripted order stream. Mouse + Keyboard appears in THREE orders
# (alice, carol, erin) so step 7 can show the keyboard as the top
# recommendation for the mouse with weight 3.
ORDERS = [
    ("alice", ["SKU-1001", "SKU-1002"]),
    ("bob", ["SKU-1001", "SKU-1004"]),
    ("carol", ["SKU-1001", "SKU-1002", "SKU-1014"]),
    ("dave", ["SKU-1004", "SKU-1005"]),
    ("erin", ["SKU-1001", "SKU-1002"]),
    ("frank", ["SKU-1012", "SKU-1013"]),
    ("grace", ["SKU-1004", "SKU-1005", "SKU-1001"]),
    ("heidi", ["SKU-1015"]),
]


def show(products, fmt=lambda p: f"{p.name} (${p.price:.2f})"):
    """Format a product list for one-line printing."""
    return ", ".join(fmt(p) for p in products) or "(none)"


def main():
    shop = ECommerceSystem()

    print("=== E-Commerce Backend Demo: six data structures, one order flow ===\n")

    # [1] Seeding: every add_product() writes THREE structures at once
    #     (hash table, trie, price BST). The stats lines afterwards show
    #     each structure's internal state as evidence.
    print(f"[1] Seeding catalog with {len(CATALOG)} products")
    for sku, name, price, stock in CATALOG:
        shop.add_product(sku, name, price, stock)
    cat = shop.catalog.stats()
    trie = shop.search_index.stats()
    print(f"    hash table: {cat['size']} records, {cat['capacity']} buckets, "
          f"load {cat['load_factor']:.2f}, max chain {cat['max_chain']}")
    print(f"    trie: {trie['nodes']} nodes | price BST: height "
          f"{shop.price_index.height()}, {len(shop.price_index)} entries\n")

    # [2] Single-prefix search: one trie walk, subtree collection.
    #     "wire" matches Wired AND Wireless products (shared prefix).
    print('[2] Customer searches "wire" (trie prefix walk)')
    print(f"    -> {show(shop.search('wire'))}\n")

    # [3] Multi-word search: two trie walks INTERSECTED, so only the
    #     product matching both prefixes survives.
    print('[3] Customer searches "wireless key"')
    print(f"    -> {show(shop.search('wireless key'))}\n")

    # [4] Range query: pruned BST in-order traversal; note the results
    #     come back already sorted by price.
    print("[4] Price filter $15-$50 (BST range query)")
    print(f"    -> {show(shop.products_in_range(15, 50))}\n")

    # [5] Checkout: orders are validated (all SKUs must exist) and
    #     enqueued FIFO. Nothing else changes yet — stock is untouched
    #     until fulfilment.
    print(f"[5] Placing {len(ORDERS)} orders (FIFO queue)")
    for user, skus in ORDERS:
        order = shop.place_order(user, skus)
        print(f"    queued order #{order.order_id} for {user}: {', '.join(skus)}")
    print(f"    pending orders: {shop.pending_orders()}\n")

    # [6] Fulfilment: each processed order decrements stock, increments
    #     sales, and adds co-purchase edges. The graph stats afterwards
    #     prove the side effect happened.
    print("[6] Fulfilment loop (stock/sales update + co-purchase edges)")
    while shop.pending_orders():
        try:
            order = shop.process_next_order()
            print(f"    order #{order.order_id} fulfilled ({order.user_id})")
        except OutOfStockError as exc:
            print(f"    REJECTED: {exc}")
    graph = shop.recommendations.stats()
    print(f"    graph now has {graph['vertices']} vertices, "
          f"{graph['edges']} edges\n")

    # [7] Recommendations: only meaningful BECAUSE step 6 ran. The
    #     keyboard ranks first with weight 3 (three orders contained
    #     mouse + keyboard).
    print('[7] Recommendations for "Wireless Mouse" (graph neighbours by weight)')
    for product, weight in shop.recommend_for("SKU-1001", k=3):
        print(f"    also bought: {product.name} (together in {weight} orders)")
    print()

    # [8] Best sellers: O(n) heapify over sales counts + k pops.
    print("[8] Best sellers - top 3 (max-heap on sales counts)")
    for product, sold in shop.best_sellers(3):
        print(f"    {product.name}: {sold} sold")
    print()

    # [9] Low stock: the same heap fed NEGATED stock levels, so the
    #     smallest stock surfaces first (min-heap trick).
    print("[9] Low-stock alert - top 3 (min-heap on stock)")
    for product, stock in shop.low_stock(3):
        print(f"    {product.name}: {stock} left")
    print()

    # [10] Error handling, exercised on purpose:
    #      - an unknown SKU is rejected at CHECKOUT (never queued);
    #      - SKU-1015 started with stock 3 and heidi bought one, so the
    #        third of these three orders must fail at FULFILMENT with
    #        an atomic, clean rejection.
    print("[10] Error handling")
    try:
        shop.place_order("mallory", ["SKU-9999"])
    except KeyError as exc:
        print(f"    unknown SKU rejected: {exc}")
    try:
        shop.place_order("mallory", ["SKU-1015"])
        shop.place_order("mallory", ["SKU-1015"])
        shop.place_order("mallory", ["SKU-1015"])
        while shop.pending_orders():
            shop.process_next_order()
    except OutOfStockError as exc:
        print(f"    out-of-stock order rejected: {exc}")


if __name__ == "__main__":
    main()
