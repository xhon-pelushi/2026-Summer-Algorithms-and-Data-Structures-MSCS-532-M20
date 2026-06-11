"""
MSCS-532 Assignment 4 — Heap Data Structures: Implementation, Analysis, and Applications
Implements Heapsort, a binary-heap Priority Queue with Task scheduling, and the
comparison sorts (Merge Sort, Randomized Quicksort) used for benchmarking.
"""

import random
import time
import statistics


# ── Heapsort ───────────────────────────────────────────────────────────────────

def max_heapify(arr: list, n: int, i: int) -> None:
    """Restore the max-heap property at index i, assuming both subtrees of i are heaps."""
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2

    if left < n and arr[left] > arr[largest]:
        largest = left
    if right < n and arr[right] > arr[largest]:
        largest = right

    if largest != i:
        arr[i], arr[largest] = arr[largest], arr[i]
        max_heapify(arr, n, largest)   # the swapped-in subtree may now violate the property


def build_max_heap(arr: list) -> None:
    """Convert arr into a max-heap in place. Bottom-up: O(n) total work."""
    n = len(arr)
    # Leaves (indices n//2 .. n-1) are already valid 1-element heaps, so start
    # at the last internal node and work back to the root.
    for i in range(n // 2 - 1, -1, -1):
        max_heapify(arr, n, i)


def heapsort(arr: list) -> None:
    """Sort arr in place, ascending, using Heapsort. O(n log n) in all cases."""
    n = len(arr)
    build_max_heap(arr)

    # Repeatedly move the current maximum (the root) to the end of the
    # unsorted prefix, shrink the heap by one, and re-heapify the root.
    for end in range(n - 1, 0, -1):
        arr[0], arr[end] = arr[end], arr[0]
        max_heapify(arr, end, 0)


# ── Comparison sorts (used for empirical benchmarking) ──────────────────────────

def merge_sort(arr: list) -> None:
    """Sort arr in place, ascending, using Merge Sort. O(n log n) in all cases."""
    if len(arr) <= 1:
        return
    mid = len(arr) // 2
    left, right = arr[:mid], arr[mid:]
    merge_sort(left)
    merge_sort(right)

    i = j = k = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            arr[k] = left[i]
            i += 1
        else:
            arr[k] = right[j]
            j += 1
        k += 1
    while i < len(left):
        arr[k] = left[i]
        i += 1
        k += 1
    while j < len(right):
        arr[k] = right[j]
        j += 1
        k += 1


def randomized_quicksort(arr: list) -> None:
    """Sort arr in place, ascending; pivot chosen uniformly at random. O(n log n) expected."""
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


# ── Task ─────────────────────────────────────────────────────────────────────

class Task:
    """A schedulable unit of work tracked by the priority queue."""

    __slots__ = ("task_id", "priority", "arrival_time", "deadline")

    def __init__(self, task_id: str, priority: int, arrival_time: float = 0.0, deadline: float | None = None):
        self.task_id = task_id
        self.priority = priority          # higher value == higher priority (max-heap)
        self.arrival_time = arrival_time  # simulation time at which the task became ready
        self.deadline = deadline          # optional simulation time by which it must finish

    def __repr__(self) -> str:
        return (f"Task(id={self.task_id!r}, priority={self.priority}, "
                f"arrival={self.arrival_time}, deadline={self.deadline})")


# ── Priority Queue (array-backed binary max-heap) ────────────────────────────

class PriorityQueue:
    """
    Max-priority queue of Task objects backed by a binary heap stored in a
    Python list. A parallel dictionary maps task_id -> current heap index so
    that increase_key/decrease_key can locate a task in O(1) before adjusting
    the heap in O(log n).
    """

    def __init__(self) -> None:
        self._heap: list[Task] = []
        self._pos: dict[str, int] = {}   # task_id -> index in self._heap

    # ── private helpers ───────────────────────────────────────────────────────

    def _swap(self, i: int, j: int) -> None:
        self._heap[i], self._heap[j] = self._heap[j], self._heap[i]
        self._pos[self._heap[i].task_id] = i
        self._pos[self._heap[j].task_id] = j

    def _sift_up(self, i: int) -> None:
        # Move the element at i up while it has higher priority than its parent.
        while i > 0:
            parent = (i - 1) // 2
            if self._heap[i].priority <= self._heap[parent].priority:
                break
            self._swap(i, parent)
            i = parent

    def _sift_down(self, i: int) -> None:
        # Move the element at i down while a child has higher priority.
        n = len(self._heap)
        while True:
            largest = i
            left, right = 2 * i + 1, 2 * i + 2
            if left < n and self._heap[left].priority > self._heap[largest].priority:
                largest = left
            if right < n and self._heap[right].priority > self._heap[largest].priority:
                largest = right
            if largest == i:
                break
            self._swap(i, largest)
            i = largest

    # ── public API ─────────────────────────────────────────────────────────────

    def is_empty(self) -> bool:
        """O(1). Return True if the queue holds no tasks."""
        return len(self._heap) == 0

    def peek(self) -> Task:
        """O(1). Return (without removing) the highest-priority task."""
        if self.is_empty():
            raise IndexError("peek from an empty priority queue")
        return self._heap[0]

    def insert(self, task: Task) -> None:
        """O(log n). Add task to the queue, maintaining the heap property."""
        self._heap.append(task)
        i = len(self._heap) - 1
        self._pos[task.task_id] = i
        self._sift_up(i)

    def extract_max(self) -> Task:
        """O(log n). Remove and return the highest-priority task."""
        if self.is_empty():
            raise IndexError("extract_max from an empty priority queue")

        top = self._heap[0]
        last = self._heap.pop()
        del self._pos[top.task_id]

        if self._heap:
            self._heap[0] = last
            self._pos[last.task_id] = 0
            self._sift_down(0)

        return top

    def increase_key(self, task_id: str, new_priority: int) -> None:
        """O(log n). Raise the priority of an existing task and re-heapify upward."""
        i = self._pos[task_id]
        if new_priority < self._heap[i].priority:
            raise ValueError("new_priority must be >= current priority for increase_key")
        self._heap[i].priority = new_priority
        self._sift_up(i)

    def decrease_key(self, task_id: str, new_priority: int) -> None:
        """O(log n). Lower the priority of an existing task and re-heapify downward."""
        i = self._pos[task_id]
        if new_priority > self._heap[i].priority:
            raise ValueError("new_priority must be <= current priority for decrease_key")
        self._heap[i].priority = new_priority
        self._sift_down(i)

    def __len__(self) -> int:
        return len(self._heap)


# ── Scheduler simulation ──────────────────────────────────────────────────────

def run_scheduler_simulation(tasks: list[Task], aging_interval: int = 3, aging_boost: int = 1) -> list[str]:
    """
    Simulate a single-server scheduler driven by the priority queue.

    Tasks "arrive" in order of their arrival_time (already sorted by the
    caller) and are pushed onto the queue. At each processing step the
    highest-priority ready task is extracted and run. Every `aging_interval`
    steps, all remaining waiting tasks have their priority increased by
    `aging_boost` (priority aging), preventing starvation of low-priority tasks.

    Returns the task_ids in the order they were executed.
    """
    pq = PriorityQueue()
    arrivals = sorted(tasks, key=lambda t: t.arrival_time)
    order: list[str] = []
    step = 0
    next_arrival = 0

    while next_arrival < len(arrivals) or not pq.is_empty():
        # Admit any tasks that have "arrived" by the current step.
        while next_arrival < len(arrivals) and arrivals[next_arrival].arrival_time <= step:
            pq.insert(arrivals[next_arrival])
            next_arrival += 1

        if pq.is_empty():
            step += 1
            continue

        if step > 0 and step % aging_interval == 0:
            for task in pq._heap:
                if task.priority < 10:
                    pq.increase_key(task.task_id, task.priority + aging_boost)

        run_task = pq.extract_max()
        order.append(run_task.task_id)
        step += 1

    return order


# ── Benchmarking utilities ────────────────────────────────────────────────────

def _bench(sort_fn, data: list, runs: int) -> float:
    """Run sort_fn on fresh copies of data and return the mean wall-clock time."""
    times = []
    for _ in range(runs):
        sample = data[:]
        t0 = time.perf_counter()
        sort_fn(sample)
        times.append(time.perf_counter() - t0)
    return statistics.mean(times)


def run_sort_benchmarks(sizes: tuple = (1000, 2500, 5000, 10000), runs: int = 3) -> dict:
    """Return nested dict: results[distribution][algorithm][n] = avg_seconds."""
    generators = {
        "random":   lambda n: random.sample(range(n * 10), n),
        "sorted":   lambda n: list(range(n)),
        "reverse":  lambda n: list(range(n, 0, -1)),
        "repeated": lambda n: [random.randint(0, max(1, n // 10)) for _ in range(n)],
    }
    algorithms = {
        "heapsort": heapsort,
        "merge_sort": merge_sort,
        "randomized_quicksort": randomized_quicksort,
    }

    results: dict = {}
    for dist, gen in generators.items():
        results[dist] = {algo: {} for algo in algorithms}
        for n in sizes:
            data = gen(n)
            for algo, fn in algorithms.items():
                results[dist][algo][n] = _bench(fn, data, runs)
    return results


def run_pq_benchmarks(sizes: tuple = (1000, 2000, 4000, 8000, 16000)) -> dict:
    """Measure average per-operation time (microseconds) for insert / extract_max
    / increase_key as a function of queue size n, demonstrating O(log n) growth."""
    results = {"insert": {}, "extract_max": {}, "increase_key": {}}

    for n in sizes:
        # Insert: time to insert n tasks into an initially empty queue.
        pq = PriorityQueue()
        t0 = time.perf_counter()
        for i in range(n):
            pq.insert(Task(f"t{i}", random.randint(0, 1_000_000)))
        results["insert"][n] = (time.perf_counter() - t0) / n * 1e6

        # increase_key: bump the priority of 1,000 random existing tasks.
        sample_ids = random.sample(list(pq._pos.keys()), min(1000, n))
        t0 = time.perf_counter()
        for tid in sample_ids:
            pq.increase_key(tid, 2_000_000)
        results["increase_key"][n] = (time.perf_counter() - t0) / len(sample_ids) * 1e6

        # extract_max: drain the queue, timing each extraction.
        t0 = time.perf_counter()
        while not pq.is_empty():
            pq.extract_max()
        results["extract_max"][n] = (time.perf_counter() - t0) / n * 1e6

    return results


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── Heapsort correctness ──────────────────────────────────────────────────
    test_cases = [
        ("random",   [5, 3, 8, 1, 9, 2, 7]),
        ("sorted",   [1, 2, 3, 4, 5]),
        ("reverse",  [5, 4, 3, 2, 1]),
        ("repeated", [3, 3, 1, 3, 2, 1]),
        ("empty",    []),
        ("single",   [42]),
    ]
    for label, arr in test_cases:
        a, b, c = arr[:], arr[:], arr[:]
        heapsort(a)
        merge_sort(b)
        randomized_quicksort(c)
        assert a == sorted(arr), f"Heapsort failed on {label}"
        assert b == sorted(arr), f"Merge Sort failed on {label}"
        assert c == sorted(arr), f"Randomized Quicksort failed on {label}"
    print("All sorting correctness checks passed.")

    # ── Priority queue correctness ────────────────────────────────────────────
    pq = PriorityQueue()
    assert pq.is_empty()
    for tid, prio in [("A", 3), ("B", 5), ("C", 1), ("D", 4), ("E", 2)]:
        pq.insert(Task(tid, prio))
    assert not pq.is_empty()
    pq.increase_key("C", 10)   # C should now be highest priority
    assert pq.peek().task_id == "C"
    pq.decrease_key("C", 0)    # C should now be lowest priority
    order = []
    while not pq.is_empty():
        order.append(pq.extract_max().task_id)
    assert order == ["B", "D", "A", "E", "C"], order
    print(f"Priority queue correctness passed. Extraction order: {order}")

    # ── Scheduler simulation demo ─────────────────────────────────────────────
    demo_tasks = [
        Task("T1", priority=2, arrival_time=0, deadline=10),
        Task("T2", priority=5, arrival_time=0, deadline=4),
        Task("T3", priority=1, arrival_time=1, deadline=20),
        Task("T4", priority=3, arrival_time=2, deadline=8),
        Task("T5", priority=1, arrival_time=2, deadline=15),
    ]
    exec_order = run_scheduler_simulation(demo_tasks)
    print(f"\nScheduler execution order: {exec_order}")

    # ── Quick benchmark ────────────────────────────────────────────────────────
    print("\nRunning sort benchmarks (sizes 1000-10000)…")
    results = run_sort_benchmarks(sizes=(1000, 2500, 5000, 10000), runs=2)
    sizes = (1000, 2500, 5000, 10000)
    print(f"\n{'Distribution':<12} {'Algorithm':<22} " +
          "  ".join(f"n={n:>6}" for n in sizes))
    for dist in ("random", "sorted", "reverse", "repeated"):
        for algo in ("heapsort", "merge_sort", "randomized_quicksort"):
            row = f"{dist:<12} {algo:<22} "
            row += "  ".join(f"{results[dist][algo][n]:>9.4f}s" for n in sizes)
            print(row)
