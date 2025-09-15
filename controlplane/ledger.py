from __future__ import annotations
import os, psycopg2, datetime

DSN = os.getenv('IMU_CP_DSN','postgresql://postgres:postgres@localhost:5432/app')

def add_cost(provider: str, cost: float):
    m = datetime.datetime.utcnow().strftime('%Y-%m')
    with psycopg2.connect(DSN) as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO provider_budget(provider,month,spent,cap) VALUES(%s,%s,%s,%s)\n                        ON CONFLICT(provider,month) DO UPDATE SET spent=provider_budget.spent+EXCLUDED.spent",
                        (provider,m,cost, 9999))
            c.commit()
