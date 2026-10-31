"""RAG over resumes (Milestone 2 rebuilt).

* Chunking: each resume is split into section / role chunks, each prefixed with the
  candidate name and section so a chunk is self-describing.
* Retrieval: bi-encoder ``all-MiniLM-L6-v2`` embeddings in a FAISS inner-product index
  (cosine similarity on normalised vectors), persisted in ``vector_store/``.
* Reranking: cross-encoder ``ms-marco-MiniLM-L-6-v2`` re-scores the top hits.

The same bi-encoder + cross-encoder pattern as the course's Milestone-2 notebook.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .config import EMBED_MODEL, RERANK_MODEL, VECTOR_DIR
from .resume_store import list_resume_files, load_profiles


@dataclass
class Hit:
    candidate_id: str
    name: str
    section: str
    text: str
    score: float           # cosine similarity (bi-encoder)
    rerank_score: float | None = None

    def to_dict(self) -> dict:
        return {"candidate_id": self.candidate_id, "name": self.name, "section": self.section,
                "text": self.text, "similarity": round(self.score, 3),
                "rerank_score": None if self.rerank_score is None else round(self.rerank_score, 3)}


@lru_cache(maxsize=1)
def _bi_encoder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def _cross_encoder():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(RERANK_MODEL)


def chunk_resume(candidate_id: str, name: str, text: str) -> list[dict]:
    chunks: list[dict] = []
    sections = re.split(r"^(?=##\s)", text, flags=re.MULTILINE)
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        title = sec.splitlines()[0].lstrip("# ").strip()
        if not sec.startswith("##"):
            title = "Header"
        parts = re.split(r"^(?=###\s)", sec, flags=re.MULTILINE) if title.lower() == "experience" else [sec]
        for part in parts:
            part = part.strip()
            if not part or part == "## Experience":
                continue
            body = re.sub(r"^##\s*Experience\s*", "", part).strip()
            label = title if title.lower() != "experience" else "Experience: " + body.splitlines()[0].lstrip("# ")
            chunks.append({"candidate_id": candidate_id, "name": name, "section": label,
                           "text": f"Candidate: {name} | {label}\n{body}"})
    return chunks


class ResumeIndex:
    def __init__(self) -> None:
        self.index = None
        self.chunks: list[dict] = []
        self.embeddings: np.ndarray | None = None

    # ------------------------------------------------------------ build / load
    @staticmethod
    def _signature() -> str:
        h = hashlib.sha1(EMBED_MODEL.encode())
        for f in list_resume_files():
            h.update(f.name.encode())
            h.update(str(f.stat().st_mtime_ns).encode())
        return h.hexdigest()

    def load_or_build(self, force: bool = False) -> "ResumeIndex":
        import faiss

        sig = self._signature()
        meta_path, idx_path = VECTOR_DIR / "chunks.json", VECTOR_DIR / "resumes.faiss"
        if not force and meta_path.exists() and idx_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("signature") == sig:
                self.chunks = meta["chunks"]
                self.index = faiss.read_index(str(idx_path))
                self.embeddings = self.index.reconstruct_n(0, self.index.ntotal)
                return self
        self.chunks = [c for p in load_profiles().values() for c in chunk_resume(p.candidate_id, p.name, p.text)]
        emb = _bi_encoder().encode([c["text"] for c in self.chunks], batch_size=64, normalize_embeddings=True,
                                   show_progress_bar=False).astype("float32")
        self.index = faiss.IndexFlatIP(emb.shape[1])
        self.index.add(emb)
        self.embeddings = emb
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(idx_path))
        meta_path.write_text(json.dumps({"signature": sig, "model": EMBED_MODEL, "chunks": self.chunks}))
        return self

    def _embed_query(self, query: str) -> np.ndarray:
        return _bi_encoder().encode([query], normalize_embeddings=True).astype("float32")

    # ------------------------------------------------------------ queries
    def search(self, query: str, k: int = 8, rerank: bool = True, candidate_id: str | None = None,
               fetch_k: int = 40) -> list[Hit]:
        """Semantic search over resume chunks, optionally filtered to one candidate, reranked by a cross-encoder."""
        q = self._embed_query(query)
        if candidate_id:
            idxs = [i for i, c in enumerate(self.chunks) if c["candidate_id"] == candidate_id]
            with np.errstate(all="ignore"):  # spurious Accelerate BLAS warnings on macOS
                sims = (self.embeddings[idxs] @ q[0]) if idxs else np.array([])
            order = np.argsort(-sims)[:fetch_k]
            pairs = [(idxs[i], float(sims[i])) for i in order]
        else:
            scores, ids = self.index.search(q, min(fetch_k, len(self.chunks)))
            pairs = [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]
        hits = [Hit(self.chunks[i]["candidate_id"], self.chunks[i]["name"], self.chunks[i]["section"],
                    self.chunks[i]["text"], s) for i, s in pairs]
        if rerank and hits:
            ce = _cross_encoder().predict([(query, h.text) for h in hits])
            for h, s in zip(hits, ce):
                h.rerank_score = float(s)
            hits.sort(key=lambda h: h.rerank_score, reverse=True)
        return hits[:k]

    def candidate_similarity(self, query: str) -> dict[str, float]:
        """Semantic relevance of EVERY candidate to the query: 0.6*best chunk + 0.4*mean(top-3 chunks)."""
        with np.errstate(all="ignore"):  # spurious Accelerate BLAS warnings on macOS
            sims = self.embeddings @ self._embed_query(query)[0]
        per: dict[str, list[float]] = {}
        for c, s in zip(self.chunks, sims):
            per.setdefault(c["candidate_id"], []).append(float(s))
        out = {}
        for cid, vals in per.items():
            top = sorted(vals, reverse=True)[:3]
            out[cid] = 0.6 * top[0] + 0.4 * (sum(top) / len(top))
        return out


@lru_cache(maxsize=1)
def get_index() -> ResumeIndex:
    return ResumeIndex().load_or_build()
