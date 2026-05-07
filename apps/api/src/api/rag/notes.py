"""In-memory notes index with TF cosine retrieval and provenance.

This is the v0.1 stand-in for ``notes_index`` in pgvector. It:
  - reads a JSONL file of {topic_id, chunk, source} records,
  - tokenises each chunk,
  - vectorises against a corpus-derived vocabulary,
  - serves cosine-similarity top-k queries with provenance preserved.

Pure Python, zero ML deps. The interface (``search``) matches what a
neural-embeddings retriever will expose, so swapping in
``sentence-transformers`` + pgvector later is a one-class change.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]+\b")


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _TOKEN_RE.findall(text)]


@dataclass(slots=True)
class NoteChunk:
    """One indexable note with its source for provenance."""

    topic_id: str
    chunk: str
    source: str = ""


@dataclass(slots=True)
class RetrievedChunk:
    """Search result: a chunk plus its similarity score."""

    chunk: NoteChunk
    score: float


@dataclass
class NotesIndex:
    """Cosine-similarity TF retriever over a small notes corpus."""

    chunks: list[NoteChunk] = field(default_factory=list)
    _vocab: dict[str, int] = field(default_factory=dict)
    _vectors: list[list[float]] = field(default_factory=list)
    _norms: list[float] = field(default_factory=list)

    @classmethod
    def from_jsonl(cls, path: Path | str) -> NotesIndex:
        items: list[NoteChunk] = []
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            data = json.loads(line)
            items.append(
                NoteChunk(
                    topic_id=data["topic_id"],
                    chunk=data["chunk"],
                    source=data.get("source", ""),
                )
            )
        idx = cls(chunks=items)
        idx._build()
        return idx

    @classmethod
    def from_chunks(cls, chunks: list[NoteChunk]) -> NotesIndex:
        idx = cls(chunks=list(chunks))
        idx._build()
        return idx

    def _build(self) -> None:
        # Build vocabulary from all chunk text.
        vocab: dict[str, int] = {}
        for c in self.chunks:
            for tok in _tokenize(c.chunk):
                if tok not in vocab:
                    vocab[tok] = len(vocab)
        self._vocab = vocab

        # Vectorise each chunk + cache norms for cosine.
        self._vectors = [self._vectorise(c.chunk) for c in self.chunks]
        self._norms = [_norm(v) for v in self._vectors]

    def _vectorise(self, text: str) -> list[float]:
        counts = Counter(_tokenize(text))
        vec = [0.0] * len(self._vocab)
        for tok, n in counts.items():
            i = self._vocab.get(tok)
            if i is not None:
                vec[i] = float(n)
        return vec

    def search(
        self, query: str, *, k: int = 5, topic_id: str | None = None
    ) -> list[RetrievedChunk]:
        """Top-k results by cosine similarity. Optional ``topic_id`` filter."""
        if not self.chunks:
            return []
        q_vec = self._vectorise(query)
        q_norm = _norm(q_vec)
        if q_norm == 0:
            return []
        scored: list[RetrievedChunk] = []
        for chunk, vec, norm in zip(self.chunks, self._vectors, self._norms, strict=True):
            if topic_id is not None and chunk.topic_id != topic_id:
                continue
            if norm == 0:
                continue
            sim = _dot(q_vec, vec) / (q_norm * norm)
            scored.append(RetrievedChunk(chunk=chunk, score=sim))
        scored.sort(key=lambda r: r.score, reverse=True)
        return [r for r in scored[:k] if r.score > 0]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))
