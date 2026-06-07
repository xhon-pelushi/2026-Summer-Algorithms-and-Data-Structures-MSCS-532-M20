"""
MSCS-532 Assignment 3 — Algorithm Efficiency and Scalability
Implements Randomized Quicksort, Deterministic Quicksort, and Hash Table with Chaining.
"""

import random
import sys
import time
import statistics

sys.setrecursionlimit(100_000)


# ── Randomized Quicksort ───────────────────────────────────────────────────────

def randomized_quicksort(arr: list) -> None:
    """Sort arr in-place; pivot chosen uniformly at random from the subarray."""
    _rqs(arr, 0, len(arr) - 1)


def _rqs(arr: list, lo: int, hi: int) -> None:
    if lo < hi:
        p = _rqs_partition(arr, lo, hi)
        _rqs(arr, lo, p - 1)
        _rqs(arr, p + 1, hi)


def _rqs_partition(arr: list, lo: int, hi: int) -> int:
    r = random.randint(lo, hi)
    arr[r], arr[hi] = arr[hi], arr[r]
    pivot = arr[hi]
    i = lo - 1
    for j in range(lo, hi):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[hi] = arr[hi], arr[i + 1]
    return i + 1


# ── Deterministic Quicksort (first element as pivot) ──────────────────────────

def deterministic_quicksort(arr: list) -> None:
    """Sort arr in-place; first element always chosen as pivot (degrades on ordered input)."""
    _dqs(arr, 0, len(arr) - 1)


def _dqs(arr: list, lo: int, hi: int) -> None:
    if lo < hi:
        p = _dqs_partition(arr, lo, hi)
        _dqs(arr, lo, p - 1)
        _dqs(arr, p + 1, hi)


def _dqs_partition(arr: list, lo: int, hi: int) -> int:
    arr[lo], arr[hi] = arr[hi], arr[lo]   # move first element to pivot position at end
    pivot = arr[hi]
    i = lo - 1
    for j in range(lo, hi):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[hi] = arr[hi], arr[i + 1]
    return i + 1


# ── Hash Table with Separate Chaining ─────────────────────────────────────────

