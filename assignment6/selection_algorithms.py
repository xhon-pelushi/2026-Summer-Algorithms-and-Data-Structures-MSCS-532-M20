"""
MSCS-532 Assignment 6, Part 1 — Medians and Order Statistics
Implements the deterministic Median-of-Medians selection algorithm
(worst-case Theta(n)) and Randomized Quickselect (expected Theta(n)),
on top of one shared partition routine, with optional comparison
instrumentation used to empirically validate the theoretical analysis.
"""

import random
import statistics
import time

# Both algorithms recurse to depth O(log n) in the worst/expected case, but a
# generous limit avoids surprises on adversarial inputs during testing.
import sys
sys.setrecursionlimit(20_000)


# ── Shared partition routine (same scheme as Assignment 5's Quicksort) ────────

def _partition_around_front(values: list, lo: int, hi: int, counters: dict | None) -> int:
    pivot_value = values[lo]
    boundary = lo

    for cursor in range(lo + 1, hi + 1):
        _track_comparison(counters)
        if values[cursor] < pivot_value:
            boundary += 1
            values[boundary], values[cursor] = values[cursor], values[boundary]

    values[lo], values[boundary] = values[boundary], values[lo]
    return boundary


def _insertion_sort(values: list, lo: int, hi: int, counters: dict | None) -> None:
    """Sort values[lo..hi] in place. Only ever called on groups of at most 5
    elements, so each call costs O(1) regardless of the surrounding input size."""
    for i in range(lo + 1, hi + 1):
        key = values[i]
        j = i - 1
        while j >= lo:
            _track_comparison(counters)
            if values[j] <= key:
                break
            values[j + 1] = values[j]
            j -= 1
        values[j + 1] = key


# ── Deterministic selection: Median-of-Medians pivot ──────────────────────────

def deterministic_select(values: list, k: int, counters: dict | None = None):
    """Return the k-th smallest element of values (k is 1-indexed). Does not
    mutate the input. Worst-case Theta(n): the pivot is always within the
    middle 30% of the current range, so every level shrinks the problem by a
    guaranteed factor regardless of how the input is arranged."""
    _validate(values, k)
    working = values[:]
    index = _select_mom(working, 0, len(working) - 1, k - 1, counters)
    return working[index]


def _select_mom(values: list, lo: int, hi: int, rank: int, counters: dict | None) -> int:
    """Partition values[lo..hi] in place until the element of 0-indexed rank
    `rank` (relative to lo) settles into its final position; return that index."""
    while True:
        _track_round(counters)
        if lo == hi:
            return lo

        pivot_index = _median_of_medians_index(values, lo, hi, counters)
        values[lo], values[pivot_index] = values[pivot_index], values[lo]
        split = _partition_around_front(values, lo, hi, counters)

        local_rank = split - lo
        if rank == local_rank:
            return split
        elif rank < local_rank:
            hi = split - 1
        else:
            rank -= local_rank + 1
            lo = split + 1


def _median_of_medians_index(values: list, lo: int, hi: int, counters: dict | None) -> int:
    """Return the index (within [lo, hi]) of the median of the medians of
    consecutive groups of 5. For n <= 5 that is just the group's own median."""
    n = hi - lo + 1
    if n <= 5:
        _insertion_sort(values, lo, hi, counters)
        return lo + (n - 1) // 2

    # Find each group-of-5's median and move it into a contiguous prefix
    # starting at lo, so the medians can be selected from in place afterward.
    num_groups = 0
    group_start = lo
    while group_start <= hi:
        group_end = min(group_start + 4, hi)
        _insertion_sort(values, group_start, group_end, counters)
        median_index = group_start + (group_end - group_start) // 2
        slot = lo + num_groups
        values[slot], values[median_index] = values[median_index], values[slot]
        num_groups += 1
        group_start += 5

    mid_rank = (num_groups - 1) // 2
    return _select_mom(values, lo, lo + num_groups - 1, mid_rank, counters)


# ── Randomized selection: Randomized Quickselect ──────────────────────────────

def randomized_select(values: list, k: int, counters: dict | None = None):
    """Return the k-th smallest element of values (k is 1-indexed). Does not
    mutate the input. Expected Theta(n): the pivot is drawn uniformly at
    random each round, so its rank is independent of how the input arrived."""
    _validate(values, k)
    working = values[:]
    index = _rselect(working, 0, len(working) - 1, k - 1, counters)
    return working[index]


def _rselect(values: list, lo: int, hi: int, rank: int, counters: dict | None) -> int:
    while True:
        _track_round(counters)
        if lo == hi:
            return lo

        choice = random.randint(lo, hi)
        values[lo], values[choice] = values[choice], values[lo]
        split = _partition_around_front(values, lo, hi, counters)

        local_rank = split - lo
        if rank == local_rank:
            return split
        elif rank < local_rank:
            hi = split - 1
        else:
            rank -= local_rank + 1
            lo = split + 1


# ── Validation & instrumentation helpers ───────────────────────────────────────

def _validate(values: list, k: int) -> None:
    if not values:
        raise ValueError("cannot select from an empty sequence")
    if not 1 <= k <= len(values):
        raise IndexError(f"k={k} out of range for length {len(values)}")


def new_counters() -> dict:
    return {"comparisons": 0, "rounds": 0}


def _track_comparison(counters: dict | None) -> None:
    if counters is not None:
        counters["comparisons"] += 1


