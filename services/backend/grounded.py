from __future__ import annotations
from fastapi import APIRouter, Query
from grounded.claim_graph import ClaimGraph

# בחר gateway: אם יש לך את gateway_cp_wrap – הוא גם כותב ללדג’ר; אחרת gateway_budget/llm_gateway
try:
    from services.llm.gateway_cp_wrap import CPGateway as Gateway
except Exception:
    try:
        from services.llm.gateway_budget_wrap import BudgetedGateway as Gateway
    except Exception:
        from services.llm.llm_gateway import LLMGateway as Gateway

router = APIRouter()

@router.get("/grounded/demo")
def grounded_demo(
    q: str = Query(..., description="השאלה"),
    src_text: str = Query(..., description="טקסט מקור יחיד לגראונדינג"),
):
    sources = [{"id": "s1", "text": src_text}]
    messages = [
        {
            "role": "system",
            "content": (
                "You are a STRICT grounder. Answer ONLY from SOURCE below. "
                "If SOURCE does not contain enough info, respond exactly: 'insufficient evidence'. "
                "Keep it 1–2 sentences. If the question is in Hebrew – answer in Hebrew."
            ),
        },
        {
            "role": "user",
            "content": f"SOURCE:\n<<<\n{src_text}\n>>>\nQUESTION:\n{q}\nAnswer strictly from SOURCE.",
        },
    ]

    try:
        gw = Gateway()
        res = gw.complete(messages)
        answer = (res.text or "").strip()
        if not answer:
            answer = "insufficient evidence"
    except Exception:
        answer = "insufficient evidence"

    cg = ClaimGraph(answer, sources)
    return {
        "answer": answer,
        "sources": sources,
        "coverage": cg.cover_ratio(),
        "per_claim": cg.per_claim(),
    }
