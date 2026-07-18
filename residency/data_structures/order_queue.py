"""FIFO order-processing queue on a circular buffer.

WHY A QUEUE, AND WHY CIRCULAR?
Order fulfilment must be first-in-first-out — customers are served in
the order they checked out. The naive Python implementation,
list.pop(0), is O(n) per dequeue because every remaining element
shifts left one slot. A CIRCULAR BUFFER avoids the shifting entirely:
a fixed array plus a moving `head` index. Dequeuing just advances the
head; enqueuing writes at (head + size) % capacity, wrapping around to
reuse slots freed at the front. Both operations become O(1).

GROWTH
When the buffer is full it DOUBLES: the occupied slots are copied into
a new array in logical (head-first) order, "unrolling" the wrap. As
with the hash table and dynamic arrays generally, doubling makes the
amortized cost of enqueue O(1) even counting the copies.
"""


class Order:
    """A customer order travelling through the fulfilment pipeline.

    `status` tracks the lifecycle: 'pending' at checkout, then either
    'fulfilled' or 'failed' (out of stock) after processing.
    """

    __slots__ = ("order_id", "user_id", "skus", "status")

    def __init__(self, order_id, user_id, skus):
        # An empty order is a caller bug; reject it at the boundary.
        if not skus:
            raise ValueError("an order must contain at least one SKU")
        self.order_id = order_id
        self.user_id = user_id
        self.skus = list(skus)   # defensive copy: caller may reuse theirs
        self.status = "pending"

    def __repr__(self):
        return (f"Order(id={self.order_id}, user={self.user_id!r}, "
                f"skus={self.skus}, status={self.status!r})")


class OrderQueue:
    """Circular-buffer FIFO queue.

    Complexity: enqueue O(1) amortized, dequeue O(1), peek O(1).
    Space: O(capacity), at most 2x the high-water mark of pending orders.
    """

    def __init__(self, initial_capacity=8):
        if initial_capacity < 1:
            raise ValueError("initial_capacity must be >= 1")
        self._buffer = [None] * initial_capacity
        self._head = 0   # index of the OLDEST order (next to dequeue)
        self._size = 0   # number of orders currently waiting

    def enqueue(self, order):
        """Append an order to the back of the queue. Amortized O(1)."""
        if self._size == len(self._buffer):
            self._grow()  # full: double before writing
        # The back of the queue is `size` slots past the head, wrapped
        # around the end of the array by the modulo.
        tail = (self._head + self._size) % len(self._buffer)
        self._buffer[tail] = order
        self._size += 1

    def dequeue(self):
        """Remove and return the oldest pending order. O(1).

        No elements move: the head index simply advances (wrapping),
        which is the entire point of the circular layout.
        """
        if self._size == 0:
            raise IndexError("dequeue from an empty order queue")
        order = self._buffer[self._head]
        self._buffer[self._head] = None  # drop the reference (GC-friendly)
        self._head = (self._head + 1) % len(self._buffer)
        self._size -= 1
        return order

    def peek(self):
        """The oldest pending order without removing it. O(1)."""
        if self._size == 0:
            raise IndexError("peek at an empty order queue")
        return self._buffer[self._head]

    def _grow(self):
        """Double the buffer, unrolling the circular layout. O(n).

        The occupied slots may currently wrap around the array end
        (e.g. [C, D, -, A, B] with head=3). Copying them in logical
        order (A, B, C, D) into the front of the new array resets
        head to 0 and restores a simple layout.
        """
        old = self._buffer
        self._buffer = [None] * (len(old) * 2)
        for i in range(self._size):
            # Logical index i lives at physical (head + i) % capacity.
            self._buffer[i] = old[(self._head + i) % len(old)]
        self._head = 0

    def __len__(self):
        return self._size

    def __bool__(self):
        # Lets callers write `while queue:` to drain it.
        return self._size > 0
