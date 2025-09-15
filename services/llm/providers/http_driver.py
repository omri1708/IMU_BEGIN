from __future__ import annotations
import os, json, urllib.request
from typing import List, Dict

class HttpDriver:
    ""Generic HTTP provider. Env:
    IMU_HTTP_LLM_ENDPOINT (required), IMU_HTTP_LLM_AUTH (optional header value)
    Request:  POST endpoint  {"messages": [...]}  →  {"text": str, "usage": {"prompt":int,"completion":int}}
    ""
    def __init__(self, endpoint: str | None = None):
        self.url = endpoint or os.getenv('IMU_HTTP_LLM_ENDPOINT')
        if not self.url:
            raise RuntimeError('IMU_HTTP_LLM_ENDPOINT not set')
        self.auth = os.getenv('IMU_HTTP_LLM_AUTH')

    def complete(self, messages: List[Dict[str,str]]) -> Dict:
        payload = json.dumps({'messages': messages}).encode('utf-8')
        req = urllib.request.Request(self.url, data=payload, headers={'Content-Type':'application/json'})
        if self.auth:
            req.add_header('Authorization', self.auth)
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode('utf-8'))
        usage = out.get('usage', {})
        return {'text': out.get('text',''), 'prompt_tokens': int(usage.get('prompt',0)), 'completion_tokens': int(usage.get('completion',0))}
