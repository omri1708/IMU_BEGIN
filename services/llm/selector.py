from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple
import json, pathlib, math

@dataclass
class ArmStats:
    n: int = 0
    success: float = 0.0
    lat_ewma: float = 1000.0
    cost_ewma: float = 0.01

class BanditSelector:
    def __init__(self, kpi_path: pathlib.Path, alpha: float = 0.5, beta: float = 0.4, gamma: float = 0.1):
        self.path = kpi_path
        self.alpha, self.beta, self.gamma = alpha, beta, gamma
        self.arms: Dict[Tuple[str,str], ArmStats] = {}
        self._bootstrap_from_log()

    def _bootstrap_from_log(self):
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
                key = (r.get('provider','?'), r.get('model','?'))
                st = self.arms.setdefault(key, ArmStats())
                st.n += 1
                st.success = 0.9 * st.success + 0.1 * (1.0 if r.get('ok') else 0.0)
                st.lat_ewma = 0.9 * st.lat_ewma + 0.1 * float(r.get('latency_ms', 1000.0))
                st.cost_ewma = 0.9 * st.cost_ewma + 0.1 * float(r.get('cost', 0.01))
            except Exception:
                continue

    def score(self, st: ArmStats) -> float:
        # higher is better; prefer success, penalize latency and cost
        inv_lat = 1.0 / max(1.0, st.lat_ewma)
        inv_cost = 1.0 / max(1e-6, st.cost_ewma)
        return self.beta * st.success + self.alpha * inv_lat + self.gamma * inv_cost

    def select(self, candidates: List[Dict[str,str]]) -> Dict[str,str]:
        if not candidates:
            return {"provider":"openai","model":"gpt-4o-mini"}
        best = None
        best_s = -1e9
        for c in candidates:
            st = self.arms.get((c['provider'], c['model']), ArmStats())
            s = self.score(st)
            if s > best_s:
                best_s, best = s, c
        return best or candidates[0]

    def update(self, provider: str, model: str, success: float, latency_ms: float, cost_usd: float):
        st = self.arms.setdefault((provider, model), ArmStats())
        st.n += 1
        st.success = 0.9 * st.success + 0.1 * float(success)
        st.lat_ewma = 0.9 * st.lat_ewma + 0.1 * float(latency_ms)
        st.cost_ewma = 0.9 * st.cost_ewma + 0.1 * float(cost_usd)
