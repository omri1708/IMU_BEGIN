# services/backend/grounded.py
from __future__ import annotations
from fastapi import APIRouter, Query
from alignment.attribution import compute_citations

# בחר Gateway עם שרשרת נפילה
try:
    from services.llm.gateway_cp_wrap import CPGateway as Gateway
except Exception:
    try:
        from services.llm.gateway_budget_wrap import BudgetedGateway as Gateway
    except Exception:
        from services.llm.llm_gateway import LLMGateway as Gateway

router = APIRouter()

def _fallback_answer(src_text: str, q: str) -> str:
    # תשובה דטרמיניסטית מהמקור (למקרה שאין דרייבר/מפתח)
    sent = (src_text or "").strip().split(".")[0]
    return sent.strip() or "insufficient evidence"

@router.get("/grounded/demo")
def grounded_demo(
    q: str = Query("What are items?"),
    src_text: str = Query("Items are records with name and description, saved via /api/items.")
):
    sources = [{"id": "s1", "text": src_text}]

    # קריאת LLM – best-effort
    ans = None; provider="echo"; model="stub"; cost=0.0; lat=0; ok=False
    try:
        gw = Gateway()
        res = gw.complete([{"role": "user", "content": q}], candidates=None, budget_usd=None)
        provider = getattr(res, "provider", "echo")
        model    = getattr(res, "model", "stub")
        cost     = float(getattr(res, "cost_usd", 0.0))
        lat      = int(getattr(res, "latency_ms", 0))
        ok       = bool(getattr(res, "ok", False))
        ans      = (getattr(res, "text", "") or "").strip()
    except Exception:
        ans = None

    # אם אין תשובה/יש driver-error ⇒ נופלים לפולבק מהמֵקור (עדיין מייצרים citations)
    if not ans or ans.startswith("[driver-error]"):
        ans = _fallback_answer(src_text, q)
        ok = False

    cits = compute_citations(ans, sources)
    coverage = len([t for t in cits["per_token"] if t]) / max(1, len(cits["per_token"]))

    return {
        "answer": ans,
        "sources": sources,
        "citations": cits,
        "coverage": coverage,
        "provider": provider,
        "model": model,
        "cost_usd": round(cost, 6),
        "latency_ms": lat,
        "ok": ok,
    }

@router.get("/grounded/strict")
def grounded_strict(
    q: str = Query("Summarize Items"),
    src_text: str = Query("Items are records with name and description, saved via /api/items.")
):
    sources = [{"id":"s1","text":src_text}]
    messages = [
        {"role":"system",
         "content": "Answer STRICTLY and ONLY from SOURCE. If not enough info, reply exactly: 'insufficient evidence'. 1–2 sentences."},
        {"role":"user",
         "content": f"SOURCE:\n<<<\n{src_text}\n>>>\nQUESTION:\n{q}\nAnswer strictly from SOURCE."}
    ]
    gw = Gateway()
    res = gw.complete(messages)
    answer = (res.text or "").strip() or "insufficient evidence"
    cits = compute_citations(answer, sources)
    return {
        "answer": answer,
        "sources": sources,
        "citations": cits,
        "coverage": len([t for t in cits["per_token"] if t]) / max(1, len(cits["per_token"])),
        "provider": getattr(res,"provider","openai"),
        "model": getattr(res,"model","gpt-4o-mini"),
        "cost_usd": round(getattr(res,"cost_usd",0.0), 6),
        "latency_ms": int(getattr(res,"latency_ms",0)),
        "ok": bool(getattr(res,"ok",True)),
    }