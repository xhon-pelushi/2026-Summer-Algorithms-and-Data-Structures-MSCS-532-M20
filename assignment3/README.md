# Assignment 3 — Algorithm Efficiency and Scalability

Analysis and implementation of Randomized Quicksort and Hashing with Chaining as part of MSCS-532-M20.

## Contents

| File | Description |
|------|-------------|
| `algorithms.py` | Randomized Quicksort, Deterministic Quicksort, and Hash Table with Chaining |
| `Pelushi_Assignment3_MSCS532.docx` | Written analysis report (APA 7th edition) |
| `chart_qs_time.png` | Execution time vs. input size across four distributions (2×2 grid) |
| `chart_qs_bar.png` | Execution time at n = 5,000 across all distribution-algorithm combinations |
| `chart_ht_metrics.png` | Hash table chain length and operation time vs. load factor |

## Run

```bash
# From the repository root:
python3 assignment3/algorithms.py
```

Runs correctness checks for both sort variants and the hash table, then prints benchmark results for n = 500 to 5,000.

## Summary

### Randomized Quicksort

| Input Distribution | Randomized QS | Deterministic QS (first-element pivot) |
|-------------------|--------------|----------------------------------------|
| Random | O(n log n) expected | O(n log n) average |
| Sorted | O(n log n) expected | **O(n²) worst case** |
| Reverse-Sorted | O(n log n) expected | **O(n²) worst case** |
| Repeated Elements | O(n log n) expected | O(n log n) average |

At n = 5,000 on reverse-sorted input, Deterministic QS was ~100× slower than Randomized QS.

### Hash Table with Chaining

| Operation | Expected Time | Worst Case |
|-----------|--------------|------------|
| Insert | O(1 + α) | O(n) |
| Search | O(1 + α) | O(n) |
| Delete | O(1 + α) | O(n) |

- α = load factor = n/m (elements / slots)
- Dynamic resizing keeps α ∈ [0.20, 0.75], maintaining O(1) expected time
- Universal MAD hash function: h(k) = ((a·hash(k) + b) mod p) mod m
