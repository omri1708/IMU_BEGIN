from __future__ import annotations
import subprocess, sys

SECS = [
  ('features','יכולות'), ('nonfunc','איכות ואילוצים'), ('policies','מדיניות ו‑TrustOps'),
  ('corpora','מקורות וקורפוסים'), ('approvals','אישורים ושערים'), ('ux','חוויית משתמש')
]

def main():
    # 1) always ensure core via main engine
    subprocess.run([sys.executable, 'interview/engine.py'])
    while True:
        print('\n[advanced] בחר נושא להעמקה (או 0 לסיום):')
        for i, (_, t) in enumerate(SECS, 1): print(f'  {i}. {t}')
        print('  7. השלמת אילוצי שדות (constraints)')
        print('  0. סיום')
        sel = input('> ').strip()
        if sel in ('0','q','quit','exit'): break
        if sel == '7':
            subprocess.run([sys.executable, 'interview/constraints_enricher.py'])
            continue
        try:
            idx = int(sel); sid = SECS[idx-1][0]
            # run a focused pass over a single section using the engine's run_section path
            # fallback: just re-run engine for idempotent capture
            subprocess.run([sys.executable, 'interview/engine.py'])
        except Exception:
            continue
    print('[advanced] הסתיים — אפשר להמשיך לתכנון/בנייה.')

if __name__ == '__main__':
    main()
