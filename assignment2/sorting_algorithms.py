"""
MSCS-532 Assignment 2 — Divide-and-Conquer Algorithms
Implements Merge Sort and Quick Sort with performance benchmarking.
"""

import time
import tracemalloc
import random
import statistics


# ── Merge Sort ─────────────────────────────────────────────────────────────────

def merge_sort(arr):
    """Sort arr using merge sort; returns a new sorted list."""
    if len(arr) <= 1:
        return arr[:]
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return _merge(left, right)


def _merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


# ── Quick Sort ─────────────────────────────────────────────────────────────────

def quick_sort(arr):
    """Sort arr in-place using quick sort with randomized pivot selection."""
    _quick_sort(arr, 0, len(arr) - 1)


def _quick_sort(arr, low, high):
    if low < high:
        p = _partition(arr, low, high)
        _quick_sort(arr, low, p - 1)
        _quick_sort(arr, p + 1, high)


def _partition(arr, low, high):
    # Randomized pivot: swap a random element into the last position
    pivot_idx = random.randint(low, high)
    arr[pivot_idx], arr[high] = arr[high], arr[pivot_idx]
    pivot = arr[high]
    i = low - 1
    for j in range(low, high):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


# ── Benchmarking ───────────────────────────────────────────────────────────────

def _benchmark(func, data, runs=5):
    """Return (avg_time_seconds, avg_peak_memory_bytes)."""
    times = []
    mems = []
    for _ in range(runs):
        sample = data[:]
        tracemalloc.start()
        t0 = time.perf_counter()
        func(sample)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        times.append(elapsed)
        mems.append(peak)
    return statistics.mean(times), statistics.mean(mems)


def run_benchmarks(sizes=(500, 1000, 2500, 5000, 10000)):
    """Benchmark both algorithms across dataset types and sizes."""
    dataset_types = {
        "random": lambda n: random.sample(range(n * 10), n),
        "sorted": lambda n: list(range(n)),
        "reverse": lambda n: list(range(n, 0, -1)),
    }

    results = {}
    for dtype, gen in dataset_types.items():
        results[dtype] = {"merge_sort": {}, "quick_sort": {}}
        for n in sizes:
            data = gen(n)

            # Merge sort works on a copy internally; pass original
            ms_time, ms_mem = _benchmark(merge_sort, data)

            # Quick sort mutates in-place; _benchmark already copies
            qs_time, qs_mem = _benchmark(quick_sort, data)

            results[dtype]["merge_sort"][n] = (ms_time, ms_mem)
            results[dtype]["quick_sort"][n] = (qs_time, qs_mem)

    return results


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Quick correctness check
    sample = [38, 27, 43, 3, 9, 82, 10]
    ms_result = merge_sort(sample)
    qs_sample = sample[:]
    quick_sort(qs_sample)
    assert ms_result == sorted(sample), "Merge sort failed"
    assert qs_sample == sorted(sample), "Quick sort failed"
    print("Correctness check passed.")

    print("\nRunning benchmarks (this may take ~30 seconds)…")
    results = run_benchmarks()
    sizes = (500, 1000, 2500, 5000, 10000)

    header = f"{'Dataset':<10} {'Algorithm':<15} " + "  ".join(f"n={n:>6}" for n in sizes)
    print("\nExecution time (seconds):")
    print(header)
    for dtype in ("random", "sorted", "reverse"):
        for algo in ("merge_sort", "quick_sort"):
            row = f"{dtype:<10} {algo:<15} "
            row += "  ".join(f"{results[dtype][algo][n][0]:>10.6f}" for n in sizes)
            print(row)

    print("\nPeak memory (KB):")
    print(header)
    for dtype in ("random", "sorted", "reverse"):
        for algo in ("merge_sort", "quick_sort"):
            row = f"{dtype:<10} {algo:<15} "
            row += "  ".join(f"{results[dtype][algo][n][1]/1024:>10.1f}" for n in sizes)
            print(row)
