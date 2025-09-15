from __future__ import annotations
from trustops.opa_eval import OPA
from contracts.business_z3 import check_refund

opa=OPA()

def test_abac_manager_read():
    out = opa.query('policy.abac','allow', {'request':{'user':{'role':'manager'}, 'action':'read'}, 'resource':{}})
    assert out.get('result') is True

def test_contract_z3():
    assert check_refund(50, 100) is True
    assert check_refund(150, 100) is False
