from __future__ import annotations
from server.middleware.redaction_core import apply_redaction, load_policies

pii, rbac = load_policies()

SAMPLE = {
  'email': 'user@example.com',
  'phone': '+1 202 555 0199',
  'card': '4242 4242 4242 4242',
  'notes': 'Contact John Doe at john@corp.com tomorrow.'
}

def test_redaction_user():
    out = apply_redaction(SAMPLE, role='user', pii=pii, rbac=rbac)
    assert out['email'] != SAMPLE['email']
    assert out['phone'] != SAMPLE['phone']
    assert out['card']  != SAMPLE['card']
    assert 'john@corp.com' not in out['notes']

def test_redaction_admin():
    out = apply_redaction(SAMPLE, role='admin', pii=pii, rbac=rbac)
    # admin can see email/phone by default policy
    # adjust policy/pii.yaml to change behavior
    assert isinstance(out['email'], str)
