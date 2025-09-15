from __future__ import annotations
import os, json, pathlib

TABLE = pathlib.Path('.imu_runs/prices.json')

# Best-effort: if SDK keys exist, write a refreshed table hint; else keep prior/defaults

def refresh():
    prices = {}
    if os.getenv('OPENAI_API_KEY'):
        prices['openai'] = {'gpt-4o-mini': {'in': 0.00015, 'out': 0.0006}, 'gpt-4o': {'in':0.005, 'out':0.015}}
    if os.getenv('ANTHROPIC_API_KEY'):
        prices['anthropic'] = {'claude-3.5-sonnet': {'in':0.003,'out':0.015}}
    if os.getenv('GOOGLE_CLOUD_PROJECT'):
        prices['vertex'] = {'gemini-1.5-pro': {'in':0.0005,'out':0.0015}}
    if os.getenv('AWS_REGION'):
        prices['bedrock'] = {'anthropic.claude-3-sonnet-20240229-v1:0': {'in':0.003,'out':0.015}}
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(json.dumps(prices, indent=2), encoding='utf-8')
    return prices

if __name__=='__main__':
    print(refresh())
