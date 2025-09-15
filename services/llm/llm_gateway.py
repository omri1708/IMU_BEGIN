from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time, json, os, pathlib
import inspect

from .tokenizers import count_tokens
# drivers
from .providers.openai_driver import OpenAIDriver  # type: ignore
from .providers.azure_openai_driver import AzureOpenAIDriver  # type: ignore
from .providers.anthropic_driver import AnthropicDriver  # type: ignore
from .providers.vertex_driver import VertexDriver  # type: ignore
from .providers.bedrock_driver import BedrockDriver  # type: ignore
from .providers.http_driver import HttpDriver  # type: ignore
from .providers.llamacpp_driver import LlamaCppDriver  # type: ignore

@dataclass
class ProviderResult:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    text: str
    ok: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)

class LLMGateway:
    PRICES = {
        ("openai", "gpt-4o-mini"): {"in": 0.00015, "out": 0.0006},
        ("openai", "gpt-4o"):      {"in": 0.005,   "out": 0.015},
        ("anthropic", "claude-3.5-sonnet"): {"in": 0.003, "out": 0.015},
        ("vertex", "gemini-1.5-pro"): {"in": 0.0005, "out": 0.0015},
        ("bedrock", "anthropic.claude-3-sonnet-20240229-v1:0"): {"in": 0.003, "out": 0.015},
        ("azure", "gpt-4o"): {"in": 0.005, "out": 0.015},
        ("http", "default"): {"in": 0.0, "out": 0.0},
        ("llamacpp", "local"): {"in": 0.0, "out": 0.0},
    }

    def __init__(self, policy: Optional[Dict[str, Any]] = None, kpi_log: str = ".imu_runs/llm_kpis.jsonl"):
        self.policy = policy or {}
        self.kpi_path = pathlib.Path(kpi_log); self.kpi_path.parent.mkdir(parents=True, exist_ok=True)

    def _price(self, provider: str, model: str, ptok: int, ctok: int) -> float:
        p = self.PRICES.get((provider, model)) or {"in": 0.001, "out": 0.003}
        return (ptok/1000.0) * p["in"] + (ctok/1000.0) * p["out"]

    def _emit_kpi(self, rec: Dict[str, Any]):
        with self.kpi_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _driver_for(self, provider: str, model: str):
        p = provider.lower()
        if p == 'openai': return OpenAIDriver(model)
        if p == 'azure':  return AzureOpenAIDriver(deployment=os.getenv('AZURE_OPENAI_DEPLOYMENT'))
        if p == 'anthropic': return AnthropicDriver(model)
        if p == 'vertex': return VertexDriver(model)
        if p == 'bedrock': return BedrockDriver(model)
        if p == 'http': return HttpDriver()
        if p == 'llamacpp': return LlamaCppDriver()
        raise RuntimeError(f'Unknown provider: {provider}')

    def _candidates(self) -> List[Dict[str,str]]:
        c = []
        if os.getenv('OPENAI_API_KEY'): c.append({"provider":"openai","model":os.getenv('OPENAI_MODEL','gpt-4o-mini')})
        if os.getenv('AZURE_OPENAI_API_KEY') and os.getenv('AZURE_OPENAI_ENDPOINT') and os.getenv('AZURE_OPENAI_DEPLOYMENT'):
            c.append({"provider":"azure","model":os.getenv('AZURE_OPENAI_DEPLOYMENT')})
        if os.getenv('ANTHROPIC_API_KEY'): c.append({"provider":"anthropic","model":os.getenv('ANTHROPIC_MODEL','claude-3.5-sonnet')})
        if os.getenv('GOOGLE_CLOUD_PROJECT'): c.append({"provider":"vertex","model":os.getenv('VERTEX_MODEL','gemini-1.5-pro')})
        if os.getenv('AWS_REGION'): c.append({"provider":"bedrock","model":os.getenv('BEDROCK_MODEL','anthropic.claude-3-sonnet-20240229-v1:0')})
        if os.getenv('LLAMACPP_MODEL_PATH'): c.append({"provider":"llamacpp","model":"local"})
        if os.getenv('IMU_HTTP_LLM_ENDPOINT'): c.append({"provider":"http","model":"default"})
        return c or [{"provider":"http","model":"default"}]

    def complete(self, messages: List[Dict[str, str]],
                 candidates: List[Dict[str, str]] | None = None,
                 budget_usd: float | None = None,
                 tags: Dict[str, Any] | None = None) -> ProviderResult:
        cand = (candidates or self._candidates())[0]
        provider, model = cand['provider'], cand['model']
        text_in = (messages[-1].get('content') if messages else '')
        ptok = count_tokens(provider, model, text_in)
        import time
        start = time.time()
        try:
            out = self._driver_for(provider, model).complete(messages)
            text_out = out.get('text','')
            ctok = out.get('completion_tokens') or count_tokens(provider, model, text_out)
            cost = self._price(provider, model, ptok, ctok)
            lat = (time.time() - start) * 1000.0
            res = ProviderResult(provider, model, ptok, ctok, cost, lat, text_out, ok=True)
        except Exception as e:
            lat = (time.time() - start) * 1000.0
            res = ProviderResult(provider, model, ptok, 0, 0.0, lat, f"[driver-error] {e}", ok=False)
        # --------- Auto-tags for KPI ----------
        caller = None
        try:
            stk = inspect.stack()
            if len(stk) >= 3:
                frm = stk[2]
                caller = f"{os.path.basename(frm.filename)}:{frm.function}"
        except Exception:
            caller = None
        rec = {
            "provider": res.provider,
            "model": res.model,
            "ptok": res.prompt_tokens,
            "ctok": res.completion_tokens,
            "cost": res.cost_usd,
            "latency_ms": res.latency_ms,
            "ok": res.ok,
            "caller": caller,
            # useful derived features:
            "answer_chars": len(res.text or ""),
            "token_eff": round((res.completion_tokens or 1) / max(1, res.prompt_tokens + res.completion_tokens), 4),
            "cost_per_token_out": round(res.cost_usd / max(1, res.completion_tokens), 6),
        }
        if tags:
            rec["tags"] = tags
        self._emit_kpi(rec)
        # enforce cost gate
        max_call = (self.policy.get('cost', {}) or {}).get('max_usd_per_call')
        if max_call is not None and res.cost_usd > float(max_call):
            raise RuntimeError(f"CostGate: call cost {res.cost_usd:.4f} > max_usd_per_call={max_call}")
        return res
