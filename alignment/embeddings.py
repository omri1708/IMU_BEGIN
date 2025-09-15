from __future__ import annotations
from typing import List

class Embedder:
    def __init__(self, model: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        self.model = model
        self._pipe = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._pipe = SentenceTransformer(model)
        except Exception:
            self._pipe = None

    def encode(self, texts: List[str]):
        if self._pipe is None:
            # fallback: poor-man bag-of-words length
            return [[len(t)] for t in texts]
        return self._pipe.encode(texts, normalize_embeddings=True)
