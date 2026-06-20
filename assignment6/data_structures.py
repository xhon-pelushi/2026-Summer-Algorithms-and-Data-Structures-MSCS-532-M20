"""
MSCS-532 Assignment 6, Part 2 — Elementary Data Structures
Implements arrays, matrices, array-backed stacks and queues, singly linked
lists, and an optional rooted tree, each from scratch, plus benchmarking
utilities that measure the access/insertion trade-offs between the
array-based and linked-list-based structures.
"""

import random
import statistics
import time


# ── Dynamic Array ──────────────────────────────────────────────────────────────

class DynamicArray:
    """A resizable array built on a fixed-capacity Python list used purely as
    raw storage (no slicing/insert/pop helpers), so capacity growth and
    element shifting are implemented explicitly rather than borrowed."""

    def __init__(self, capacity: int = 8):
        self._capacity = max(1, capacity)
        self._size = 0
        self._store = [None] * self._capacity

    def __len__(self) -> int:
        return self._size

    def _grow(self) -> None:
        self._capacity *= 2
        bigger = [None] * self._capacity
        for i in range(self._size):
            bigger[i] = self._store[i]
        self._store = bigger

    def access(self, index: int):
        """O(1). Return the element at index."""
        if not 0 <= index < self._size:
            raise IndexError(index)
        return self._store[index]

    def append(self, value) -> None:
        """O(1) amortized. Insert at the end; occasionally O(n) on a resize."""
        if self._size == self._capacity:
            self._grow()
        self._store[self._size] = value
        self._size += 1

    def insert(self, index: int, value) -> None:
        """O(n) worst case: every element from index onward shifts right one
        slot to make room, even though the resize itself is amortized O(1)."""
        if not 0 <= index <= self._size:
            raise IndexError(index)
        if self._size == self._capacity:
            self._grow()
        for i in range(self._size, index, -1):
            self._store[i] = self._store[i - 1]
        self._store[index] = value
        self._size += 1

    def delete(self, index: int):
        """O(n) worst case: every element after index shifts left one slot
        to close the gap."""
        if not 0 <= index < self._size:
            raise IndexError(index)
        removed = self._store[index]
        for i in range(index, self._size - 1):
            self._store[i] = self._store[i + 1]
        self._size -= 1
        self._store[self._size] = None
        return removed

    def to_list(self) -> list:
        return [self._store[i] for i in range(self._size)]


# ── Matrix ─────────────────────────────────────────────────────────────────────

class Matrix:
    """A 2D array backed by a list of row lists."""

    def __init__(self, rows: int, cols: int, fill=0):
        self.rows = rows
        self.cols = cols
        self._data = [[fill] * cols for _ in range(rows)]

    def get(self, r: int, c: int):
        """O(1)."""
        return self._data[r][c]

    def set(self, r: int, c: int, value) -> None:
        """O(1)."""
        self._data[r][c] = value

    def insert_row(self, index: int, row_values: list) -> None:
        """O(rows + cols): building the new row costs O(cols), and every
        existing row reference at or after index shifts down one slot, O(rows)
        — shifting a row pointer is O(1) regardless of how many columns it has."""
        if len(row_values) != self.cols:
            raise ValueError(f"expected {self.cols} values, got {len(row_values)}")
        self._data.insert(index, list(row_values))
        self.rows += 1

    def delete_row(self, index: int) -> list:
        """O(rows): every row reference after index shifts up one slot."""
        removed = self._data.pop(index)
        self.rows -= 1
        return removed

    def to_list(self) -> list:
        return [row[:] for row in self._data]


# ── Array-backed Stack (LIFO) ──────────────────────────────────────────────────

class ArrayStack:
    """A stack backed directly by a Python list, operating only at the end of
    it so every operation touches a single slot."""

    def __init__(self):
        self._data: list = []

    def push(self, value) -> None:
        """O(1) amortized."""
        self._data.append(value)

    def pop(self):
        """O(1)."""
        if not self._data:
            raise IndexError("pop from an empty stack")
        return self._data.pop()

    def peek(self):
        """O(1)."""
        if not self._data:
            raise IndexError("peek from an empty stack")
        return self._data[-1]

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def __len__(self) -> int:
        return len(self._data)


