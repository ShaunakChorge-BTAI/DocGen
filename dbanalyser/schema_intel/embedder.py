"""
Schema Embedding Engine
========================
Converts schema objects (table names, column lists, DDL text) into
searchable vector representations using a dependency-free TF-IDF approach.

Optional: install `sentence-transformers` for semantic embeddings.
  pip install sentence-transformers

The embedding dimension is fixed at 256 for TF-IDF; 384 for MiniLM.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import List

log = logging.getLogger(__name__)

_STOP_WORDS = frozenset([
    "a", "an", "the", "of", "and", "or", "in", "on", "at", "to", "for",
    "is", "are", "was", "were", "be", "been", "being", "with", "by",
    "from", "as", "this", "that", "it", "not", "null", "nvarchar",
    "varchar", "int", "bigint", "smallint", "tinyint", "bit", "char",
    "text", "money", "float", "real", "decimal", "numeric", "date",
    "datetime", "datetime2", "uniqueidentifier", "varbinary", "image",
])

_VOCAB_SIZE = 256   # TF-IDF vector dimension


def _tokenize(text: str) -> List[str]:
    """Lower-case, split on non-alphanumeric, remove stop-words."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOP_WORDS]


def _hash_token(token: str, size: int = _VOCAB_SIZE) -> int:
    """Map a token string to a bucket index via FNV-1a hash."""
    h = 2166136261
    for ch in token.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h % size


def _tfidf_vector(tokens: List[str], size: int = _VOCAB_SIZE) -> List[float]:
    """
    Build a hashed TF vector of dimension ``size``.
    Values are normalised to unit length.
    """
    freq: dict[int, int] = {}
    for t in tokens:
        idx = _hash_token(t, size)
        freq[idx] = freq.get(idx, 0) + 1

    vec = [0.0] * size
    n   = max(len(tokens), 1)
    for idx, cnt in freq.items():
        # TF * IDF-proxy (log dampening on frequency)
        vec[idx] = (cnt / n) * (1 + math.log(1 + cnt))

    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_schema_object(
    object_type: str,
    object_name: str,
    parent_name: str = "",
    definition: str = "",
    use_transformers: bool = False,
) -> List[float]:
    """
    Embed a schema object into a float vector.

    Args:
        object_type     : "table" | "column" | "procedure" | "view" | "index"
        object_name     : name of the object
        parent_name     : parent object (e.g. table name for a column)
        definition      : DDL or description text
        use_transformers: if True, try sentence-transformers (MiniLM-L6-v2)

    Returns:
        List[float] vector.
    """
    text = f"{object_type} {object_name} {parent_name} {definition}"

    if use_transformers:
        try:
            from sentence_transformers import SentenceTransformer   # type: ignore
            _model = getattr(embed_schema_object, "_st_model", None)
            if _model is None:
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                embed_schema_object._st_model = _model  # cache
            return _model.encode(text).tolist()
        except ImportError:
            log.debug("sentence-transformers not installed — falling back to TF-IDF")

    return _tfidf_vector(_tokenize(text))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb   = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def vector_to_json(vec: List[float]) -> str:
    return json.dumps(vec)


def vector_from_json(s: str) -> List[float]:
    if not s or s.strip() in ("", "null", "[]"):
        return []
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return []
