# services/llm/gateway_runtime_budget.py
from __future__ import annotations
from services.llm.llm_gateway import LLMGateway, ProviderResult
from services.selfopt import budget_runtime

class RuntimeBudgetedGateway(LLMGateway):
    """בודק תקציב לפני כל קריאה ל-LLM (על בסיס llm_kpis.jsonl)."""
    def complete(self, messages, candidates=None, budget_usd=None, **kw) -> ProviderResult:
        # חסימה לפני הקריאה (אם עברנו את התקרה)
        budget_runtime.enforce()
        # העבר כל פרמטרים נוספים (למשל tags) לשכבה הבסיסית
        return super().complete(messages, candidates=candidates, budget_usd=budget_usd, **kw)
