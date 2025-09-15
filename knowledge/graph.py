from __future__ import annotations
import json, time, pathlib
class KGraph:
    def __init__(self, path="./.imu_kg.jsonl"): self.p=pathlib.Path(path)
    def add(self, kind:str, key:str, data:dict): self.p.parent.mkdir(parents=True, exist_ok=True); self.p.write_text((self.p.read_text(encoding="utf-8") if self.p.exists() else "")+json.dumps({"ts":time.time(),"kind":kind,"key":key,"data":data})+"\n", encoding="utf-8")
