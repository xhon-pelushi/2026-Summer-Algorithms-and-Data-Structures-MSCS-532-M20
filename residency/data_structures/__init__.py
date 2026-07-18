"""Core data structures for the e-commerce order platform.

Each structure is implemented from scratch (no dict/heapq shortcuts for the
mechanics being demonstrated) and exposes its core operations with documented
time complexity.
"""

from .product_catalog import Product, ProductCatalog
from .search_trie import SearchTrie
from .price_index import PriceIndex
from .recommendation_graph import RecommendationGraph
from .top_k_heap import TopKHeap
from .order_queue import Order, OrderQueue

__all__ = [
    "Product",
    "ProductCatalog",
    "SearchTrie",
    "PriceIndex",
    "RecommendationGraph",
    "TopKHeap",
    "Order",
    "OrderQueue",
]
