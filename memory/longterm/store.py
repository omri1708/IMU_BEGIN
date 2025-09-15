from __future__ import annotations
import sqlite3, json, time, pathlib

class LTStore:
    def __init__(self, path: str = '.imu_runs/longterm.db'):
        self.p = pathlib.Path(path); self.p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.p))
        self.db.execute('CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT, ts REAL, ttl REAL)')
        self.db.commit()
    def put(self, k: str, v: dict, ttl_s: float = 30*24*3600):
        self.db.execute('REPLACE INTO kv (k,v,ts,ttl) VALUES (?,?,?,?)', (k, json.dumps(v, ensure_ascii=False), time.time(), ttl_s)); self.db.commit()
    def get(self, k: str):
        cur = self.db.execute('SELECT v,ts,ttl FROM kv WHERE k=?', (k,)); row = cur.fetchone()
        if not row: return None
        v,ts,ttl = row; 
        if time.time() - ts > ttl: self.db.execute('DELETE FROM kv WHERE k=?',(k,)); self.db.commit(); return None
        return json.loads(v)
