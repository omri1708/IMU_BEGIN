from __future__ import annotations
from .llm_gateway import LLMGateway
from controlplane.enforcer import check_and_add

class BudgetedGateway(LLMGateway):
    def complete(self, messages, candidates=None, budget_usd=None):
        res = super().complete(messages, candidates=candidates, budget_usd=budget_usd)
        chk = check_and_add(res.provider, res.cost_usd)
        if not chk['ok']:
            raise RuntimeError(f"Budget exceeded for {res.provider}: {chk}")
        return res
