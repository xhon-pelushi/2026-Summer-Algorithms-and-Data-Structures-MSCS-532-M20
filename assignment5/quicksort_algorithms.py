"""
MSCS-532 Assignment 5 — Quicksort Algorithm: Implementation, Analysis, and Randomization
Implements Deterministic Quicksort (first-element pivot) and Randomized Quicksort
on top of one shared partition routine, with optional comparison/swap/recursion-
depth instrumentation used to empirically validate the theoretical time and space
complexity analysis.
"""

import random
import sys
import time
import statistics

# Deterministic Quicksort recurses to depth n-1 on sorted/reverse-sorted input
# (its worst case). Raise the limit so n up to ~10,000 doesn't hit RecursionError.
sys.setrecursionlimit(100_000)


# ── Shared partition routine ───────────────────────────────────────────────────
# Both algorithms below reduce to this one routine: it always treats values[start]
# as the pivot and partitions in a single left-to-right scan, without ever moving
# the pivot to the far end first. Everything less than the pivot gets pulled into
# a growing block immediately to its right; once the scan finishes, the pivot is
# swapped into the gap between that block and everything left untouched.

def _partition_around_front(values: list, start: int, end: int, counters: dict | None) -> int:
    pivot_value = values[start]
    boundary = start   # last index (inclusive) known to hold a value < pivot_value

    for cursor in range(start + 1, end + 1):
        _track_comparison(counters)
        if values[cursor] < pivot_value:
            boundary += 1
            values[boundary], values[cursor] = values[cursor], values[boundary]
            _track_swap(counters)

    values[start], values[boundary] = values[boundary], values[start]
    return boundary


# ── Deterministic Quicksort (first element as pivot) ──────────────────────────

def deterministic_quicksort(values: list, counters: dict | None = None) -> None:
    """Sort values in place, ascending; the first element of every subarray is the
    pivot. O(n log n) average case, O(n^2) worst case (sorted/reverse-sorted input),
    because a fixed pivot rule lets the input order alone decide every split."""
    _sort_fixed_pivot(values, 0, len(values) - 1, counters, depth=1)


def _sort_fixed_pivot(values: list, start: int, end: int, counters: dict | None, depth: int) -> None:
    if start < end:
        _track_depth(counters, depth)
        split = _partition_around_front(values, start, end, counters)
        _sort_fixed_pivot(values, start, split - 1, counters, depth + 1)
        _sort_fixed_pivot(values, split + 1, end, counters, depth + 1)


# ── Randomized Quicksort ───────────────────────────────────────────────────────

def randomized_quicksort(values: list, counters: dict | None = None) -> None:
    """Sort values in place, ascending; the pivot for every subarray is chosen
    uniformly at random before partitioning. O(n log n) expected, regardless of
    how the input happens to be arranged."""
    _sort_random_pivot(values, 0, len(values) - 1, counters, depth=1)


def _sort_random_pivot(values: list, start: int, end: int, counters: dict | None, depth: int) -> None:
    if start < end:
        _track_depth(counters, depth)
        # Swap a uniformly random element into the pivot slot (index `start`)
        # before handing off to the same partition routine the fixed-pivot
        # version uses. This is the one line that decouples split quality
        # from input order: the value occupying `start` going into the scan
        # below is now equally likely to be any element in [start, end].
        choice = random.randint(start, end)
        values[start], values[choice] = values[choice], values[start]

        split = _partition_around_front(values, start, end, counters)
        _sort_random_pivot(values, start, split - 1, counters, depth + 1)
        _sort_random_pivot(values, split + 1, end, counters, depth + 1)


# ── Instrumentation helpers ────────────────────────────────────────────────────
# counters is an optional dict of the form {"comparisons": 0, "swaps": 0, "max_depth": 0}.
# Passing None (the default) skips all bookkeeping so timing benchmarks measure
# only the sort itself.

def new_counters() -> dict:
    return {"comparisons": 0, "swaps": 0, "max_depth": 0}


def _track_comparison(counters: dict | None) -> None:
    if counters is not None:
        counters["comparisons"] += 1


def _track_swap(counters: dict | None) -> None:
    if counters is not None:
        counters["swaps"] += 1


def _track_depth(counters: dict | None, depth: int) -> None:
    if counters is not None and depth > counters["max_depth"]:
        counters["max_depth"] = depth


# ── Benchmarking utilities ────────────────────────────────────────────────────

def _bench_time(sort_fn, data: list, runs: int) -> float:
    """Run sort_fn on fresh copies of data and return the mean wall-clock time."""
    times = []
    for _ in range(runs):
        sample = data[:]
        t0 = time.perf_counter()
        sort_fn(sample)
        times.append(time.perf_counter() - t0)
    return statistics.mean(times)


