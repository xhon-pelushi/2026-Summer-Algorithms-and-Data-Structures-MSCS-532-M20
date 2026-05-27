# Assignment 2 — Divide-and-Conquer Algorithms

Analysis and implementation of Merge Sort and Quick Sort as part of MSCS-532-M20.

## Contents

| File | Description |
|------|-------------|
| `sorting_algorithms.py` | Merge Sort and Quick Sort implementations with benchmarking |
| `Pelushi_Assignment2_MSCS532.docx` | Written analysis report (APA 7th edition) |
| `chart_time.png` | Execution time vs. input size across dataset types |
| `chart_memory.png` | Peak memory usage vs. input size |
| `chart_bar.png` | Execution time at n=10,000 across all combinations |

## Run

```bash
# From the repository root:
python3 assignment2/sorting_algorithms.py
```

Runs a correctness check and prints benchmark results for n = 500 to 10,000.

## Summary

| Algorithm | Time Complexity | Space Complexity |
|-----------|----------------|-----------------|
| Merge Sort | Θ(n log n) all cases | Θ(n) |
| Quick Sort | Θ(n log n) average, O(n²) worst | O(log n) average |
