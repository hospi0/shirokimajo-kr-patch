# -*- coding: utf-8 -*-
r"""보충 추출(2026-10-04) — 첫 추출(smtext.segments)이 놓친 맵 문장: 화자 인자가 SJIS 앞 바이트(0x80·0x81)라
  인자와 다음 글자가 붙어 읽힌 문장({02}≠ﾙら…) · 장 제목({19}{FF}…) 등. 빌더가 «번역 없음/풀기 실패» 로 둔 문장 명령을
  인자 인식 디코더(show2: 01·02·09·19 뒤 1바이트, 07 뒤 2바이트는 항상 {XX})로 «문장 명령 통째» 한 줄로 뽑는다.
  번호 E0001‥ · 같은 문장은 한 줄(개수). 가나·한자가 없는 문장(부호만)은 뺀다.
python tools/smextra.py → work/text/sm_extra.tsv + my files/tsv/sm_extra_NNN.tsv(29KB 단위)"""
import collections, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smdis, smbuild, smtext, smkr

ARGS = {0x01: 1, 0x02: 1, 0x09: 1, 0x19: 1, 0x07: 2}


def show2(b):
    s = []; i = 0
    while i < len(b):
        c = b[i]
        if c in ARGS:
            s.append('{%02X}' % c + ''.join('{%02X}' % x for x in b[i + 1:i + 1 + ARGS[c]])); i += 1 + ARGS[c]; continue
        if smtext.lead(c):
            s.append(b[i:i + 2].decode('cp932')); i += 2; continue
        if c == 0x0D:
            s.append('\\n')
        elif c < 0x20 or (c >= 0x7F and not 0xA1 <= c <= 0xDF):
            s.append('{%02X}' % c)
        else:
            s.append(bytes([c]).decode('cp932'))
        i += 1
    return ''.join(s)


def ops_left():
    """빌더가 번역을 못 넣은 맵 문장 명령 → [(파일, 주소, 문장 시작, 끝, show2)]"""
    KO = smkr.load(); L = smdis.length_table(); out = []
    D1 = os.path.join(ROOT, 'work', 'disc', 'd1', 'MAP')
    for f in sorted(x for x in os.listdir(D1) if x.endswith('.BIN')):
        d = open(os.path.join(D1, f), 'rb').read()
        seen, _, _ = smdis.walk(d, smdis.entries(d), L); segs = smtext.segments(d)
        for a in sorted(seen):
            p, op, n = seen[a]
            if (p, op) not in smdis.TEXT_OPS:
                continue
            s0, e0 = smbuild.text_span(d, a, p, op, n)
            r = smkr.compose(d, s0, e0, [(s, e) for s, e in segs if s0 <= s < e0], KO)
            if not isinstance(r, str):
                continue
            try:
                t = show2(d[s0:e0])
            except UnicodeDecodeError:
                continue
            if smkr.encode(t, {}) != bytes(d[s0:e0]):
                continue
            if not re.search(r'[぀-ヿ一-鿿]', t):
                continue
            out.append((f, a, s0, e0, t))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = ops_left(); first = {}; cnt = collections.Counter()
    for f, a, s0, e0, t in rows:
        cnt[t] += 1; first.setdefault(t, 'MAP/%s:%06X' % (f, s0))
    lines = ['%s\t%s\t%d\t%s\t' % ('E%04d' % (k + 1), first[t], cnt[t], t) for k, t in enumerate(first)]
    head = '#번호\t첫 위치\t개수\t원문\t번역\n'
    open(os.path.join(ROOT, 'work/text/sm_extra.tsv'), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(lines) + '\n')
    # 29KB 단위 나눔(자투리는 앞 파일에 합침)
    chunks = [[]]; size = 0
    for l in lines:
        b = len((l + '\n').encode('utf-8'))
        if size + b > 29 * 1024 and chunks[-1]:
            chunks.append([]); size = 0
        chunks[-1].append(l); size += b
    if len(chunks) > 1 and sum(len((l + '\n').encode('utf-8')) for l in chunks[-1]) < 8 * 1024:
        chunks[-2] += chunks.pop()
    od = os.path.join(ROOT, 'my files', 'tsv')
    for i, c in enumerate(chunks):
        open(os.path.join(od, 'sm_extra_%03d.tsv' % (i + 1)), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(c) + '\n')
    jp = sum(1 for t in first for ch in t if '぀' <= ch <= 'ヿ' or '一' <= ch <= '鿿')
    print('문장 명령 %d · 고유 %d줄 · 가나·한자 %d자 · 파일 %d개' % (len(rows), len(first), jp, len(chunks)))


if __name__ == '__main__':
    main()
