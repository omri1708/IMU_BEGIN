from __future__ import annotations
import subprocess, json

def main():
    p = subprocess.run(['git','diff','--stat'], capture_output=True, text=True)
    print(json.dumps({'diffstat': p.stdout.strip()}))

if __name__=='__main__':
    main()
