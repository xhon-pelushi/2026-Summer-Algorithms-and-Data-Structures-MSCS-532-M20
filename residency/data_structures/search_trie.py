"""Trie (prefix tree) for product-name search and autocomplete.

WHY A TRIE HERE?
Autocomplete fires on every keystroke, so its cost matters more than any
other query in the storefront. A linear scan compares the prefix against
all n product names — O(n) per keystroke. A trie instead stores names
character by character along SHARED prefix paths, so answering a query
means walking one node per typed character and then collecting the
subtree below. The cost depends on the prefix length and the number of
matches — NOT on how many products the store has. That independence
from catalog size is the entire reason this structure exists.

HOW NAMES ARE INDEXED
Every word of a product name is inserted separately ("Wireless Mouse"
is indexed under both "wireless" and "mouse"), so a shopper typing
"mou" still finds it. Words are lowercased so search is
case-insensitive. Each node carries the set of SKUs whose word ENDS at
that node; a prefix query collects SKUs from the whole subtree.

THE TRADE-OFF
Tries buy speed with memory: one node per distinct prefix character.
The node count is tracked so the benchmarks can measure that cost
instead of guessing at it.
"""


class _TrieNode:
    """One node = one character position along some word's path.

    __slots__ keeps the many nodes a large catalog creates as small as
    Python allows.
    """

    __slots__ = ("children", "skus")

    def __init__(self):
        self.children = {}  # char -> child _TrieNode
        self.skus = set()   # SKUs whose indexed word terminates HERE


class SearchTrie:
    """Prefix tree over product-name words.

    Complexity for a word of length L with k results in the subtree:
        insert : O(L)
        prefix_search : O(L + subtree size), independent of total products
    Space: O(total characters inserted) nodes in the worst case.
    """

    def __init__(self):
        self._root = _TrieNode()  # empty root; every word starts here
        self._node_count = 1      # diagnostics: memory proxy
        self._word_count = 0      # diagnostics: distinct words indexed

    def insert(self, name, sku):
        """Index every word of a product name under the given SKU.

        Cost is O(len(name)) total: one node-step per character, creating
        nodes only where no other product has created them already —
        that sharing is what keeps the trie compact for real catalogs
        full of "Wireless X" / "Wireless Y" names.
        """
        if not name:
            raise ValueError("cannot index an empty product name")
        for word in name.lower().split():
            node = self._root
            # Walk down one character at a time, creating missing links.
            for ch in word:
                if ch not in node.children:
                    node.children[ch] = _TrieNode()
                    self._node_count += 1
                node = node.children[ch]
            # `node` is now the terminal node for this word.
            if not node.skus:
                self._word_count += 1  # first product to use this word
            node.skus.add(sku)

    def remove(self, name, sku):
        """Un-index a SKU from every word of its name. O(len(name)).

        Only the SKU entry is removed; empty nodes are deliberately left
        in place. Reclaiming them would require parent back-pointers or
        a recursive prune for very little gain, because in a live
        catalog another product almost always shares the branch.
        """
        for word in name.lower().split():
            node = self._root
            # for/else: the else block runs only if we walked the whole
            # word without falling off the tree (i.e., the word exists).
            for ch in word:
                if ch not in node.children:
                    break  # word was never indexed; nothing to remove
                node = node.children[ch]
            else:
                node.skus.discard(sku)

    def prefix_search(self, prefix, limit=None):
        """Return SKUs of every product with a word starting with prefix.

        Two phases:
          1. WALK: O(len(prefix)) steps down to the node representing
             the prefix. If any character is missing, no product
             matches and we return [] immediately.
          2. COLLECT: depth-first traversal of the subtree below that
             node, gathering the SKU sets found along the way. An
             explicit stack is used instead of recursion so a deep
             branch can never overflow Python's call stack.

        `limit` allows autocomplete to stop early after enough
        suggestions (the UI only shows a handful anyway).
        """
        prefix = prefix.lower().strip()
        if not prefix:
            return []  # an empty prefix would match the entire catalog

        # Phase 1: walk down to the prefix node.
        node = self._root
        for ch in prefix:
            if ch not in node.children:
                return []  # dead end: no word starts with this prefix
            node = node.children[ch]

        # Phase 2: DFS collection below the prefix node.
        results = []
        seen = set()   # a SKU can appear at several nodes; dedupe it
        stack = [node]
        while stack:
            current = stack.pop()
            # sorted() here makes result order deterministic: Python
            # randomizes set iteration order between processes, and a
            # search API should not return a different order each run.
            for sku in sorted(current.skus):
                if sku not in seen:
                    seen.add(sku)
                    results.append(sku)
                    if limit is not None and len(results) >= limit:
                        return results  # early exit: enough suggestions
            stack.extend(current.children.values())
        return results

    def stats(self):
        """Diagnostics for benchmarking: node and word counts."""
        return {"nodes": self._node_count, "words": self._word_count}
