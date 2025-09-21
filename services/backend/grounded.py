# services/backend/grounded.py
from __future__ import annotations
from fastapi import APIRouter, Query, Body
from alignment.attribution import compute_citations
import os

# בחר Gateway עם שרשרת נפילה
try:
    from services.llm.gateway_cp_wrap import CPGateway as Gateway
except Exception:
    try:
        from services.llm.gateway_runtime_budget import RuntimeBudgetedGateway as Gateway
    except Exception:
        try:
            from services.llm.gateway_budget_wrap import BudgetedGateway as Gateway
        except Exception:
            from services.llm.llm_gateway import LLMGateway as Gateway


router = APIRouter()
COVERAGE_MIN = float(os.getenv("EVIDENCE_COV_MIN", "0.8"))
gw = Gateway()


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
    ans = None; provider="echo"; model="stub"; cost=0.0; lat=0; ok=False  # noqa: E702
    try:
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
    CAP = float(os.getenv("MAX_COST_PER_CALL", "0.02"))
    ok = ok and (cost <= CAP)
    
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
    import os
    COVERAGE_MIN = float(os.getenv("COVERAGE_MIN", "0.8"))

    sources = [{"id":"s1","text":src_text}]
    messages = [
        {"role":"system",
         "content": "Answer STRICTLY and ONLY from SOURCE. If not enough info, reply exactly: 'insufficient evidence'. 1–2 sentences."},
        {"role":"user",
         "content": f"SOURCE:\n<<<\n{src_text}\n>>>\nQUESTION:\n{q}\nAnswer strictly from SOURCE."}
    ]

    provider, model, cost, lat = "echo", "stub", 0.0, 0
    answer = None
    ok_res = True

    try:
        gw = Gateway()
        res = gw.complete(messages)  # אל תעביר tags כאן כרגע
        provider = getattr(res, "provider", provider)
        model    = getattr(res, "model", model)
        cost     = float(getattr(res, "cost_usd", cost))
        lat      = int(getattr(res, "latency_ms", lat))
        ok_res   = bool(getattr(res, "ok", True))
        answer   = (getattr(res, "text", "") or "").strip()
    except Exception:
        # חסם תקציב/דרייבר איננו ⇒ נפילה לפולבק בטוח
        answer = None
        ok_res = False
        provider, model = "blocked", "budget"

    if not answer or answer.startswith("[driver-error]"):
        answer = "insufficient evidence"
        ok_res = False

    cits = compute_citations(answer, sources)
    coverage = len([t for t in cits["per_token"] if t]) / max(1, len(cits["per_token"]))
    CAP = float(os.getenv("MAX_COST_PER_CALL", "0.02"))

    ok = ok_res and (answer != "insufficient evidence") and (coverage >= COVERAGE_MIN) and (cost <= CAP)

    return {
        "answer": answer,
        "sources": sources,
        "citations": cits,
        "coverage": coverage,
        "provider": provider,
        "model": model,
        "cost_usd": round(cost, 6),
        "latency_ms": lat,
        "ok": ok,
    }

@router.post("/grounded/verify")
def grounded_verify(payload: dict = Body(...)):
    """
    קלט: {"answer": "...", "sources": [{"id":"s1","text":"..."}]}
    פלט: {"ok": bool, "notes": [...], "coverage": float, "citations": {...}}
    """
    answer = (payload or {}).get("answer", "") or ""
    sources = (payload or {}).get("sources", []) or []
    cits = compute_citations(answer, sources)
    coverage = len([t for t in cits["per_token"] if t]) / max(1, len(cits["per_token"]))
    # בקשת ביקורת מה-LLM (קלה):
    src_concat = "\n\n".join([s.get("text", "") for s in sources])
    prompt = {
        "role": "user",
        "content": (
            "You are a strict critic. Given SOURCE and ANSWER, say PASS if the answer strictly "
            "uses only facts from SOURCE and provides no hallucinated content; otherwise FAIL and list brief reasons.\n"
            f"SOURCE:\n<<<\n{src_concat}\n>>>\nANSWER:\n{answer}\n\nReply JSON: {{\"verdict\":\"PASS|FAIL\",\"reasons\":[\"...\"]}}"
        ),
    }
    def simple_verdict(answer: str, sources_text: str) -> str:
        # "מחמיר": כל מילה משמעותית בתשובה (3+ תווים) חייבת להופיע במקור, מותר חריגה עד 20%
        import re
        aw = [w.lower() for w in re.findall(r"[A-Za-zא-ת]{3,}", answer)]
        sw = set([w.lower() for w in re.findall(r"[A-Za-zא-ת]{3,}", sources_text)])
        if not aw: 
            return "FAIL: empty"
        extra = [w for w in aw if w not in sw]
        leak_ratio = len(extra)/max(1,len(aw))
        return "FAIL: leak" if leak_ratio > 0.2 else "PASS"
    
    res = gw.complete([prompt], tags={"route": "verify"})
    verdict = simple_verdict(answer, " ".join(s["text"] for s in sources))
    reasons = []
    try:
        import json as _json
        j = _json.loads((res.text or "").strip())
        verdict = str(j.get("verdict", "FAIL")).upper()
        reasons = j.get("reasons", [])
    except Exception:
        reasons = ["LLM returned non-JSON verdict"]

    ok = (coverage >= COVERAGE_MIN) and (verdict == "PASS")
    return {"ok": ok, "notes": reasons, "coverage": coverage, "citations": cits}

