"""
app/agents/classification/seed.py

Bootstrap seed corpus: ≥1 (text, category) pair per category.
Used on first boot to give the classifier a non-trivial starting point
before any documents are uploaded.

These are realistic short excerpts — not lorem ipsum.
"""

from __future__ import annotations

from app.agents.classification.engine import CATEGORIES

SEED_CORPUS: list[tuple[str, str]] = [
    # ── Programming ──────────────────────────────────────────────────────────
    (
        "Python uses dynamic typing and garbage collection. Functions are first-class "
        "objects, enabling functional programming patterns alongside object-oriented "
        "design. The GIL limits true thread-level parallelism in CPython.",
        "Programming",
    ),
    (
        "Rust's ownership model eliminates entire classes of memory bugs at compile "
        "time. The borrow checker enforces that references do not outlive the data "
        "they point to, preventing use-after-free and data races without a GC.",
        "Programming",
    ),
    # ── Artificial Intelligence ───────────────────────────────────────────────
    (
        "Transformer architectures use self-attention to capture long-range "
        "dependencies in sequences. BERT pre-trains bidirectionally on masked "
        "language modelling; GPT uses causal left-to-right language modelling.",
        "Artificial Intelligence",
    ),
    (
        "Gradient descent minimises a differentiable loss function by iteratively "
        "updating weights in the direction of the negative gradient. Stochastic "
        "gradient descent samples mini-batches for efficiency on large datasets.",
        "Artificial Intelligence",
    ),
    # ── College ───────────────────────────────────────────────────────────────
    (
        "Calculus lecture notes: the chain rule states d/dx[f(g(x))] = f'(g(x)) · g'(x). "
        "Applications include optimisation, physics kinematics, and neural-network "
        "backpropagation.",
        "College",
    ),
    (
        "Assignment: compare the Keynesian and monetarist perspectives on fiscal "
        "stimulus. Discuss liquidity traps, the IS-LM model, and Milton Friedman's "
        "critique of fine-tuning.",
        "College",
    ),
    # ── Research ──────────────────────────────────────────────────────────────
    (
        "Abstract: We propose a novel attention mechanism that reduces quadratic "
        "complexity to linear by approximating the softmax kernel. Empirical results "
        "on long-document benchmarks show a 3× throughput improvement.",
        "Research",
    ),
    (
        "Related Work: Prior approaches to entity alignment in heterogeneous knowledge "
        "graphs rely on seed alignments and iterative label propagation. Our method "
        "dispenses with seeds by leveraging structural equivalence.",
        "Research",
    ),
    # ── Finance ───────────────────────────────────────────────────────────────
    (
        "A discounted cash flow model values an asset by summing expected future cash "
        "flows discounted at the risk-adjusted rate (WACC). Terminal value accounts "
        "for cash flows beyond the explicit forecast horizon.",
        "Finance",
    ),
    (
        "The Sharpe ratio measures excess return per unit of volatility: "
        "(R_p - R_f) / σ_p. A ratio above 1 is generally considered acceptable; "
        "hedge funds target ratios above 2.",
        "Finance",
    ),
    # ── Personal ──────────────────────────────────────────────────────────────
    (
        "Journal entry: Attended yoga class this morning — 45 minutes of vinyasa "
        "flow. Feeling more focused afterwards. Need to remember to book dentist "
        "appointment next week.",
        "Personal",
    ),
    (
        "Travel notes: Arrived in Lisbon. The pastéis de nata at Pastéis de Belém "
        "were extraordinary. Planning to visit Sintra tomorrow — leave early to beat "
        "the crowds.",
        "Personal",
    ),
    # ── Backend Development ───────────────────────────────────────────────────
    (
        "REST API design: use nouns for resources (/users, /orders), HTTP verbs for "
        "actions (GET, POST, PUT, DELETE). Return 201 Created with Location header "
        "for new resources; 204 No Content for successful deletions.",
        "Backend Development",
    ),
    (
        "PostgreSQL connection pooling with PgBouncer: session mode maintains a "
        "dedicated server connection per client session; transaction mode multiplexes "
        "connections — suitable for stateless API servers.",
        "Backend Development",
    ),
    # ── Frontend Development ──────────────────────────────────────────────────
    (
        "React 18 introduces concurrent rendering. The useTransition hook lets you "
        "mark state updates as non-urgent, keeping the UI responsive during expensive "
        "re-renders. Suspense boundaries handle loading states declaratively.",
        "Frontend Development",
    ),
    (
        "CSS custom properties (variables) enable design tokens: "
        "--color-primary: #6366f1; --spacing-4: 1rem. "
        "Combined with calc() and media queries, they replace preprocessor variables "
        "for most use cases.",
        "Frontend Development",
    ),
    # ── Networking ────────────────────────────────────────────────────────────
    (
        "TCP three-way handshake: SYN → SYN-ACK → ACK. The initial sequence number "
        "is randomly chosen to prevent sequence-number prediction attacks. "
        "TIME_WAIT ensures late packets are not misinterpreted by a new connection.",
        "Networking",
    ),
    (
        "BGP (Border Gateway Protocol) is the routing protocol of the internet. "
        "Autonomous systems exchange reachability information; path selection uses "
        "attributes like AS_PATH length, LOCAL_PREF, and MED.",
        "Networking",
    ),
    # ── Databases ─────────────────────────────────────────────────────────────
    (
        "B-tree indexes in PostgreSQL maintain sorted data in a balanced tree. "
        "Range queries benefit greatly from B-tree ordering; equality lookups on "
        "high-cardinality columns are also very efficient.",
        "Databases",
    ),
    (
        "Neo4j's Cypher query language uses ASCII-art graph patterns: "
        "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name. "
        "MERGE ensures idempotent node/relationship creation.",
        "Databases",
    ),
]

# Sanity check: every category has at least one seed
_seeded_categories = {label for _, label in SEED_CORPUS}
assert _seeded_categories == set(CATEGORIES), (
    f"Missing seed categories: {set(CATEGORIES) - _seeded_categories}"
)
