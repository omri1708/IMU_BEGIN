from __future__ import annotations
import os
from typing import List, Dict

class VertexDriver:
    def __init__(self, model: str):
        from google.cloud import aiplatform  # type: ignore
        from vertexai.preview.generative_models import GenerativeModel  # type: ignore
        project = os.getenv('GOOGLE_CLOUD_PROJECT')
        location = os.getenv('GOOGLE_CLOUD_REGION','us-central1')
        if not project:
            raise RuntimeError('GOOGLE_CLOUD_PROJECT not set')
        aiplatform.init(project=project, location=location)
        self.model = GenerativeModel(model)

    def complete(self, messages: List[Dict[str,str]]) -> Dict:
        text = '\n'.join([m['content'] for m in messages])
        res = self.model.generate_content([text])
        out = getattr(res,'text',None) or (res.candidates[0].content.parts[0].text if getattr(res,'candidates',None) else '')
        # token usage optional
        return {'text': out, 'prompt_tokens': 0, 'completion_tokens': 0}
