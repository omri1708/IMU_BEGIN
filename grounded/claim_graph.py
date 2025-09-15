from __future__ import annotations
from typing import List, Dict, Any
from alignment.attribution import compute_citations

class ClaimGraph:
    def __init__(self, answer: str, sources: List[Dict[str,Any]]):
        self.answer = answer; self.sources = sources
        self.citations = compute_citations(answer, sources)
    def per_token_ids(self): return self.citations.get('per_token', [])
    def cover_ratio(self) -> float:
        toks = self.per_token_ids(); covered = sum(1 for t in toks if t)
        return covered / max(1, len(toks))
    def per_claim(self) -> List[Dict[str,Any]]:
        # naive split by sentences; map to top source id
        import re
        sents = re.split(r"(?<=[.!?])\s+", self.answer.strip()) if self.answer else []
        ids = self.per_token_ids();
        out = []
        o=0
        for s in sents:
            n = len(re.findall(r"\w+|[^\w\s]", s));
            seg = ids[o:o+n]; o+=n
            top = None
            if seg:
                from collections import Counter
                c = Counter(seg); c.pop(None, None); top = (c.most_common(1)[0][0] if c else None)
            out.append({'claim': s, 'source_id': top})
        return out
