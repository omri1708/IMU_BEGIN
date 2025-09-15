from __future__ import annotations
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
app=FastAPI(title="Streaming")
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    q=asyncio.Queue(maxsize=16)  # back-pressure
    async def producer():
        for i in range(50):
            await q.put(f"chunk-{i}")
            await asyncio.sleep(0.01)
        await q.put(None)
    asyncio.create_task(producer())
    try:
        while True:
            item=await q.get()
            if item is None: break
            await ws.send_text(item)
            # (ack could be read here)
        await ws.send_text("[[END]]")
    except WebSocketDisconnect: return
