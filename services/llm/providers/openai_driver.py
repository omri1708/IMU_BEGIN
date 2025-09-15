from __future__ import annotations
import os
from typing import List, Dict

class OpenAIDriver:
    def __init__(self, model: str):
        self.model = model
        try:
            import openai  # type: ignore
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise RuntimeError('OPENAI_API_KEY not set')
            # new-style client
            self.client = openai.OpenAI(api_key=api_key)
            self.mode = 'client'
        except Exception:
            # fallback to legacy global
            import openai  # type: ignore
            openai.api_key = os.getenv('OPENAI_API_KEY')
            self.openai = openai
            self.mode = 'legacy'

    def complete(self, messages: List[Dict[str, str]]) -> Dict:
        if self.mode == 'client':
            res = self.client.chat.completions.create(model=self.model, messages=messages)
            m = res.choices[0].message
            usage = res.usage or type('U',(),{'prompt_tokens':0,'completion_tokens':0})
            return {
                'text': (m.content if hasattr(m,'content') else ''),
                'prompt_tokens': int(getattr(usage,'prompt_tokens',0)),
                'completion_tokens': int(getattr(usage,'completion_tokens',0)),
            }
        else:
            res = self.openai.ChatCompletion.create(model=self.model, messages=messages)
            usage = res.get('usage',{})
            return {
                'text': res['choices'][0]['message']['content'],
                'prompt_tokens': int(usage.get('prompt_tokens',0)),
                'completion_tokens': int(usage.get('completion_tokens',0)),
            }
