from __future__ import annotations
from .llm_gateway import LLMGateway
from controlplane.ledger import add_cost

class CPGateway(LLMGateway):
    def complete(self, messages, candidates=None, budget_usd=None):
        res = super().complete(messages, candidates=candidates, budget_usd=budget_usd)
        try: add_cost(res.provider, res.cost_usd)
        except Exception: pass
        return res
