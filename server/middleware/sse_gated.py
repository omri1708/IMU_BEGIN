from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import json, asyncio
from grounded.evidence_gate import EvidenceGate
from alignment.attribution import compute_citations
import yaml
from pathlib import Path

POL = Path('policy/trustops.yaml')

def _gate():
    y = yaml.safe_load(POL.read_text()) if POL.exists() else {}
    g = y.get('grounding',{})
    return EvidenceGate(g.get('allow_domains',[]), g.get('nli_threshold',0.72), g.get('require_provenance',True), g.get('nli_model'))

async def sse_stream(app: FastAPI, path: str = '/sse'):
    gate = _gate()
    @app.get(path)
    async def _sse(req: Request):
        async def gen():
            for i in range(10):
                data = {'answer': f'chunk-{i}', 'sources':[{'id':'s1','text':'chunk'}]}
                res = gate.check({'answer': data['answer'], 'sources': data['sources']})
                if res.get('ok'):
                    data['citations'] = compute_citations(data['answer'], data['sources'])
                    yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(0.05)
        return StreamingResponse(gen(), media_type='text/event-stream')
