from __future__ import annotations
from typing import List, Tuple

# Longest Common Substring spans (O(n*m)) — returns non-overlapping spans
# on (a,b) indices with minimum length threshold

def lcs_spans(a: str, b: str, min_len: int = 8) -> List[Tuple[int,int,int,int]]:
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return []
    dp = [[0]*(m+1) for _ in range(n+1)]
    spans = []
    used_a = [False]*n
    used_b = [False]*m
    for i in range(1, n+1):
        ai = a[i-1]
        for j in range(1, m+1):
            if ai == b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
                L = dp[i][j]
                if L >= min_len:
                    a_end = i
                    b_end = j
                    a_start = a_end - L
                    b_start = b_end - L
                    # check overlap budget
                    if not any(used_a[a_start:a_end]) and not any(used_b[b_start:b_end]):
                        for k in range(a_start, a_end): used_a[k] = True
                        for k in range(b_start, b_end): used_b[k] = True
                        spans.append((a_start, a_end, b_start, b_end))
            else:
                dp[i][j] = 0
    spans.sort(key=lambda x: x[0])
    return spans
