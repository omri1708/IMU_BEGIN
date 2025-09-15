from __future__ import annotations
import os, json
from typing import List, Dict

class BedrockDriver:
    def __init__(self, model_id: str):
        import boto3  # type: ignore
        region = os.getenv('AWS_REGION','us-east-1')
        self.client = boto3.client('bedrock-runtime', region_name=region)
        self.model_id = model_id

    def complete(self, messages: List[Dict[str,str]]) -> Dict:
        text = '\n'.join([m['content'] for m in messages if m['role'] in ('user','system')])
        body = {"inputText": text, "textGenerationConfig": {"temperature": 0.3, "maxTokenCount": 512}}
        res = self.client.invoke_model(modelId=self.model_id, body=json.dumps(body))
        out = json.loads(res['body'].read())
        # body schema varies by model; best-effort extraction
        text = out.get('results',[{}])[0].get('outputText','') or out.get('output', '')
        return {'text': text, 'prompt_tokens': 0, 'completion_tokens': 0}
