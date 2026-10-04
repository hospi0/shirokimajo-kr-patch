# -*- coding: utf-8 -*-
"""번역 병합: python tools/trmerge.py <분할번호> <번역파일>
번역파일 = 줄마다 `번호<TAB>번역` (빈 번역·잡음 줄은 생략). work/text/split/sm_NNN.tsv 의 5번째 칸에 채운다.
제어 코드 {XX}·%d·%s·\\n 개수가 원문과 다르면 경고."""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def codes(s): return sorted(re.findall(r'\{[0-9A-F]{2}\}|%[a-z]|\\n', s))
def main():
    n, tr = sys.argv[1], sys.argv[2]
    path = os.path.join(ROOT, 'work', 'text', 'split', 'sm_%03d.tsv' % int(n))
    t = {}
    for ln in open(tr, encoding='utf-8').read().split('\n'):
        if not ln.strip(): continue
        k, _, v = ln.partition('\t'); t[k] = v
    out = []; done = 0; warn = 0
    for ln in open(path, encoding='utf-8').read().split('\n'):
        if not ln or ln.startswith('#'): out.append(ln); continue
        f = ln.split('\t')
        if f[0] in t:
            f = f[:4] + [t.pop(f[0])]
            if codes(f[3]) != codes(f[4]): print('경고: 제어코드 불일치', f[0], f[3], '→', f[4]); warn += 1
            done += 1
        out.append('\t'.join(f))
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    if t: print('못 찾은 번호:', list(t))
    print('sm_%03d: %d줄 병합, 경고 %d' % (int(n), done, warn))
main()
