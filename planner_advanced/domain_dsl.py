from __future__ import annotations
from typing import Dict, Any

DSL_EXAMPLE = {
  'Customer':   {'fields': {'id':'int!','email':'str!','name':'str','phone':'str?'}},
  'Product':    {'fields': {'id':'int!','sku':'str!','name':'str!','price':'float!'}},
  'Order':      {'fields': {'id':'int!','customer_id':'int!','status':'str!','total':'float!'}, 'events': ['OrderPlaced','OrderPaid','OrderShipped']},
  'LineItem':   {'fields': {'id':'int!','order_id':'int!','sku':'str!','qty':'int!','price':'float!'}},
}

TYPE_MAP = {'int':'int','float':'float','str':'str','text':'text'}

def parse_type(t: str):
    req = t.endswith('!')
    base = t.rstrip('!?')
    return TYPE_MAP.get(base, 'str'), req

