"""
app/services/gazetteer.py

Shared technology gazetteer and alias map.
Used by:
  - app/agents/relationships/extract.py  (entity typing in file 05)
  - app/agents/kg_maintenance/resolution.py  (synonym merge in file 06)

Rules:
  - Both files import from THIS module — they never define their own lists.
  - TECH_NAMES is a frozenset of canonical technology names (lowercase).
  - ALIASES maps slug(alias) → slug(canonical) for synonym merging.
"""

from __future__ import annotations

from app.services.textnorm import slug

# --------------------------------------------------------------------------- #
# Canonical technology names (used for entity-type assignment in file 05)     #
# --------------------------------------------------------------------------- #

_RAW_TECH_NAMES: list[str] = [
    # Programming languages
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C", "C++",
    "C#", "Ruby", "Kotlin", "Swift", "Scala", "R", "MATLAB", "Julia",
    "Haskell", "Erlang", "Elixir", "PHP", "Perl", "Bash", "PowerShell",
    # Web frameworks / libraries
    "React", "Vue", "Angular", "Svelte", "Next.js", "Nuxt", "Remix",
    "FastAPI", "Django", "Flask", "Express", "NestJS", "Spring Boot",
    "Rails", "Laravel", "ASP.NET",
    # Databases
    "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Cassandra",
    "DynamoDB", "Elasticsearch", "InfluxDB", "CockroachDB", "Neo4j",
    "ChromaDB", "Pinecone", "Weaviate", "Qdrant", "Milvus",
    # Container / orchestration
    "Docker", "Kubernetes", "Helm", "Podman", "Containerd",
    # Cloud platforms
    "AWS", "GCP", "Azure", "Vercel", "Netlify", "Render", "Heroku",
    "Cloudflare", "DigitalOcean", "Fly.io",
    # DevOps / CI
    "Terraform", "Ansible", "GitHub Actions", "Jenkins", "GitLab CI",
    "CircleCI", "ArgoCD", "Pulumi",
    # ML / AI frameworks
    "TensorFlow", "PyTorch", "scikit-learn", "Keras", "JAX", "Hugging Face",
    "LangChain", "LlamaIndex", "Sentence Transformers", "spaCy", "NLTK",
    "OpenCV", "Pandas", "NumPy", "SciPy", "Matplotlib", "Plotly",
    # Message / streaming
    "Kafka", "RabbitMQ", "Celery", "Redis Streams", "NATS", "ZeroMQ",
    # API / protocols
    "REST", "GraphQL", "gRPC", "WebSockets", "HTTP", "HTTPS",
    "OAuth", "JWT", "OpenAPI", "Swagger",
    # Monitoring / observability
    "Prometheus", "Grafana", "Datadog", "Sentry", "OpenTelemetry",
    "Jaeger", "Zipkin",
    # Build / package
    "npm", "yarn", "pnpm", "pip", "Poetry", "Hatch", "Cargo", "Maven",
    "Gradle", "Webpack", "Vite", "esbuild", "Rollup",
    # Version control
    "Git", "GitHub", "GitLab", "Bitbucket",
    # Operating systems / infra
    "Linux", "Ubuntu", "Debian", "Alpine", "macOS", "Windows",
    "Nginx", "Apache", "Caddy", "HAProxy",
    # Storage
    "S3", "GCS", "Azure Blob", "MinIO",
    # Protocols / specs
    "TCP", "UDP", "DNS", "TLS", "SSL", "SSH",
]

# Frozenset of lowercase slugs for O(1) membership test
TECH_SLUGS: frozenset[str] = frozenset(slug(t) for t in _RAW_TECH_NAMES)

# Map raw lowercase name → canonical display name (for Neo4j node .name)
TECH_CANONICAL: dict[str, str] = {slug(t): t for t in _RAW_TECH_NAMES}


def is_technology(name: str) -> bool:
    """Return True if *name* is a known technology."""
    return slug(name) in TECH_SLUGS


# --------------------------------------------------------------------------- #
# Alias map: slug(alias) → slug(canonical)                                     #
# Used by KG maintenance (06) for synonym merging                              #
# --------------------------------------------------------------------------- #

_RAW_ALIASES: list[tuple[str, str]] = [
    # Kubernetes variants
    ("k8s", "kubernetes"),
    ("kube", "kubernetes"),
    # JavaScript variants
    ("js", "javascript"),
    ("ts", "typescript"),
    # Python
    ("py", "python"),
    # PostgreSQL variants
    ("postgres", "postgresql"),
    ("pg", "postgresql"),
    # MongoDB
    ("mongo", "mongodb"),
    # AWS
    ("amazon web services", "aws"),
    ("amazon s3", "s3"),
    ("amazon rds", "postgresql"),   # approximate, context-dependent
    # GCP
    ("google cloud platform", "gcp"),
    ("google cloud", "gcp"),
    # Azure
    ("microsoft azure", "azure"),
    # GitHub Actions
    ("gh actions", "github actions"),
    ("github action", "github actions"),
    # React
    ("reactjs", "react"),
    ("react.js", "react"),
    # Node.js
    ("nodejs", "node.js"),
    ("node", "node.js"),
    # Next.js
    ("nextjs", "next.js"),
    # Hugging Face
    ("hf", "hugging face"),
    ("transformers", "hugging face"),
    # scikit-learn
    ("sklearn", "scikit-learn"),
    # Sentence Transformers
    ("sentence transformers", "sentence transformers"),
    ("sbert", "sentence transformers"),
    # Docker Compose
    ("docker-compose", "docker"),
    ("docker compose", "docker"),
    # Celery
    ("celerybeat", "celery"),
    ("celery beat", "celery"),
]

# Slug-keyed alias lookup
ALIAS_MAP: dict[str, str] = {
    slug(alias): slug(canonical)
    for alias, canonical in _RAW_ALIASES
}


def resolve_alias(name: str) -> str:
    """
    Return the canonical slug for *name*, or its own slug if no alias exists.

    Used by KG maintenance entity resolution (06 §5.1 step a).
    """
    s = slug(name)
    return ALIAS_MAP.get(s, s)
