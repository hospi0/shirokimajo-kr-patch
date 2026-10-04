# -*- coding: utf-8 -*-
"""원문 대사 줄 폭 분포(px: 전각 12 · 반각 6) — 대사창 폭을 «벼랑»에서 읽는다
  쪽 = {0E}·{0F}·{10} 사이, 줄 = \\n. 맵 대사(MAP000 제외)만.
python tools/smwidth.py"""
import collections, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{(?:01|02|09|19)\}.|\{07\}..|\{[0-9A-F]{2}\}')
NL = '\\n'


def width(s):
    s = TOK.sub('', s)
    return sum(6 if ord(c) < 0x80 or 0xFF61 <= ord(c) <= 0xFF9F else 12 for c in s)


def pages(t):
    return re.split(r'\{0E\}|\{0F\}|\{10\}', t)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    W = collections.Counter(); L = collections.Counter(); ex = {}
    for l in open(os.path.join(ROOT, 'work/text/sm.tsv'), encoding='utf-8'):
        if l.startswith('#'):
            continue
        f = l.rstrip('\n').split('\t')
        if not f[1].startswith('MAP/') or f[1].startswith('MAP/MAP000'):
            continue
        for pg in pages(f[3]):
            if '　　' in pg:                  # 들여쓴 장면 자막(가운데 맞춤) 제외
                continue
            ls = pg.split(NL); L[len(ls)] += 1
            for x in ls:
                w = width(x); W[w] += 1; ex.setdefault(w, x)
    tot = sum(W.values()); acc = 0
    for w in sorted(W):
        acc += W[w]
        if 168 <= w <= 300:
            print(w, W[w], '%.2f%%' % (acc / tot * 100), ex[w][:40])
    print('쪽당 줄 수', sorted(L.items()))


if __name__ == '__main__':
    main()
