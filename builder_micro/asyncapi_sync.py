from __future__ import annotations
from pathlib import Path
import yaml

def sync(service_dir: str):
    p = Path(service_dir)/'asyncapi.yaml'
    if not p.exists(): return
    y = yaml.safe_load(p.read_text())
    # TODO: generate consumer/producer stubs from AsyncAPI
