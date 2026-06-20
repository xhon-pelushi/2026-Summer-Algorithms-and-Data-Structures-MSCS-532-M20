# Assignment 5 — Quicksort Algorithm: Implementation, Analysis, and Randomization

Implementation and analysis of Deterministic Quicksort (first-element pivot) and
Randomized Quicksort as part of MSCS-532-M20.

## Contents

| File | Description |
|------|--------------|
| `quicksort_algorithms.py` | Deterministic Quicksort, Randomized Quicksort, comparison/swap/recursion-depth instrumentation, and benchmarking utilities |
| `Pelushi_Assignment5_MSCS532.docx` | Written analysis report (APA 7th edition) |
| `chart_qs_time.png` | Execution time vs. input size for both algorithms across four distributions (2x2 grid) |
| `chart_qs_bar.png` | Execution time at n = 8,000 across all distribution-algorithm combinations (log scale) |
| `chart_qs_comparisons.png` | Comparison count vs. n on sorted input, plotted against the n(n−1)/2 and 1.39 n log₂(n) reference curves |
| `benchmark_data.json` | Raw timing and instrumentation data behind the charts and report tables |

## Run

```bash
# From the repository root:
python3 assignment5/quicksort_algorithms.py
```

Runs correctness checks (including an exact n(n−1)/2 comparison-count check for
sorted/reverse-sorted input), then prints timing and instrumentation benchmark
results for n = 1,000 to 8,000.

## Summary

### Time Complexity

| Case | Time Complexity | Reason |
|------|-----------------|--------|
| Best | Θ(n log n) | Balanced split (k ≈ n/2) gives T(n) = 2T(n/2) + Θ(n) |
| Worst | Θ(n²) | Maximally unbalanced split gives T(n) = T(n−1) + Θ(n), an arithmetic series |
| Average | Θ(n log n) | Expected comparisons ≈ 2n ln n ≈ 1.39 n log₂ n over random pivot choices |

- Space complexity: O(1) auxiliary (in-place partition); recursion stack is
  O(log n) on a balanced split, O(n) on a maximally unbalanced one.
- Deterministic Quicksort (first-element pivot) hits its Θ(n²) worst case on
  sorted and reverse-sorted input — measured comparison count matched the
  closed-form n(n−1)/2 exactly, and max recursion depth matched n − 1 exactly.
- Randomized Quicksort stayed within a small constant factor of n log n on
  every distribution tested, including the adversarial sorted/reverse-sorted
  inputs, because the pivot's rank is independent of input order.

### Empirical Results (n = 8,000)

| Distribution | Deterministic | Randomized |
|--------------|---------------|------------|
| Random | 8.62 ms | 10.36 ms |
| Sorted | 992.35 ms | 10.20 ms |
| Reverse-Sorted | 1,718.64 ms | 9.86 ms |
| Repeated Elements | 8.78 ms | 11.45 ms |

Randomization is roughly 100–200x faster than the deterministic pivot on
sorted/reverse-sorted input, and roughly on par elsewhere — exactly the
behavior the recurrence-based analysis predicts.