# ── Array-backed Queue (FIFO), circular buffer ────────────────────────────────

class ArrayQueue:
    """A queue backed by a fixed-capacity array used as a circular buffer:
    head/tail indices wrap around with modular arithmetic instead of shifting
    elements, so both ends of the queue cost O(1) just like the stack above.
    Capacity doubles (amortized O(1)) when the buffer fills up."""

    def __init__(self, capacity: int = 8):
        self._capacity = max(1, capacity)
        self._store = [None] * self._capacity
        self._head = 0
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def _grow(self) -> None:
        old_capacity = self._capacity
        self._capacity *= 2
        bigger = [None] * self._capacity
        for i in range(self._size):
            bigger[i] = self._store[(self._head + i) % old_capacity]
        self._store = bigger
        self._head = 0

    def enqueue(self, value) -> None:
        """O(1) amortized."""
        if self._size == self._capacity:
            self._grow()
        tail = (self._head + self._size) % self._capacity
        self._store[tail] = value
        self._size += 1

    def dequeue(self):
        """O(1). No shifting: only the head index moves."""
        if self._size == 0:
            raise IndexError("dequeue from an empty queue")
        value = self._store[self._head]
        self._store[self._head] = None
        self._head = (self._head + 1) % self._capacity
        self._size -= 1
        return value

    def is_empty(self) -> bool:
        return self._size == 0


class NaiveListQueue:
    """A queue backed by a plain Python list with FIFO order enforced by
    popping index 0. Included only to measure, in Part 2's empirical
    analysis, the O(n) cost that the circular buffer above avoids: removing
    the front element forces every remaining element to shift left one slot."""

    def __init__(self):
        self._data: list = []

    def enqueue(self, value) -> None:
        """O(1) amortized."""
        self._data.append(value)

    def dequeue(self):
        """O(n): list.pop(0) shifts every remaining element left one slot."""
        if not self._data:
            raise IndexError("dequeue from an empty queue")
        return self._data.pop(0)

    def is_empty(self) -> bool:
        return len(self._data) == 0


# ── Singly Linked List ─────────────────────────────────────────────────────────

class _Node:
    __slots__ = ("value", "next")

    def __init__(self, value):
        self.value = value
        self.next = None


class SinglyLinkedList:
    """A singly linked list with both a head and tail pointer, so insertion
    at either end is O(1); only operations that must locate a node by
    position or value pay the O(n) traversal cost."""

    def __init__(self):
        self._head: _Node | None = None
        self._tail: _Node | None = None
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def insert_front(self, value) -> None:
        """O(1)."""
        node = _Node(value)
        node.next = self._head
        self._head = node
        if self._tail is None:
            self._tail = node
        self._size += 1

    def insert_back(self, value) -> None:
        """O(1), thanks to the maintained tail pointer."""
        node = _Node(value)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def access(self, index: int):
        """O(n): no random access, so the list must be walked from the head."""
        if not 0 <= index < self._size:
            raise IndexError(index)
        node = self._head
        for _ in range(index):
            node = node.next
        return node.value

    def search(self, value) -> int:
        """O(n). Return the index of the first matching node, or -1."""
        node = self._head
        index = 0
        while node is not None:
            if node.value == value:
                return index
            node = node.next
            index += 1
        return -1

    def delete_front(self):
        """O(1)."""
        if self._head is None:
            raise IndexError("delete_front from an empty list")
        removed = self._head.value
        self._head = self._head.next
        if self._head is None:
            self._tail = None
        self._size -= 1
        return removed

    def delete(self, value) -> bool:
        """O(n): the list must be walked to find the node and its predecessor.
        Returns True if a matching node was removed, False otherwise."""
        prev, node = None, self._head
        while node is not None:
            if node.value == value:
                if prev is None:
                    self._head = node.next
                else:
                    prev.next = node.next
                if node is self._tail:
                    self._tail = prev
                self._size -= 1
                return True
            prev, node = node, node.next
        return False

    def traverse(self) -> list:
        """O(n). Return all values in list order."""
        result = []
        node = self._head
        while node is not None:
            result.append(node.value)
            node = node.next
        return result