def _track_round(counters: dict | None) -> None:
    if counters is not None:
        counters["rounds"] += 1


# ── Benchmarking utilities ────────────────────────────────────────────────────

def _bench_time(select_fn, data: list, k: int, runs: int) -> float:
    times = []
    for _ in range(runs):
        sample = data[:]
        t0 = time.perf_counter()
        select_fn(sample, k)
        times.append(time.perf_counter() - t0)
    return statistics.mean(times)


def run_time_benchmarks(sizes: tuple = (2000, 4000, 8000, 16000), runs: int = 5) -> dict:
    """Return nested dict: results[distribution][algorithm][n] = avg_seconds.
    The target rank k is always the median, ceil(n / 2)."""
    generators = {
        "random":   lambda n: random.sample(range(n * 10), n),
        "sorted":   lambda n: list(range(n)),
        "reverse":  lambda n: list(range(n, 0, -1)),
        "repeated": lambda n: [random.randint(0, max(1, n // 10)) for _ in range(n)],
    }
    algorithms = {"deterministic": deterministic_select, "randomized": randomized_select}

    results: dict = {}
    for dist, gen in generators.items():
        results[dist] = {algo: {} for algo in algorithms}
        for n in sizes:
            data = gen(n)
            k = (n + 1) // 2
            for algo, fn in algorithms.items():
                results[dist][algo][n] = _bench_time(fn, data, k, runs)
    return results


def run_instrumentation_benchmarks(sizes: tuple = (2000, 4000, 8000, 16000), runs: int = 5) -> dict:
    """Return nested dict: results[distribution][algorithm][n] = {comparisons, rounds},
    averaged across `runs` repetitions (both algorithms re-draw randomness each
    call: the deterministic grouping is fixed, but group boundaries interact
    with duplicate values, so even it is averaged for consistency)."""
    generators = {
        "random":   lambda n: random.sample(range(n * 10), n),
        "sorted":   lambda n: list(range(n)),
        "reverse":  lambda n: list(range(n, 0, -1)),
        "repeated": lambda n: [random.randint(0, max(1, n // 10)) for _ in range(n)],
    }
    algorithms = {"deterministic": deterministic_select, "randomized": randomized_select}

    results: dict = {}
    for dist, gen in generators.items():
        results[dist] = {algo: {} for algo in algorithms}
        for n in sizes:
            data = gen(n)
            k = (n + 1) // 2
            for algo, fn in algorithms.items():
                agg = {"comparisons": [], "rounds": []}
                for _ in range(runs):
                    c = new_counters()
                    fn(data[:], k, c)
                    agg["comparisons"].append(c["comparisons"])
                    agg["rounds"].append(c["rounds"])
                results[dist][algo][n] = {key: statistics.mean(vals) for key, vals in agg.items()}
    return results


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── Correctness checks: every rank, several shapes, including duplicates ──
    test_cases = [
        ("random",    [5, 3, 8, 1, 9, 2, 7]),
        ("sorted",    [1, 2, 3, 4, 5]),
        ("reverse",   [5, 4, 3, 2, 1]),
        ("repeated",  [3, 3, 1, 3, 2, 1]),
        ("all_equal", [7, 7, 7, 7, 7]),
        ("single",    [42]),
        ("negatives", [-4, 10, 0, -4, 7, -1]),
    ]
    for label, sample in test_cases:
        expected = sorted(sample)
        for k in range(1, len(sample) + 1):
            d = deterministic_select(sample, k)
            r = randomized_select(sample, k)
            assert d == expected[k - 1], f"deterministic_select failed on {label}, k={k}"
            assert r == expected[k - 1], f"randomized_select failed on {label}, k={k}"
    print("All correctness checks passed (every rank, including duplicates).")

    for bad_values, bad_k in [([], 1), ([1, 2, 3], 0), ([1, 2, 3], 4)]:
        for fn in (deterministic_select, randomized_select):
            try:
                fn(bad_values, bad_k)
                raise AssertionError("expected an exception for invalid input")
            except (ValueError, IndexError):
                pass
    print("Edge-case validation (empty input, out-of-range k) passed.")

    # ── Quick benchmark ────────────────────────────────────────────────────────
    print("\nRunning timing benchmarks (median selection, n = 2000-16000)...")
    SIZES = (2000, 4000, 8000, 16000)
    results = run_time_benchmarks(sizes=SIZES)
    print(f"\n{'Distribution':<12} {'Algorithm':<16} " +
          "  ".join(f"n={s:>6}" for s in SIZES))
    for dist in ("random", "sorted", "reverse", "repeated"):
        for algo in ("deterministic", "randomized"):
            row = f"{dist:<12} {algo:<16} "
            row += "  ".join(f"{results[dist][algo][s]:>9.5f}s" for s in SIZES)
            print(row)

    print("\nRunning instrumentation benchmarks (comparisons, select rounds)...")
    inst = run_instrumentation_benchmarks(sizes=SIZES)
    for dist in ("random", "sorted", "reverse", "repeated"):
        for algo in ("deterministic", "randomized"):
            row = inst[dist][algo][SIZES[-1]]
            print(f"  {dist:<10} {algo:<14} n={SIZES[-1]:<6} "
                  f"comparisons={row['comparisons']:>10.0f}  rounds={row['rounds']:>5.1f}")
