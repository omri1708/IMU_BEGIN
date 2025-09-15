from __future__ import annotations
from typing import Optional

# OpenAI — tiktoken
try:
    import tiktoken  # type: ignore
except Exception:
    tiktoken = None

# Anthropic SDK has helper in newer versions; guard gracefully
try:
    import anthropic  # type: ignore
except Exception:
    anthropic = None

# Vertex — google-cloud-aiplatform has token counting helpers for some models
try:
    from vertexai.preview.generative_models import GenerativeModel  # type: ignore
    HAVE_VERTEX = True
except Exception:
    HAVE_VERTEX = False


def count_tokens(provider: str, model: str, text: str) -> int:
    provider = (provider or '').lower()
    if provider == 'openai' and tiktoken:
        try:
            enc = tiktoken.encoding_for_model(model)
        except Exception:
            enc = tiktoken.get_encoding('cl100k_base')
        return len(enc.encode(text or ''))
    if provider == 'anthropic' and anthropic:
        try:
            # No public tokenizer API guaranteed; rough approx
            return max(1, int(len(text or '') / 4))
        except Exception:
            return max(1, int(len(text or '') / 4))
    if provider == 'vertex' and HAVE_VERTEX:
        try:
            gm = GenerativeModel(model)
            # some SDKs expose count_tokens; fallback to approx if not
            if hasattr(gm, 'count_tokens'):
                return int(gm.count_tokens([text]).total_tokens)  # type: ignore
        except Exception:
            pass
    # default approx
    return max(1, int(len(text or '') / 4))
