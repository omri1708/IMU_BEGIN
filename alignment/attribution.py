from __future__ import annotations
from typing import List, Dict, Any
import re

try:
    from rapidfuzz import fuzz  # type: ignore
except Exception:
    fuzz = None

from .algo.lcs import lcs_spans
from .embeddings import Embedder

TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)

def _tokens(s: str) -> List[str]:
    return TOKEN_RE.findall(s or '')


def _best_source_for(sentence: str, sources: List[Dict[str,Any]]) -> Dict[str,Any] | None:
    best = None; best_score = -1.0
    for s in sources:
        txt = s.get('text') or ''
        score = 0.0
        if fuzz:
            score = float(fuzz.partial_ratio(sentence, txt))
        else:
            # heuristic: Jaccard on tokens
            a = set(_tokens(sentence.lower()))
            b = set(_tokens(txt.lower()))
            if a or b:
                score = 100.0 * len(a & b) / max(1, len(a | b))
        if score > best_score:
            best, best_score = s, score
    return best


def compute_citations(answer: str, sources: List[Dict[str,Any]]) -> Dict[str,Any]:
    ""Return per-token and per-chunk citations without provider dependence.
    sources: list of {id, text, meta}
    ""
    tokens = _tokens(answer)
    per_token = [None]*len(tokens)
    chunks: List[Dict[str,Any]] = []

    # 1) sentence-level assignment to sources
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip()) if answer else []
    sent_bounds = []
    ofs = 0
    for s in sentences:
        n = len(_tokens(s))
        sent_bounds.append((ofs, ofs+n, s))
        ofs += n

    for (i0, i1, stext) in sent_bounds:
        best = _best_source_for(stext, sources)
        if not best:
            continue
        for i in range(i0, i1): per_token[i] = best.get('id')

    # 2) refine with LCS spans per source
    for src in sources:
        txt = src.get('text') or ''
        spans = lcs_spans(answer, txt, min_len=16)
        for a0,a1,b0,b1 in spans:
            toks = _tokens(answer[:a0])
            start_tok = len(toks)
            span_toks = _tokens(answer[a0:a1])
            for i in range(start_tok, start_tok+len(span_toks)):
                if 0 <= i < len(per_token): per_token[i] = src.get('id')
            chunks.append({
                'answer_span': [a0,a1], 'source_id': src.get('id'), 'source_span': [b0,b1], 'method': 'lcs'
            })

    # 3) optional embeddings (sentence-level backup)
    try:
        emb = Embedder()
        a_vecs = emb.encode([x[2] for x in sent_bounds])
        s_vecs = emb.encode([s.get('text','') for s in sources])
        import numpy as np  # type: ignore
        for idx, vec in enumerate(a_vecs):
            sims = [float(np.dot(vec, sv)) if hasattr(sv, '__len__') else 0.0 for sv in s_vecs]
            j = int(np.argmax(sims)) if sims else -1
            if j >= 0 and sims[j] > 0.6:
                i0,i1,_ = sent_bounds[idx]
                for i in range(i0, i1): per_token[i] = sources[j].get('id')
                chunks.append({'answer_tokens': [i0,i1], 'source_id': sources[j].get('id'), 'method':'emb'})
    except Exception:
        pass

    return {'per_token': per_token, 'chunks': chunks}
