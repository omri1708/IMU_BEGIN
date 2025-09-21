from __future__ import annotations
from typing import Dict, Any, List
import os
from alignment.attribution import compute_citations

class EvidenceGate:
    def __init__(self, allow_domains: List[str], nli_threshold: float = 0.72, require_provenance: bool = True,
                 nli_model: str | None = None):
        self.allow = set((allow_domains or []))
        self.thr = nli_threshold
        self.require = require_provenance
        self.nli = None
        # טוען NLI רק אם ביקשת במפורש (כדי לא להכריח transformers בתוך container)
        if os.getenv("NLI_REQUIRED", "0") == "1":
            try:
                from grounded.nli_model import NLIEstimator  # טעינה דינמית
                self.nli = NLIEstimator(nli_model)
            except Exception:
                self.nli = None

    def _allowed(self, src: str) -> bool:
        src = (src or '').lower()
        return any(src.endswith(d.lower()) for d in self.allow) if self.allow else True  # אם אין allowlist – אל תחסום

    def check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sources = payload.get('sources') or []
        if self.require and not sources:
            return {"ok": False, "reason": "no_provenance"}

        # בדיקת דומיינים
        for s in sources:
            if not self._allowed((s.get('domain') or s.get('url') or '').split('/')[-1]):
                return {"ok": False, "reason": "domain_not_allowed", "bad": s}

        answer = (payload.get('answer') or '').strip()
        # חישוב ציטוטים/כיסוי ללא תלות ב-NLI
        cits = compute_citations(answer, sources)
        coverage = len([t for t in cits.get("per_token",[]) if t]) / max(1, len(cits.get("per_token",[])))

        # אם NLI כבוי – הסתמכות על coverage בלבד
        if self.nli is None:
            return {"ok": coverage >= self.thr, "entailment": None, "coverage": coverage, "citations": cits}

        # אחרת: NLI אמיתי (אם הותקן)
        texts = [s.get('text','') for s in sources]
        try:
            score, _ = self.nli.score(answer, texts)
        except Exception:
            score = 0.0
        ok = (score >= self.thr) and (coverage >= self.thr)
        return {"ok": ok, "entailment": score, "coverage": coverage, "citations": cits}
