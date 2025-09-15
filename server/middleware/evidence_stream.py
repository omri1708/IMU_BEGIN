from __future__ import annotations
import json
from fastapi import FastAPI, WebSocket
from grounded.evidence_gate import EvidenceGate
from alignment.attribution import compute_citations
import yaml
from pathlib import Path

POL = Path('policy/trustops.yaml')

def _pol():
    y = yaml.safe_load(POL.read_text()) if POL.exists() else {}
    g = y.get('grounding',{})
    return EvidenceGate(g.get('allow_domains',[]), g.get('nli_threshold',0.72), g.get('require_provenance',True), g.get('nli_model'))

async def gate_ws(app: FastAPI, path: str = '/ws-gated'):
    gate = _pol()

    @app.websocket(path)
    async def _ws(ws: WebSocket):
        await ws.accept()
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                data = {'answer': raw}
            res = gate.check({'answer': data.get('answer'), 'sources': data.get('sources',[])})
            if not res.get('ok'):
                await ws.send_text(json.dumps({'error':'EvidenceGate','details':res}))
                continue
            if 'sources' in data and 'citations' not in data:
                data['citations'] = compute_citations(str(data['answer']), list(data['sources']))
            await ws.send_text(json.dumps(data))
