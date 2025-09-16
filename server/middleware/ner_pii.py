from __future__ import annotations
import re
from typing import List, Dict

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\+?\d[\d\s-]{7,}\d")
_CARD  = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

class NER:
    def __init__(self):
        self.pipe = None
        try:
            from transformers import pipeline  # type: ignore
            self.pipe = pipeline(
                'token-classification',
                model='dslim/bert-base-NER',
                aggregation_strategy='simple',
                device=-1  # אל תנסה GPU; מפחית תקלות spawning
                )
        except Exception:
            self.pipe = None

    def find(self, text: str) -> List[Dict]:
        hits = []
        for m in _EMAIL.finditer(text or ''): hits.append({'start': m.start(), 'end': m.end(), 'class': 'email'})
        for m in _PHONE.finditer(text or ''): hits.append({'start': m.start(), 'end': m.end(), 'class': 'phone'})
        for m in _CARD.finditer(text or ''):  hits.append({'start': m.start(), 'end': m.end(), 'class': 'card'})
        if self.pipe is not None and text:
            try:
                ents = self.pipe(text)
                for e in ents:
                    lbl = (e.get('entity_group') or '').lower()
                    if lbl in ('per','person'): hits.append({'start': int(e['start']), 'end': int(e['end']), 'class': 'person'})
                    if lbl in ('loc','location'): hits.append({'start': int(e['start']), 'end': int(e['end']), 'class': 'address'})
                    if lbl in ('org','organization'): pass
            except Exception:
                pass
        return sorted(hits, key=lambda x: x['start'])

    def mask(self, text: str, role: str, policy: Dict) -> str:
        if not text: return text
        hits = self.find(text)
        out = []
        i = 0
        for h in hits:
            cls = h['class']
            allow = role in (policy.get('classes',{}).get(cls,{}).get('roles_allow',[]) or [])
            if allow:
                continue
            out.append(text[i:h['start']])
            mask = policy.get('classes',{}).get(cls,{}).get('mask','partial')
            if mask == 'last4' and (h['end']-h['start'])>=4:
                out.append('**** **** **** ' + text[h['end']-4:h['end']])
            else:
                out.append('***')
            i = h['end']
        out.append(text[i:])
        return ''.join(out)