def run_time_benchmarks(
    sizes: tuple = (1000, 2000, 4000, 8000),
    runs_normal: int = 3,
    runs_worst: int = 2,
) -> dict:
    """Return nested dict: results[distribution][algorithm][n] = avg_seconds.

    Fewer runs are used for sorted/reverse because Deterministic Quicksort is
    O(n^2) on those inputs and slow at the larger sizes.
    """
    generators = {
        "random":   (lambda n: random.sample(range(n * 10), n),                        runs_normal),
        "sorted":   (lambda n: list(range(n)),                                          runs_worst),
        "reverse":  (lambda n: list(range(n, 0, -1)),                                    runs_worst),
        "repeated": (lambda n: [random.randint(0, max(1, n // 10)) for _ in range(n)],  runs_normal),
    }
    results: dict = {}
    for dist, (gen, runs_det) in generators.items():
        results[dist] = {"deterministic": {}, "randomized": {}}
        for n in sizes:
            data = gen(n)
            results[dist]["deterministic"][n] = _bench_time(deterministic_quicksort, data, runs_det)
            results[dist]["randomized"][n] = _bench_time(randomized_quicksort, data, runs_normal)
    return results


def run_instrumentation_benchmarks(sizes: tuple = (1000, 2000, 4000, 8000)) -> dict:
    """Return nested dict: results[distribution][algorithm][n] = {comparisons, swaps, max_depth}.

    Deterministic counts are exact (single run, no randomness). Randomized
    counts are averaged over several runs since pivot choice varies.
    """
    randomized_runs = 5
    generators = {
        "random":   lambda n: random.sample(range(n * 10), n),
        "sorted":   lambda n: list(range(n)),
        "reverse":  lambda n: list(range(n, 0, -1)),
        "repeated": lambda n: [random.randint(0, max(1, n // 10)) for _ in range(n)],
    }
    results: dict = {}
    for dist, gen in generators.items():
        results[dist] = {"deterministic": {}, "randomized": {}}
        for n in sizes:
            data = gen(n)

            det_counters = new_counters()
            deterministic_quicksort(data[:], det_counters)
            results[dist]["deterministic"][n] = det_counters

            agg = {"comparisons": [], "swaps": [], "max_depth": []}
            for _ in range(randomized_runs):
                rand_counters = new_counters()
                randomized_quicksort(data[:], rand_counters)
                for key in agg:
                    agg[key].append(rand_counters[key])
            results[dist]["randomized"][n] = {key: statistics.mean(vals) for key, vals in agg.items()}
    return results


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── Correctness checks ────────────────────────────────────────────────────
    test_cases = [
        ("random",    [5, 3, 8, 1, 9, 2, 7]),
        ("sorted",    [1, 2, 3, 4, 5]),
        ("reverse",   [5, 4, 3, 2, 1]),
        ("repeated",  [3, 3, 1, 3, 2, 1]),
        ("empty",     []),
        ("single",    [42]),
        ("all_equal", [7, 7, 7, 7, 7]),
    ]
    for label, sample in test_cases:
        a, b = sample[:], sample[:]
        deterministic_quicksort(a)
        randomized_quicksort(b)
        assert a == sorted(sample), f"Deterministic Quicksort failed on {label}"
        assert b == sorted(sample), f"Randomized Quicksort failed on {label}"
    print("All correctness checks passed.")

    # ── Worst-case comparison-count check ─────────────────────────────────────
    # A fixed pivot forces a maximally unbalanced split at every step on sorted
    # or reverse-sorted input: comparisons = (n-1)+(n-2)+...+0 = n(n-1)/2.
    n = 500
    for label, data in [("sorted", list(range(n))), ("reverse", list(range(n, 0, -1)))]:
        c = new_counters()
        deterministic_quicksort(data[:], c)
        expected = n * (n - 1) // 2
        assert c["comparisons"] == expected, (label, c["comparisons"], expected)
        assert c["max_depth"] == n - 1, (label, c["max_depth"], n - 1)
    print(f"Worst-case formula n(n-1)/2 confirmed for n={n} on sorted and reverse input.")

    # ── Quick benchmark ────────────────────────────────────────────────────────
    print("\nRunning timing benchmarks (sizes 1000-8000)...")
    SIZES = (1000, 2000, 4000, 8000)
    results = run_time_benchmarks(sizes=SIZES)
    print(f"\n{'Distribution':<12} {'Algorithm':<16} " +
          "  ".join(f"n={s:>5}" for s in SIZES))
    for dist in ("random", "sorted", "reverse", "repeated"):
        for algo in ("deterministic", "randomized"):
            row = f"{dist:<12} {algo:<16} "
            row += "  ".join(f"{results[dist][algo][s]:>8.4f}s" for s in SIZES)
            print(row)

    print("\nRunning instrumentation benchmarks (comparisons, swaps, max recursion depth)...")
    inst = run_instrumentation_benchmarks(sizes=SIZES)
    for dist in ("random", "sorted", "reverse", "repeated"):
        for algo in ("deterministic", "randomized"):
            row = inst[dist][algo][SIZES[-1]]
            print(f"  {dist:<10} {algo:<14} n={SIZES[-1]:<6} "
                  f"comparisons={row['comparisons']:>10.0f}  "
                  f"swaps={row['swaps']:>9.0f}  "
                  f"max_depth={row['max_depth']:>6.0f}")