# ── Optional: Rooted Tree (left-child, right-sibling linked representation) ───

class TreeNode:
    """A node in a rooted tree represented with linked lists: rather than a
    list of children, each node points to its first child and its next
    sibling, so a node with k children is reachable by walking k
    right-sibling links from that first child (CLRS section 10.4)."""

    __slots__ = ("key", "parent", "first_child", "next_sibling")

    def __init__(self, key):
        self.key = key
        self.parent: "TreeNode | None" = None
        self.first_child: "TreeNode | None" = None
        self.next_sibling: "TreeNode | None" = None


class RootedTree:
    def __init__(self, root_key):
        self.root = TreeNode(root_key)

    def add_child(self, parent: TreeNode, child_key) -> TreeNode:
        """O(1) at the parent if a tail pointer were kept; here it is O(k) in
        the parent's existing child count, since the new child is linked in
        after walking to the end of the sibling chain."""
        child = TreeNode(child_key)
        child.parent = parent
        if parent.first_child is None:
            parent.first_child = child
        else:
            sibling = parent.first_child
            while sibling.next_sibling is not None:
                sibling = sibling.next_sibling
            sibling.next_sibling = child
        return child

    def preorder(self) -> list:
        """O(n). Visit a node, then each of its children's subtrees in turn."""
        return self._preorder_from(self.root)

    def _preorder_from(self, node: TreeNode) -> list:
        result = [node.key]
        child = node.first_child
        while child is not None:
            result.extend(self._preorder_from(child))
            child = child.next_sibling
        return result


# ── Benchmarking utilities ────────────────────────────────────────────────────

def bench_access(sizes: tuple = (1000, 2000, 4000, 8000, 16000), samples: int = 200) -> dict:
    """Average per-access time (microseconds), array vs. linked list, for
    random indices into a structure of size n."""
    results = {"array": {}, "linked_list": {}}
    for n in sizes:
        arr = DynamicArray(capacity=n)
        for v in range(n):
            arr.append(v)
        indices = [random.randint(0, n - 1) for _ in range(samples)]
        t0 = time.perf_counter()
        for i in indices:
            arr.access(i)
        results["array"][n] = (time.perf_counter() - t0) / samples * 1e6

        ll = SinglyLinkedList()
        for v in range(n):
            ll.insert_back(v)
        t0 = time.perf_counter()
        for i in indices:
            ll.access(i)
        results["linked_list"][n] = (time.perf_counter() - t0) / samples * 1e6
    return results


def bench_front_insert(sizes: tuple = (1000, 2000, 4000, 8000, 16000), inserts: int = 200) -> dict:
    """Average per-insert time (microseconds), array vs. linked list, for
    inserting at the front of a structure already holding n elements."""
    results = {"array": {}, "linked_list": {}}
    for n in sizes:
        arr = DynamicArray(capacity=n + inserts)
        for v in range(n):
            arr.append(v)
        t0 = time.perf_counter()
        for v in range(inserts):
            arr.insert(0, v)
        results["array"][n] = (time.perf_counter() - t0) / inserts * 1e6

        ll = SinglyLinkedList()
        for v in range(n):
            ll.insert_back(v)
        t0 = time.perf_counter()
        for v in range(inserts):
            ll.insert_front(v)
        results["linked_list"][n] = (time.perf_counter() - t0) / inserts * 1e6
    return results


