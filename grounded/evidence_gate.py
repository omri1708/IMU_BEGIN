from __future__ import annotations
from typing import Dict, Any, List
from .nli_model import NLIEstimator

class EvidenceGate:
    def __init__(self, allow_domains: List[str], nli_threshold: float = 0.72, require_provenance: bool = True,
                 nli_model: str | None = None):
        self.allow = set((allow_domains or []))
        self.thr = nli_threshold
        self.require = require_provenance
        self.nli = NLIEstimator(nli_model)

    def _allowed(self, src: str) -> bool:
        src = (src or '').lower()
        return any(src.endswith(d.lower()) for d in self.allow) if self.allow else False

    def check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sources = payload.get('sources') or []
        if self.require and not sources:
            return {"ok": False, "reason": "no_provenance"}
        # domain allowlist
        if self.allow:
            for s in sources:
                if not self._allowed((s.get('domain') or s.get('url') or '').split('/')[-1]):
                    return {"ok": False, "reason": "domain_not_allowed", "bad": s}
        # entailment (claim vs sources.text)
        claim = payload.get('claim') or payload.get('answer') or ''
        premises = [s.get('text', '') for s in sources if s.get('text')]
        score, meta = self.nli.score(claim, premises)
        return {"ok": (score >= self.thr), "entailment": score, "meta": meta}
