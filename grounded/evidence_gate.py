from __future__ import annotations
from typing import Dict, Any, List
import os
try:
    NLI_REQUIRED = os.getenv("NLI_REQUIRED", "0") == "1"
except Exception:
    NLI_REQUIRED = False

class EvidenceGate:
    def __init__(self, allow_domains: List[str], nli_threshold: float = 0.72, require_provenance: bool = True,
                  nli_model: str|None = None):

        self.allow = set((allow_domains or []))
        self.thr = nli_threshold
        self.require = require_provenance
        self._nli = None
        if NLI_REQUIRED:
            try:
                from grounded.nli_model import NLIEstimator
                self._nli = NLIEstimator(nli_model)
            except Exception:
                # אם לא הצלחנו לטעון מודל – נמשיך בלי NLI
                self._nli = None

    def _allowed(self, src: str) -> bool:
        src = (src or '').lower()
        return any(src.endswith(d.lower()) for d in self.allow) if self.allow else False

    def check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sources = payload.get('sources') or []
        answer = (payload.get("answer") or "").strip()
        if self.require and not sources:
            return {"ok": False, "reason": "no_provenance"}
        # domain allowlist
        if self.allow:
            for s in sources:
                if not self._allowed((s.get('domain') or s.get('url') or '').split('/')[-1]):
                    return {"ok": False, "reason": "domain_not_allowed", "bad": s}
        
        # אם אין NLI – נכשיר תשובה כל עוד יש מקורות; NLI “אמיתי” רץ רק כשהופעל במכוון
        if not self._nli:
            return {"ok": bool(sources), "entailment": None, "mode": "no-nli"}
        
        # entailment (claim vs sources.text)
        claim = payload.get('claim') or payload.get('answer') or ''
        premises = [s.get('text', '') for s in sources if s.get('text')]
        score, meta = self._nli.score(claim, premises)
        return {"ok": (score >= self.thr), "entailment": score, "meta": meta}
