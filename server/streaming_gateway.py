from __future__ import annotations
import asyncio, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from alignment.attribution import compute_citations

app = FastAPI(title='Streaming GW')

@app.websocket('/ws')
async def ws(ws: WebSocket):
    await ws.accept()
    try:
        i=0
        while True:
            data = await ws.receive_text()
            # echo with citation envelope (simulated)
            ans = {'answer': data, 'sources':[{'id':'s1','text':data}], 'citations': compute_citations(data, [{'id':'s1','text':data}])}
            await ws.send_text(json.dumps(ans))
            i+=1
    except WebSocketDisconnect:
        return
