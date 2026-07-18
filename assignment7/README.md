# Assignment 7 — Exploring Hash Tables and Their Practical Applications

A written discussion covering hash function design and collision-resolution
strategies:

- **Hash Functions and Their Impact** — characteristics of a good hash
  function, real-world failure modes (power-of-two clustering, hash-flooding
  DoS attacks), and the speed-vs-security trade-off illustrated through
  CPython's adoption of SipHash (PEP 456).
- **Open Addressing vs. Separate Chaining** — efficiency, memory, and
  complexity trade-offs between the two strategies, how real systems
  (Java `HashMap`, Redis, Python `dict`, Rust/Abseil `SwissTable`) choose
  between them, and how performance under each degrades as the load factor
  increases.

No source code — this assignment is a written paper only.

See `Pelushi_Assignment7_MSCS532.docx` for the full report.
