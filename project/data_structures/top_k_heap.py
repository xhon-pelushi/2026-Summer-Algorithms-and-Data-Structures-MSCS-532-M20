"""Binary max-heap for top-N queries (best sellers, low-stock alerts).

WHY A HEAP HERE?
Dashboard questions like "top 10 best sellers" need the k largest of n
values, with k tiny and n the whole catalog. Fully sorting costs
O(n log n); a heap does better in theory: build it bottom-up in O(n),
then pop just k times at O(log n) each, for O(n + k log n) total.
(The Phase 3 benchmarks tell an honest story about how this plays out
against Python's C-implemented sort — see the reports.)

HOW IT WORKS
The heap is ARRAY-BACKED: the tree lives implicitly in a Python list,
where the children of index i sit at 2i+1 and 2i+2 and its parent at
(i-1)//2. No node objects, no pointers — just index arithmetic. The
HEAP PROPERTY (every parent >= its children) is maintained by two
repair routines:
  - sift UP:   a newly appended element swaps upward until its parent
               is bigger (used by push).
  - sift DOWN: an element placed at the root swaps downward with its
               larger child until both children are smaller (used by
               pop and by bottom-up construction).

Entries are (priority, item) tuples compared as tuples, so ties on
priority fall back to the item, keeping results deterministic. A
min-heap behaviour (lowest stock first) is obtained by simply negating
priorities at the call site.
"""


class TopKHeap:
    """Array-backed binary max-heap of (priority, item) pairs.

    Complexity for n stored entries:
        push / pop : O(log n)
        peek : O(1)
        heapify (build from a list) : O(n)
        top_k : O(k log n) without disturbing the heap (works on a copy)
    Space: O(n).
    """

    def __init__(self, entries=None):
        self._heap = []
        if entries:
            # Bulk load: copy the entries then repair with bottom-up
            # heapify, which is O(n) — cheaper than n pushes, O(n log n).
            self._heap = [(p, i) for p, i in entries]
            self._heapify()

    def _heapify(self):
        """Bottom-up heap construction, O(n).

        Leaves are trivially valid heaps already, so we start at the
        LAST INTERNAL node (index n//2 - 1) and sift each internal node
        down. Working bottom-up means every subtree below the current
        node is already a valid heap when we fix it.
        """
        for idx in range(len(self._heap) // 2 - 1, -1, -1):
            self._sift_down(idx)

    def _sift_up(self, idx):
        """Bubble the element at idx toward the root until ordered."""
        while idx > 0:
            parent = (idx - 1) // 2  # implicit-tree parent index
            if self._heap[idx] > self._heap[parent]:
                # Child outranks parent: swap and continue upward.
                self._heap[idx], self._heap[parent] = (
                    self._heap[parent], self._heap[idx])
                idx = parent
            else:
                break  # heap property restored

    def _sift_down(self, idx):
        """Sink the element at idx until both children are smaller."""
        n = len(self._heap)
        while True:
            largest = idx
            # Compare against both children (2i+1, 2i+2) and remember
            # the largest of the three.
            for child in (2 * idx + 1, 2 * idx + 2):
                if child < n and self._heap[child] > self._heap[largest]:
                    largest = child
            if largest == idx:
                break  # parent already outranks both children: done
            self._heap[idx], self._heap[largest] = (
                self._heap[largest], self._heap[idx])
            idx = largest  # follow the displaced element down

    def push(self, priority, item):
        """Insert an entry. O(log n).

        Append at the bottom (the only place that keeps the tree
        complete), then sift up to restore the heap property.
        """
        self._heap.append((priority, item))
        self._sift_up(len(self._heap) - 1)

    def pop(self):
        """Remove and return the highest-priority (priority, item). O(log n).

        The maximum is always at index 0. To delete it without leaving
        a hole, the LAST element is moved into the root slot and sifted
        down to its correct place.
        """
        if not self._heap:
            raise IndexError("pop from an empty heap")
        top = self._heap[0]
        last = self._heap.pop()      # shrink the array by one
        if self._heap:
            self._heap[0] = last     # move last element to the root...
            self._sift_down(0)       # ...and repair downward
        return top

    def peek(self):
        """Highest-priority entry without removing it. O(1)."""
        if not self._heap:
            raise IndexError("peek at an empty heap")
        return self._heap[0]

    def top_k(self, k):
        """Return the k highest-priority entries, best first. O(k log n).

        NON-DESTRUCTIVE: pops from a shallow copy of the backing array,
        so a dashboard query never disturbs the live heap.
        """
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        # Build a throwaway heap sharing the same entries (tuples are
        # immutable, so a shallow list copy is safe).
        snapshot = TopKHeap.__new__(TopKHeap)
        snapshot._heap = self._heap[:]
        return [snapshot.pop() for _ in range(min(k, len(snapshot._heap)))]

    def __len__(self):
        return len(self._heap)
