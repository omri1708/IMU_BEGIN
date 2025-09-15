from __future__ import annotations
import json
import subprocess
import os
import re
import pathlib
from services.llm.llm_gateway import LLMGateway

# Reads failing pytest output, asks LLM for a patch diff, applies to working tree and opens PR (if gh CLI)

def run_autopatch(test_output_path: str = '.imu_runs/junit.xml'):
    # 1) parse failures (simplified)
    text = pathlib.Path(test_output_path).read_text(encoding='utf-8') if pathlib.Path(test_output_path).exists() else ''
    if 'failure' not in text and 'error' not in text:
        print(json.dumps({'autopatch':'no_failures'}))
        return 0
    # 2) ask gateway for a patch suggestion
    gw = LLMGateway()
    prompt = {'role':'user','content': f"Tests failing; propose unified diff patch to fix. Context:\n{text[:4000]}"}
    res = gw.complete([prompt], tags={"task_type": "autopatch", "source": "ci/autopatch.py"})
    diff = res.text
    # 3) apply diff if looks like a patch
    if '--- ' in diff and '+++ ' in diff:
        p = subprocess.run(['git','apply','-p0','--reject','--whitespace=fix'], input=diff, text=True)
        if p.returncode != 0:
            print(json.dumps({'autopatch':'apply_failed'}))
            return 2
        subprocess.run(['git','checkout','-b','autopatch/quickfix'], text=True)
        subprocess.run(['git','add','-A'], text=True)
        subprocess.run(['git','commit','-m','autopatch: quick fix from failing tests'], text=True)
        if os.environ.get('GITHUB_TOKEN'):
            subprocess.run(['gh','pr','create','--fill'], text=True)
        print(json.dumps({'autopatch':'patch_applied'}))
        return 0
    print(json.dumps({'autopatch':'no_patch_suggested'}))
    return 3

if __name__=='__main__':
    run_autopatch()
