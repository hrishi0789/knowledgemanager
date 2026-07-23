"""
app/agents/relationships/parse.py

Dependency graph construction and DP-ERE syntactic distance measurement.

Algorithm (05 §5.2):
  - Build an undirected token graph G where each edge is (token, token.head).
  - Map entity span to its head token (root of the noun phrase).
  - Compute shortest path length between two head tokens via BFS.
  - Formula: d(h_i, h_j) using networkx.shortest_path_length on undirected graph.
    This yields the same result as the LCA formula without LCA bookkeeping.
"""

from __future__ import annotations

import networkx as nx
import spacy
from spacy.tokens import Span, Token


def build_dependency_graph(sent: spacy.tokens.Span) -> nx.Graph:
    """
    Build an undirected dependency tree graph from a spaCy sentence.

    Nodes are token indices (int); edges connect each token to its syntactic head.
    """
    G: nx.Graph = nx.Graph()

    for token in sent:
        G.add_node(token.i)
        if token.head.i != token.i:   # skip root (self-loops)
            G.add_edge(token.i, token.head.i)

    return G


def syntactic_distance(graph: nx.Graph, head_i: int, head_j: int) -> int:
    """
    Return the shortest path length between two head tokens in the
    undirected dependency graph.

    Returns a large sentinel value (999) if the tokens are not connected
    (should not occur in a well-formed dependency tree).
    """
    if head_i == head_j:
        return 0
    try:
        return nx.shortest_path_length(graph, source=head_i, target=head_j)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return 999


def span_head_index(span: Span) -> int:
    """Return the token index of a noun-phrase span's syntactic root."""
    return span.root.i
