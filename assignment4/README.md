# Assignment 4 — Heap Data Structures: Implementation, Analysis, and Applications

Implementation and analysis of Heapsort and a binary-heap Priority Queue (with Task
scheduling) as part of MSCS-532-M20.

## Contents

| File | Description |
|------|-------------|
| `heap_algorithms.py` | Heapsort, Merge Sort, Randomized Quicksort, `Task`, `PriorityQueue`, and the scheduler simulation |
| `Pelushi_Assignment4_MSCS532.docx` | Written analysis report (APA 7th edition) |
| `chart_sort_time.png` | Execution time vs. input size for Heapsort/Merge Sort/Randomized Quicksort across four distributions (2x2 grid) |
| `chart_sort_bar.png` | Execution time at n = 10,000 across all distribution-algorithm combinations |
| `chart_pq_ops.png` | Priority queue operation time (insert/extract_max/increase_key) vs. queue size |

## Run

```bash
# From the repository root:
python3 assignment4/heap_algorithms.py
```

Runs correctness checks for Heapsort, Merge Sort, Randomized Quicksort, and the
priority queue, demonstrates the scheduler simulation, then prints sort
benchmark results for n = 1,000 to 10,000.

## Summary

### Heapsort

| Case | Time Complexity | Reason |
|------|-----------------|--------|
| Best | Θ(n log n) | Build-heap is Θ(n); each of the n−1 extractions costs O(log n) regardless of input |
| Average | Θ(n log n) | Same structural argument; heap shape depends only on n |
| Worst | Θ(n log n) | Same structural argument; no input triggers worse than O(log n) per extraction |

- Space complexity: O(1) auxiliary (in-place); O(log n) recursion stack for `max_heapify`
- Heapsort is consistently ~30-40% slower than Merge Sort and Randomized Quicksort
  in constant factors, but is the only one of the three with both an unconditional
  Θ(n log n) worst case **and** O(1) extra space.

### Priority Queue (binary max-heap)

| Operation | Time Complexity |
|-----------|-----------------|
| `is_empty()` | O(1) |
| `peek()` | O(1) |
| `insert(task)` | O(log n) |
| `extract_max()` | O(log n) |
| `increase_key(id, p)` | O(log n) |
| `decrease_key(id, p)` | O(log n) |

- Backed by a Python list (array-based binary heap) plus a `task_id -> index`
  dictionary, so `increase_key`/`decrease_key` locate a task in O(1) before the
  O(log n) re-heapify.
- The scheduler simulation demonstrates priority aging: every few steps, all
  waiting tasks have their priority raised via `increase_key`, preventing
  starvation of low-priority tasks.
