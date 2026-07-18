"""Synthetic catalog and order-stream generator for the benchmarks.

REALISM MATTERS FOR FAIR BENCHMARKS
Two deliberate choices make this synthetic data behave like a real
store instead of random noise:

1. PRODUCT NAMES are adjective + noun + variant combinations
   ("Wireless Keyboard XL", "Portable Speaker 2"). Real catalogs are
   full of shared word prefixes, and shared prefixes are precisely what
   a trie compresses — benchmarking it on random strings would make the
   trie look worse (no sharing) and the linear scan look better (fewer
   partial matches).

2. ORDER CONTENTS follow a POPULARITY SKEW: the product index is drawn
   as int(n * random()^2), which quadratically biases selection toward
   low indices. A minority of "hit" products therefore appears in many
   orders, giving the co-purchase graph hub vertices with high degree —
   exactly the shape real co-purchase data has, and the harder case for
   the also_bought ranking.

Both generators take a seed so every benchmark run sees identical data,
making timings comparable across runs and machines.
"""

import random

# Vocabulary for product names. 20 adjectives x 20 nouns x 8 variants
# gives 3,200 distinct names; with 100k products many names repeat,
# which is realistic (multiple sellers, same product type) and gives
# prefix searches result sets worth measuring.
ADJECTIVES = [
    "Wireless", "Wired", "Portable", "Compact", "Ergonomic", "Adjustable",
    "Foldable", "Rechargeable", "Smart", "Classic", "Premium", "Ultra",
    "Mini", "Pro", "Slim", "Rugged", "Silent", "Backlit", "Magnetic",
    "Waterproof",
]
NOUNS = [
    "Mouse", "Keyboard", "Headphones", "Speaker", "Monitor", "Webcam",
    "Charger", "Cable", "Stand", "Sleeve", "Hub", "Adapter", "Microphone",
    "Lamp", "Desk Mat", "Earbuds", "Tablet", "Router", "Dock", "Tripod",
]
VARIANTS = ["", " XL", " Mini", " 2", " Plus", " Lite", " Max", " SE"]


def make_products(n, seed=1):
    """Return n (sku, name, price, stock) tuples.

    SKUs are sequential and unique; prices are uniform on $1-$500
    (which the range-query benchmark relies on: a $100-$125 window is
    ~5% of the catalog); stock is 5-100 units.
    """
    rng = random.Random(seed)  # private RNG: reproducible, no global state
    products = []
    for i in range(n):
        name = (f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}"
                f"{rng.choice(VARIANTS)}").strip()
        products.append((
            f"SKU-{100000 + i}",             # unique, fixed-width SKU
            name,
            round(rng.uniform(1.0, 500.0), 2),  # price in cents precision
            rng.randint(5, 100),                # starting stock
        ))
    return products


def make_orders(products, n_orders, seed=2):
    """Return n_orders (user_id, [skus]) tuples with popularity skew.

    Each order holds 1-4 DISTINCT items (a set comprehension dedupes
    collisions, mirroring a shopping cart). The rng.random()**2 term is
    the popularity skew: squaring a uniform [0,1) sample pushes it
    toward 0, so low-index products are chosen far more often and
    become the store's best sellers / graph hubs.
    """
    rng = random.Random(seed)
    n = len(products)
    orders = []
    for i in range(n_orders):
        n_items = rng.randint(1, 4)
        skus = {products[int(n * rng.random() ** 2)][0]
                for _ in range(n_items)}
        # User ids repeat across orders (n_orders/4 distinct users),
        # like a customer base with returning buyers.
        orders.append((f"user-{rng.randint(1, n_orders // 4 + 1)}",
                       sorted(skus)))
    return orders
