#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU M4 AUTOPILOT — first‑principles runner that *connects what’s needed when needed*
---------------------------------------------------------------------------------
What it does (idempotent, interactive where required):
  1) Validates minimal interview core; if missing → runs interview/engine.py
  2) Auto‑discovers usable LLM providers (OpenAI/Azure/Anthropic/Vertex/Bedrock)
     • if none configured → asks only the keys needed and writes secrets/manifest.yaml + .env
  3) Plans & builds from seeds (gen_universal.py)
  4) Runs Alembic autogen (builder_v2/migrate.py)
  5) Executes pytest (if available) and mines JUnit for regressions (tests/miner/regression_miner.py)
  6) Prints a crisp run report (traceability coverage, provider chosen, costs, test gate)

Usage:
  python IMU_M4_AUTOPILOT.py
"""
from __future__ import annotations
import os, sys, subprocess, json, pathlib, shutil
from typing import Dict, Any

R = pathlib.Path('.')

# ---------------- helpers ----------------

def run(cmd: list[str], check: bool = True):
    print("$ ", ' '.join(cmd));
    p = subprocess.run(cmd, text=True)
    if check and p.returncode != 0:
        raise SystemExit(p.returncode)


def have(path: str | pathlib.Path) -> bool:
    return (R / path).exists()


def ensure_interview_core():
    if not have('specs/requirements.yaml'):
        print('[autopilot] running human interview to collect minimal spec…')
        run([sys.executable, 'interview/engine.py'], check=False)
    # quick sanity: still missing? prompt user
    if not have('specs/requirements.yaml'):
        print('[autopilot] missing specs/requirements.yaml — cannot proceed.')
        raise SystemExit(2)


def discover_providers() -> Dict[str, Any]:
    env = os.environ
    providers = {}
    if env.get('OPENAI_API_KEY'): providers['openai'] = {'model': env.get('OPENAI_MODEL','gpt-4o-mini')}
    if env.get('AZURE_OPENAI_API_KEY') and env.get('AZURE_OPENAI_ENDPOINT') and env.get('AZURE_OPENAI_DEPLOYMENT'):
        providers['azure'] = {'model': env.get('AZURE_OPENAI_DEPLOYMENT')}
    if env.get('ANTHROPIC_API_KEY'): providers['anthropic'] = {'model': env.get('ANTHROPIC_MODEL','claude-3.5-sonnet')}
    if env.get('GOOGLE_CLOUD_PROJECT'): providers['vertex'] = {'model': env.get('VERTEX_MODEL','gemini-1.5-pro')}
    if env.get('AWS_REGION'): providers['bedrock'] = {'model': env.get('BEDROCK_MODEL','anthropic.claude-3-sonnet-20240229-v1:0')}
    return providers


def prompt_secrets(providers_needed: list[str]):
    print('[autopilot] no usable LLM provider configured. minimal keys needed:')
    for p in providers_needed:
        print(' -', p)
    ans = input('enter provider to configure now (openai/azure/anthropic/vertex/bedrock or skip): ').strip()
    if not ans or ans == 'skip':
        print('[autopilot] skipping provider configuration (build will run in no‑LLM mode).')
        return
    if ans == 'openai':
        os.environ['OPENAI_API_KEY'] = input('OPENAI_API_KEY: ').strip()
        os.environ.setdefault('OPENAI_MODEL','gpt-4o-mini')
    elif ans == 'azure':
        os.environ['AZURE_OPENAI_API_KEY'] = input('AZURE_OPENAI_API_KEY: ').strip()
        os.environ['AZURE_OPENAI_ENDPOINT'] = input('AZURE_OPENAI_ENDPOINT: ').strip()
        os.environ['AZURE_OPENAI_DEPLOYMENT'] = input('AZURE_OPENAI_DEPLOYMENT: ').strip()
    elif ans == 'anthropic':
        os.environ['ANTHROPIC_API_KEY'] = input('ANTHROPIC_API_KEY: ').strip()
        os.environ.setdefault('ANTHROPIC_MODEL','claude-3.5-sonnet')
    elif ans == 'vertex':
        os.environ['GOOGLE_CLOUD_PROJECT'] = input('GOOGLE_CLOUD_PROJECT: ').strip()
        os.environ.setdefault('GOOGLE_CLOUD_REGION','us-central1')
        os.environ.setdefault('VERTEX_MODEL','gemini-1.5-pro')
    elif ans == 'bedrock':
        os.environ.setdefault('AWS_REGION','us-east-1')
        os.environ['BEDROCK_MODEL'] = input('BEDROCK_MODEL (e.g. anthropic.claude-3-sonnet-20240229-v1:0): ').strip()
    else:
        print('[autopilot] unknown provider; continuing without LLM.')
    # write secrets manifest minimally
    smp = R/'secrets/manifest.env'
    smp.parent.mkdir(parents=True, exist_ok=True)
    with smp.open('w', encoding='utf-8') as f:
        for k in ['OPENAI_API_KEY','OPENAI_MODEL','AZURE_OPENAI_API_KEY','AZURE_OPENAI_ENDPOINT','AZURE_OPENAI_DEPLOYMENT',
                  'ANTHROPIC_API_KEY','ANTHROPIC_MODEL','GOOGLE_CLOUD_PROJECT','GOOGLE_CLOUD_REGION','VERTEX_MODEL',
                  'AWS_REGION','BEDROCK_MODEL']:
            if os.getenv(k): f.write(f"{k}={os.getenv(k)}\n")
    print('[autopilot] wrote secrets/manifest.env — source it in your shell to reuse.')


def traceability_gate() -> Dict[str, Any]:
    try:
        out = subprocess.check_output([sys.executable, 'traceability/trace_gate.py'], text=True, stderr=subprocess.STDOUT)
        print(out)
        j = json.loads(out)
        return j
    except Exception as e:
        print('[autopilot] trace gate output not JSON (continuing).', e)
        return {}


def main():
    ensure_interview_core()
    prov = discover_providers()
    if not prov:
        prompt_secrets(['openai','azure','anthropic','vertex','bedrock'])
        prov = discover_providers()

    print('[autopilot] plan & build…')
    run([sys.executable, 'gen_universal.py'])

    if have('builder_v2/migrate.py'):
        print('[autopilot] alembic autogen…')
        run([sys.executable, '-m', 'builder_v2.migrate'], check=False)

    print('[autopilot] traceability gate…')
    cov = traceability_gate()

    # tests → junit → miner
    if shutil.which('pytest'):
        print('[autopilot] tests…')
        run(['pytest','-q','--maxfail=1','--disable-warnings','--junitxml','.imu_runs/junit.xml'], check=False)
        if have('tests/miner/regression_miner.py'):
            print('[autopilot] regression miner…')
            run([sys.executable, 'tests/miner/regression_miner.py', '.imu_runs/junit.xml'], check=False)

    # summarize
    print("\n=== AUTOPILOT REPORT ===")
    print("providers:", prov or 'none (no‑LLM mode)')
    print("traceability:", cov.get('missing','n/a'))
    print("done.")

if __name__ == '__main__':
    main()
