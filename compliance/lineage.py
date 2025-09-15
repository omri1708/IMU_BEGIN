from __future__ import annotations
from openlineage.client import OpenLineageClient

OL = OpenLineageClient.from_environment()

def emit_job(job: str, run: str):
    try: OL.emit_start(job, run)
    except Exception: pass
