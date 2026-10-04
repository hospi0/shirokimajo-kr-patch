# -*- coding: utf-8 -*-
r"""빌드 결과 검사: 맵 문장 명령을 인자 인식 디코더(smextra.show2)로 풀어 «가나가 남은» 문장을 찾는다 (2026-10-04)
  원인: 화자 인자가 SJIS 앞 바이트(0x80‥0x82)라 첫 추출이 다음 글자와 붙여 읽어 어긋남 → 첫 글자만 남거나(«あわわ» → «あ»)
        그 화자 대사 조각이 통째로 빠짐(«{02}{81}なにやってるのよ»). 번역이 일부 들어간 문장이라 보충 추출(smextra)에서도 빠졌다.
  가나만 본다(장음 ー·중점 ・ 제외 — 한글은 한자 칸이라 한자로 보인다).
python tools/smleft.py [--tsv]  → 목록 · --tsv 면 work/text/sm_left.tsv(원문 show2 · 지금 들어간 것)"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smdis, smextra

JP = re.compile(r'[ぁ-ゖァ-ヺ]')


def scan():
    L = smdis.length_table(); D1 = os.path.join(ROOT, 'work', 'disc', 'd1', 'MAP'); B = os.path.join(ROOT, 'work', 'build', 'MAP')
    out = []
    for f in sorted(x for x in os.listdir(D1) if x.endswith('.BIN')):
        d = open(os.path.join(D1, f), 'rb').read()
        nb = os.path.join(B, f)
        if not os.path.exists(nb):
            continue
        n = open(nb, 'rb').read()
        seen, _, _ = smdis.walk(d, smdis.entries(d), L)
        for a in sorted(seen):
            p, op, ln = seen[a]
            if (p, op) not in smdis.TEXT_OPS:
                continue
            q = a
            if n[q] == 0xFD and n[q + 1] == 0:
                q = int.from_bytes(n[q + 2:q + 6], 'big') - smdis.BASE
            if n[q:q + 2] != bytes([p, op]):
                continue
            s0 = q + smdis.TEXT_OPS[(p, op)]
            e0 = smdis.text_end(n, s0) - 1
            while e0 > s0 and n[e0 - 1] == 0:
                e0 -= 1
            try:
                t = smextra.show2(n[s0:e0])
            except UnicodeDecodeError:
                continue
            if JP.search(t):
                o0 = a + smdis.TEXT_OPS[(p, op)]; o1 = smdis.text_end(d, o0) - 1
                while o1 > o0 and d[o1 - 1] == 0:
                    o1 -= 1
                out.append((f, a, smextra.show2(d[o0:o1]), t))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    out = scan(); uniq = {}
    for f, a, o, t in out:
        uniq.setdefault(o, (f, a, t))
    for o, (f, a, t) in uniq.items():
        print(f, hex(a), o[:80])
    print('가나 남은 문장 명령', len(out), '· 고유', len(uniq))
    if '--tsv' in sys.argv:
        with open(os.path.join(ROOT, 'work', 'text', 'sm_left.tsv'), 'w', encoding='utf-8', newline='\n') as w:
            w.write('#번호\t첫 위치\t원문(show2)\t지금 들어간 것(인자 디코딩)\n')
            for k, (o, (f, a, t)) in enumerate(uniq.items()):
                w.write('L%03d\tMAP/%s:%06X\t%s\t%s\n' % (k + 1, f, a, o, t))


if __name__ == '__main__':
    main()
