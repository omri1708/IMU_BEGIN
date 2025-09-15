from __future__ import annotations
import os
from typing import List, Dict

class AnthropicDriver:
    def __init__(self, model: str):
        from anthropic import Anthropic  # type: ignore
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError('ANTHROPIC_API_KEY not set')
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, messages: List[Dict[str,str]]) -> Dict:
        # Flatten assistant/system to a simple user prompt for demo
        text = '\n'.join([m['content'] for m in messages if m['role'] in ('user','system')])
        res = self.client.messages.create(model=self.model, max_tokens=512, messages=[{"role":"user","content":text}])
        out = ''.join([c.text for c in res.content if getattr(c,'type','')=='text'])
        usage = getattr(res,'usage',None)
        return {
            'text': out,
            'prompt_tokens': int(getattr(usage,'input_tokens',0) or 0),
            'completion_tokens': int(getattr(usage,'output_tokens',0) or 0),
        }
