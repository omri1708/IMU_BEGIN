from __future__ import annotations
import os
from typing import List, Dict

class AzureOpenAIDriver:
    def __init__(self, deployment: str | None = None):
        import openai  # type: ignore
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION','2024-02-15-preview')
        if not (api_key and endpoint):
            raise RuntimeError('AZURE_OPENAI_API_KEY/AZURE_OPENAI_ENDPOINT not set')
        try:
            self.client = openai.AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint)
            self.deployment = deployment or os.getenv('AZURE_OPENAI_DEPLOYMENT')
            if not self.deployment:
                raise RuntimeError('AZURE_OPENAI_DEPLOYMENT not set')
            self.mode='client'
        except Exception as e:
            raise RuntimeError(f'Azure OpenAI init failed: {e}')

    def complete(self, messages: List[Dict[str,str]]) -> Dict:
        res = self.client.chat.completions.create(deployment_id=self.deployment, messages=messages)
        m = res.choices[0].message
        usage = res.usage or type('U',(),{'prompt_tokens':0,'completion_tokens':0})
        return {
            'text': (m.content if hasattr(m,'content') else ''),
            'prompt_tokens': int(getattr(usage,'prompt_tokens',0)),
            'completion_tokens': int(getattr(usage,'completion_tokens',0)),
        }
