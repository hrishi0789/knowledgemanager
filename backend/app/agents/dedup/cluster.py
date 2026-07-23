"""
app/agents/dedup/cluster.py

Star-contraction connected components algorithm (07 §5.4).

Input:  edges = list of (doc_id_a, doc_id_b) pairs passing Jaccard threshold
Output: dict mapping each doc_id → representative doc_id (cluster label)

Deterministic: representative = lexicographically minimum doc_id in component.
Star-contraction converges in O(log n) rounds on a finite graph.
Guard: cap at 50 iterations to detect non-convergence bugs.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

_MAX_ITERATIONS = 50


def star_contraction(edges: list[tuple[str, str]]) -> dict[str, str]:
    """
    Assign each node a cluster label equal to the representative doc_id
    of its connected component.

    Parameters
    ----------
    edges:
        Pairs of document IDs that are near-duplicates (Jaccard >= threshold).
        May contain (a, a) self-loops (they are ignored).

    Returns
    -------
    dict mapping doc_id → representative doc_id.
    Nodes with no edges are NOT included (they are singletons with cluster_id=NULL).
    """
    if not edges:
        return {}

    # Collect all unique nodes
    nodes: set[str] = set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)

    # Build adjacency list (undirected)
    adj: dict[str, set[str]] = {n: {n} for n in nodes}
    for a, b in edges:
        if a != b:
            adj[a].add(b)
            adj[b].add(a)

    # Initialise labels (each node labels itself)
    label: dict[str, str] = {n: n for n in nodes}

    for iteration in range(_MAX_ITERATIONS):
        changed = False
        new_label: dict[str, str] = {}

        # Large-Star: each node takes the minimum label in its closed neighbourhood
        for u in nodes:
            neighbours = adj[u]
            min_label = min(label[v] for v in neighbours)
            new_label[u] = min_label
            if min_label != label[u]:
                changed = True

        label = new_label

        if not changed:
            log.debug("Star-contraction converged", iterations=iteration + 1)
            break
    else:
        log.error(
            "Star-contraction did not converge",
            max_iterations=_MAX_ITERATIONS,
        )

    return label
