from __future__ import annotations
import re
from typing import List, Dict
CUES = {
  "crm": ["lead","pipeline","contact","opportunity","sales","crm"],
  "commerce": ["product","cart","order","payment","checkout","inventory","sku","commerce","catalog"],
  "support": ["ticket","sla","support","csat","case","knowledge base","faq","helpdesk"],
  "internal": ["form","approval","dashboard","admin","workflow","tooling","internal"]
}
def induce_domains(text: str) -> List[str]:
    t=text.lower()
    scores={k:0 for k in CUES}
    for k, cues in CUES.items():
        for c in cues:
            if re.search(rf"\b{re.escape(c)}\b", t): scores[k]+=1
    # normalize and pick ≥1; allow hybrid
    ranked=sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top=[k for k,v in ranked if v==ranked[0][1] and v>0]
    return top or ["internal"]  # דיפולט