def bench_queue_dequeue(sizes: tuple = (1000, 2000, 4000, 8000, 16000)) -> dict:
    """Average per-dequeue time (microseconds) while draining a queue of size
    n: naive list-shift queue vs. circular-buffer ArrayQueue."""
    results = {"naive": {}, "circular": {}}
    for n in sizes:
        naive = NaiveListQueue()
        for v in range(n):
            naive.enqueue(v)
        t0 = time.perf_counter()
        while not naive.is_empty():
            naive.dequeue()
        results["naive"][n] = (time.perf_counter() - t0) / n * 1e6

        circ = ArrayQueue(capacity=n)
        for v in range(n):
            circ.enqueue(v)
        t0 = time.perf_counter()
        while not circ.is_empty():
            circ.dequeue()
        results["circular"][n] = (time.perf_counter() - t0) / n * 1e6
    return results


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── DynamicArray correctness ───────────────────────────────────────────────
    arr = DynamicArray(capacity=2)
    for v in [10, 20, 30, 40]:
        arr.append(v)
    assert arr.to_list() == [10, 20, 30, 40]
    arr.insert(1, 99)
    assert arr.to_list() == [10, 99, 20, 30, 40]
    removed = arr.delete(0)
    assert removed == 10 and arr.to_list() == [99, 20, 30, 40]
    assert arr.access(0) == 99
    print("DynamicArray correctness passed.")

    # ── Matrix correctness ─────────────────────────────────────────────────────
    m = Matrix(2, 3)
    m.set(0, 0, 1)
    m.set(1, 2, 5)
    assert m.get(0, 0) == 1 and m.get(1, 2) == 5
    m.insert_row(1, [7, 8, 9])
    assert m.to_list() == [[1, 0, 0], [7, 8, 9], [0, 0, 5]]
    m.delete_row(0)
    assert m.to_list() == [[7, 8, 9], [0, 0, 5]]
    print("Matrix correctness passed.")

    # ── Stack correctness ──────────────────────────────────────────────────────
    s = ArrayStack()
    assert s.is_empty()
    for v in [1, 2, 3]:
        s.push(v)
    assert s.peek() == 3 and len(s) == 3
    assert s.pop() == 3 and s.pop() == 2 and s.pop() == 1
    assert s.is_empty()
    print("ArrayStack correctness passed.")

    # ── Queue correctness ──────────────────────────────────────────────────────
    q = ArrayQueue(capacity=2)
    for v in [1, 2, 3, 4, 5]:
        q.enqueue(v)
    drained = [q.dequeue() for _ in range(5)]
    assert drained == [1, 2, 3, 4, 5]
    assert q.is_empty()

    nq = NaiveListQueue()
    for v in [1, 2, 3]:
        nq.enqueue(v)
    assert [nq.dequeue() for _ in range(3)] == [1, 2, 3]
    print("ArrayQueue / NaiveListQueue correctness passed.")

    # ── Linked list correctness ────────────────────────────────────────────────
    ll = SinglyLinkedList()
    ll.insert_back(2)
    ll.insert_back(3)
    ll.insert_front(1)
    assert ll.traverse() == [1, 2, 3]
    assert ll.access(1) == 2
    assert ll.search(3) == 2 and ll.search(99) == -1
    assert ll.delete(2) is True
    assert ll.traverse() == [1, 3]
    assert ll.delete_front() == 1
    assert ll.traverse() == [3]
    print("SinglyLinkedList correctness passed.")

    # ── Rooted tree correctness ────────────────────────────────────────────────
    tree = RootedTree("A")
    b = tree.add_child(tree.root, "B")
    tree.add_child(tree.root, "C")
    tree.add_child(b, "D")
    tree.add_child(b, "E")
    assert tree.preorder() == ["A", "B", "D", "E", "C"]
    print("RootedTree correctness passed.")

    # ── Quick benchmark ────────────────────────────────────────────────────────
    SIZES = (1000, 2000, 4000, 8000, 16000)
    print("\nIndexed access time, array vs. linked list (microseconds/op):")
    access_results = bench_access(SIZES)
    for n in SIZES:
        print(f"  n={n:<7} array={access_results['array'][n]:>8.3f}us  "
              f"linked_list={access_results['linked_list'][n]:>10.3f}us")

    print("\nFront-insertion time, array vs. linked list (microseconds/op):")
    insert_results = bench_front_insert(SIZES)
    for n in SIZES:
        print(f"  n={n:<7} array={insert_results['array'][n]:>10.3f}us  "
              f"linked_list={insert_results['linked_list'][n]:>8.3f}us")

    print("\nQueue dequeue time, naive shift-queue vs. circular buffer (microseconds/op):")
    queue_results = bench_queue_dequeue(SIZES)
    for n in SIZES:
        print(f"  n={n:<7} naive={queue_results['naive'][n]:>10.3f}us  "
              f"circular={queue_results['circular'][n]:>8.3f}us")
