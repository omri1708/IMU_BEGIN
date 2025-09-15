from __future__ import annotations
import os, json
from services.llm.tokenizers import count_tokens

def sanity(model: str = 'gpt-4o-mini'):
    n = count_tokens('openai', model, 'hello world')
    return {'model': model, 'hello_tokens': n}

if __name__=='__main__':
    print(json.dumps(sanity()))