class HashTable:
    """
    Separate-chaining hash table backed by a universal (MAD) hash function:
        h(k) = ((a * hash(k) + b) mod p) mod m
    where p is a large prime and a, b are drawn at random from valid ranges.

    Automatically resizes up (×2) when load factor exceeds 0.75 and
    down (÷2) when load factor drops below 0.20.
    """

    _PRIME: int = 1_000_003
    _MIN_SLOTS: int = 16
    _LOAD_HIGH: float = 0.75
    _LOAD_LOW: float = 0.20

    def __init__(self, initial_slots: int = 16) -> None:
        self._m: int = max(initial_slots, self._MIN_SLOTS)
        self._n: int = 0
        self._table: list[list] = [[] for _ in range(self._m)]
        self._a, self._b = self._new_params()

    # ── private helpers ────────────────────────────────────────────────────────

    def _new_params(self) -> tuple[int, int]:
        p = self._PRIME
        return random.randint(1, p - 1), random.randint(0, p - 1)

    def _hash(self, key) -> int:
        raw = hash(key) & 0x7FFF_FFFF_FFFF_FFFF   # ensure non-negative
        return int((self._a * raw + self._b) % self._PRIME) % self._m

    def _resize(self, new_m: int) -> None:
        old = self._table
        self._m = max(new_m, self._MIN_SLOTS)
        self._n = 0
        self._table = [[] for _ in range(self._m)]
        self._a, self._b = self._new_params()
        for chain in old:
            for k, v in chain:
                self.insert(k, v)

    # ── public API ─────────────────────────────────────────────────────────────

    def insert(self, key, value) -> None:
        """Add key-value pair; updates value if key already exists. O(1) expected."""
        h = self._hash(key)
        for i, (k, _) in enumerate(self._table[h]):
            if k == key:
                self._table[h][i] = (key, value)
                return
        self._table[h].append((key, value))
        self._n += 1
        if self._n / self._m > self._LOAD_HIGH:
            self._resize(self._m * 2)

    def search(self, key):
        """Return the value for key, or None if not present. O(1) expected."""
        h = self._hash(key)
        for k, v in self._table[h]:
            if k == key:
                return v
        return None

    def delete(self, key) -> bool:
        """Remove key-value pair; return True if found. O(1) expected."""
        h = self._hash(key)
        chain = self._table[h]
        for i, (k, _) in enumerate(chain):
            if k == key:
                chain.pop(i)
                self._n -= 1
                if self._m > self._MIN_SLOTS and self._n / self._m < self._LOAD_LOW:
                    self._resize(max(self._m // 2, self._MIN_SLOTS))
                return True
        return False

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def load_factor(self) -> float:
        return self._n / self._m

    @property
    def slot_count(self) -> int:
        return self._m

    @property
    def element_count(self) -> int:
        return self._n

    def avg_chain_length(self) -> float:
        occupied = [len(c) for c in self._table if c]
        return statistics.mean(occupied) if occupied else 0.0

    def max_chain_length(self) -> int:
        return max((len(c) for c in self._table), default=0)


# ── Benchmarking utilities ────────────────────────────────────────────────────

def _bench(func, data: list, runs: int) -> float:
    times = []
    for _ in range(runs):
        sample = data[:]
        t0 = time.perf_counter()
        try:
            func(sample)
            times.append(time.perf_counter() - t0)
        except RecursionError:
            times.append(float("inf"))
    return statistics.mean(times)


def run_quicksort_benchmarks(
    sizes: tuple = (500, 1000, 2500, 5000),
    runs_normal: int = 3,
    runs_worst: int = 2,
) -> dict:
    """Return nested dict: results[distribution][algorithm][n] = avg_seconds."""
    generators = {
        "random":   (lambda n: random.sample(range(n * 10), n), runs_normal),
        "sorted":   (lambda n: list(range(n)),                  runs_worst),
        "reverse":  (lambda n: list(range(n, 0, -1)),           runs_worst),
        "repeated": (lambda n: [random.randint(0, max(1, n // 10)) for _ in range(n)], runs_normal),
    }
    results: dict = {}
    for dist, (gen, runs) in generators.items():
        results[dist] = {"randomized": {}, "deterministic": {}}
        for n in sizes:
            data = gen(n)
            results[dist]["randomized"][n] = _bench(randomized_quicksort, data, runs_normal)
            results[dist]["deterministic"][n] = _bench(deterministic_quicksort, data, runs)
    return results


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── Correctness checks ────────────────────────────────────────────────────
    test_cases = [
        ("random",   [5, 3, 8, 1, 9, 2, 7]),
        ("sorted",   [1, 2, 3, 4, 5]),
        ("reverse",  [5, 4, 3, 2, 1]),
        ("repeated", [3, 3, 1, 3, 2, 1]),
        ("empty",    []),
        ("single",   [42]),
    ]
    for label, arr in test_cases:
        a, b = arr[:], arr[:]
        randomized_quicksort(a)
        deterministic_quicksort(b)
        assert a == sorted(arr), f"Randomized Quicksort failed on {label}"
        assert b == sorted(arr), f"Deterministic Quicksort failed on {label}"
    print("All Quicksort correctness checks passed.")

    # ── Hash table correctness ────────────────────────────────────────────────
    ht = HashTable()
    for i in range(100):
        ht.insert(f"key{i}", i * 10)
    assert ht.search("key42") == 420
    assert ht.search("missing") is None
    ht.delete("key42")
    assert ht.search("key42") is None
    ht.insert("key42", 999)
    assert ht.search("key42") == 999
    print(f"Hash table correctness passed. "
          f"n={ht.element_count}, m={ht.slot_count}, "
          f"load={ht.load_factor:.2f}, avg_chain={ht.avg_chain_length():.2f}")

    # ── Quick benchmark ───────────────────────────────────────────────────────
    print("\nRunning benchmarks (sizes 500–5000) …")
    results = run_quicksort_benchmarks()
    sizes = (500, 1000, 2500, 5000)
    print(f"\n{'Distribution':<12} {'Algorithm':<16} " +
          "  ".join(f"n={n:>5}" for n in sizes))
    for dist in ("random", "sorted", "reverse", "repeated"):
        for algo in ("randomized", "deterministic"):
            row = f"{dist:<12} {algo:<16} "
            row += "  ".join(
                f"{results[dist][algo][n]:>8.4f}s" for n in sizes
            )
            print(row)
