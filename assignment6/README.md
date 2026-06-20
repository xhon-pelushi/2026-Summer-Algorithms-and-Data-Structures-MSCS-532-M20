# Assignment 6 — Medians and Order Statistics & Elementary Data Structures

Implementation and analysis of deterministic (Median of Medians) and randomized
(Randomized Quickselect) order-statistic selection, plus elementary data
structures (arrays, matrices, stacks, queues, singly linked lists, and an
optional rooted tree) as part of MSCS-532-M20.

## Contents

| File | Description |
|------|--------------|
| `selection_algorithms.py` | Deterministic Median-of-Medians select, Randomized Quickselect, comparison/round instrumentation, and benchmarking utilities |
| `data_structures.py` | DynamicArray, Matrix, ArrayStack, ArrayQueue (circular buffer), NaiveListQueue, SinglyLinkedList, RootedTree, and trade-off benchmarking utilities |
| `Pelushi_Assignment6_MSCS532.docx` | Written analysis report (APA 7th edition) |
| `chart_sel_time.png` | Median-selection execution time vs. input size for both algorithms across four distributions (2x2 grid) |
| `chart_sel_bar.png` | Median-selection execution time at n = 16,000 across all distributions |
| `chart_sel_comparisons.png` | Comparison count vs. n on random input, with linear (O(n)) reference lines for each algorithm |
| `chart_ds_access.png` | Indexed access time, array vs. linked list |
| `chart_ds_insert.png` | Front-insertion time, array vs. linked list |
| `chart_ds_queue.png` | Dequeue time, naive list-shift queue vs. circular-buffer queue |
| `benchmark_data.json` | Raw timing and instrumentation data behind the charts and report tables |

## Run

```bash
# From the repository root:
python3 assignment6/selection_algorithms.py
python3 assignment6/data_structures.py
```

Each script runs its own correctness checks (every rank/value, including
duplicates and edge cases) followed by a quick benchmark printout.

## Summary

### Part 1 — Selection Algorithms

| Algorithm | Time Complexity | Reason |
|-----------|-----------------|--------|
| Deterministic (Median of Medians) | Theta(n) worst case | T(n) <= T(n/5) + T(7n/10) + O(n); the pivot is guaranteed to fall within the middle 30% of the range regardless of input order, so 1/5 + 7/10 < 1 forces linear total work |
| Randomized Quickselect | O(n) expected | A random pivot lands in the middle half with probability >= 1/2, giving an expected geometric series O(n) + O(3n/4) + ... = O(n) |

- Space complexity: both copy the input once, O(n); after that, the main
  selection loop is iterative (no recursion). The deterministic version's
  only recursion is the nested median-of-medians sub-selection, bounded to
  O(log5 n) depth. The randomized version performs no recursive sub-calls.
- Unlike Assignment 5's deterministic Quicksort, neither selection algorithm
  shows a distribution-dependent blowup: median-of-medians inspects actual
  group values rather than a fixed position, so no input order can force its
  worst case, and randomized selection's pivot is independent of input order
  by construction.

### Empirical Results (n = 16,000, median selection)

| Distribution | Deterministic | Randomized |
|--------------|---------------|------------|
| Random | 12.40 ms | 2.78 ms |
| Sorted | 10.23 ms | 2.22 ms |
| Reverse-Sorted | 11.64 ms | 2.55 ms |
| Repeated Elements | 11.62 ms | 3.79 ms |

The deterministic version is consistently 3-5x slower across every
distribution — a real but bounded constant-factor cost of guaranteeing the
worst case, not an asymptotic difference.

### Part 2 — Elementary Data Structures

| Structure | Key Operations | Time Complexity |
|-----------|-----------------|------------------|
| DynamicArray | access / append / insert / delete | O(1) / O(1) amortized / O(n) / O(n) |
| Matrix | get,set / insert_row,delete_row | O(1) / O(rows) |
| ArrayStack | push / pop / peek | O(1) (amortized push) |
| ArrayQueue (circular buffer) | enqueue / dequeue | O(1) amortized |
| NaiveListQueue | enqueue / dequeue | O(1) amortized / O(n) |
| SinglyLinkedList | insert_front,insert_back / access,search,delete | O(1) / O(n) |
| RootedTree (left-child, right-sibling) | add_child / preorder | O(k) / O(n) |

### Empirical Trade-offs (n = 16,000)

| Comparison | Result |
|------------|--------|
| Indexed access | Array 0.042 us vs. Linked List 84.321 us (~2,000x) |
| Front insertion | Array 412.7 us vs. Linked List 0.258 us (~1,600x, opposite winner) |
| Queue dequeue | Naive list-shift 0.890 us vs. circular buffer ~0.1 us, naive grows with n |

Arrays and linked lists are near-exact mirror images of each other's
strengths: whichever operation matches a structure's "cheap end" runs in
O(1), and whichever doesn't costs O(n). The circular-buffer queue recovers
O(1) at both ends by decoupling logical position from physical storage via
modular arithmetic, avoiding the shift cost a naive array-backed queue pays
on every dequeue.
