from __future__ import annotations
# Placeholder: would require running Redis locally; ensure import works
from streaming.bus import Bus

def test_import_bus():
    assert callable(getattr(Bus, 'publish'))
