from __future__ import annotations
import os, json
from typing import List, Tuple

class NLIEstimator:

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.device = device
        self.model_name = model_name
        self._mode = None  # 'cross' | 'zero'
        self._model = None
        self._tokenizer = None
        self._load()

    def _load(self):
        name = self.model_name or os.getenv('IMU_NLI_MODEL') or 'cross-encoder/nli-deberta-v3-base'
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            self._model = CrossEncoder(name, device=self.device or 'cpu')
            self._mode = 'cross'
            return
        except Exception:
            pass
        # fallback
        from transformers import pipeline  # type: ignore
        self._model = pipeline('zero-shot-classification', model='facebook/bart-large-mnli', device=-1)
        self._mode = 'zero'

    def score(self, hypothesis: str, premises: List[str]) -> Tuple[float, dict]:
        if not premises:
            return 0.0, {"mode": self._mode, "premises": 0}
        if self._mode == 'cross':
            pairs = [(p, hypothesis) for p in premises]
            try:
                import numpy as np
                logits = self._model.predict(pairs)  # shape [N,3] (contradiction, neutral, entailment)
                ent = logits[:, 2]
                ent_norm = (ent - ent.min()) / (ent.max() - ent.min() + 1e-9)
                return float(ent_norm.max()), {"mode": 'cross', "n": len(premises)}
            except Exception as e:
                return 0.0, {"mode": 'cross-error', "err": str(e)}
        else:  # zero-shot
            try:
                res = self._model(sequences=premises, candidate_labels=[hypothesis])
                # the pipeline returns a score per premise for the given label
                scores = [r['scores'][0] if isinstance(r, dict) else 0.0 for r in (res if isinstance(res, list) else [res])]
                return float(max(scores) if scores else 0.0), {"mode": 'zero', "n": len(scores)}
            except Exception as e:
                return 0.0, {"mode": 'zero-error', "err": str(e)}
