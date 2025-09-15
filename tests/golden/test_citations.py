from __future__ import annotations
from alignment.attribution import compute_citations

ANS = 'The capital of France is Paris. It is known for the Eiffel Tower.'
SRCS = [
  {'id':'s1','text':'Paris is the capital city of France with the Eiffel Tower.'},
  {'id':'s2','text':'Berlin is the capital of Germany.'}
]

def test_citations_basic():
    cit = compute_citations(ANS, SRCS)
    assert 'per_token' in cit and isinstance(cit['per_token'], list)
    assert any(x == 's1' for x in cit['per_token'])
