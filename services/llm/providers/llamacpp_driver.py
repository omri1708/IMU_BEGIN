from __future__ import annotations
import os
from typing import List, Dict

class LlamaCppDriver:
    def __init__(self, model_path: str | None = None, n_ctx: int = 4096):
        from llama_cpp import Llama  # type: ignore
        self.model_path = model_path or os.getenv('LLAMACPP_MODEL_PATH')
        if not self.model_path:
            raise RuntimeError('LLAMACPP_MODEL_PATH not set')
        self.llm = Llama(model_path=self.model_path, n_ctx=n_ctx)

    def complete(self, messages: List[Dict[str,str]]) -> Dict:
        prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages]) + "\nASSISTANT:"
        out = self.llm(prompt=prompt, max_tokens=256, echo=False)
        text = out.get('choices',[{}])[0].get('text','')
        usage = out.get('usage',{})
        return {'text': text, 'prompt_tokens': int(usage.get('prompt_tokens',0) or 0), 'completion_tokens': int(usage.get('completion_tokens',0) or 0)}
