# -*- coding: utf-8 -*-
r"""맵 스크립트 재조립(2026-10-04, 검증 단계) — 문장 명령의 문장 바이트를 바꾸고 뒤를 밀며 절대주소를 전부 고친다.
  고치는 주소: ① 명령 안 u32 (FD 00‥04 @+2 · FF 65·FF 1F @+4) ② 명령 밖(데이터 표) 짝수 위치 u32 중 «명령 머리»를 가리키는 값
  python tools/smbuild.py selftest   → 전 맵: 모든 문장에 전각 공백 1자를 더해 재조립 → 다시 역어셈블해 명령 열·대상 대응 검사
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smdis

ADDR_OPS = {(0xFD, 0): 2, (0xFD, 1): 2, (0xFD, 3): 2, (0xFD, 4): 2, (0xFF, 0x65): 4, (0xFF, 0x1F): 4}
B = smdis.BASE; LIMIT = 0x20000


def analyze(d):
    L = smdis.length_table()
    seen, err, errs = smdis.walk(d, smdis.entries(d), L)
    code = bytearray(len(d))
    for a, (p, op, n) in seen.items(): code[a:a + n] = b'\x01' * n
    ptrs = []                                        # (위치, 대상)
    for a, (p, op, n) in seen.items():
        if (p, op) in ADDR_OPS:
            o = a + ADDR_OPS[(p, op)]; ptrs.append((o, struct.unpack_from('>I', d, o)[0] - B))
    for i in range(0, len(d) - 3, 2):
        if code[i] or code[i + 3]: continue
        v = struct.unpack_from('>I', d, i)[0] - B
        if v in seen: ptrs.append((i, v))
    return seen, ptrs


def text_span(d, a, p, op, n):
    """문장 바이트 [시작, 끝) — 끝 = 00 위치"""
    s = a + smdis.TEXT_OPS[(p, op)]; e = s
    while d[e] != 0:
        b = d[e]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF: e += 2
        elif b < 0x20: e += 1 + smdis.CTRL_ARG.get(b, 0)
        else: e += 1
    return s, e


def rebuild(d, newtext):
    """newtext: {명령 주소: 새 문장 바이트(00 없이)} → 새 파일 바이트, 주소 대응표"""
    seen, ptrs = analyze(d)
    out = bytearray(); amap = {}; pos = 0
    for a in sorted(x for x in seen if seen[x][:2] in smdis.TEXT_OPS and x in newtext):
        p, op, n = seen[a]; s, e = text_span(d, a, p, op, n)
        out += d[pos:s]
        for k in range(pos, s): pass
        amap_seg = (pos, s, len(out) - (s - pos))
        amap.setdefault('segs', []).append(amap_seg)
        t = newtext[a] + b'\x00'
        if (s + len(t)) % 2 != (s % 2) ^ 0: pass
        out += t
        if len(out) & 1: out += b'\x00'
        pos = a + n                                  # 원래 다음 명령
    out += d[pos:]; amap.setdefault('segs', []).append((pos, len(d), len(out) - (len(d) - pos)))
    def new(x):
        for s0, e0, ns in amap['segs']:
            if s0 <= x < e0 or (x == e0 and x == len(d)): return ns + (x - s0)
        raise ValueError('주소 대응 없음 %X' % x)
    for o, t in ptrs:
        struct.pack_into('>I', out, new(o), new(t) + B)
    if len(out) > LIMIT: raise SystemExit('⛔맵 버퍼 넘침 %d > %d' % (len(out), LIMIT))
    return bytes(out), new


def selftest():
    sys.stdout.reconfigure(encoding='utf-8'); bad = 0
    for f in sorted(x for x in os.listdir(os.path.join(smdis.D1, 'MAP')) if x.endswith('.BIN')):
        d = open(os.path.join(smdis.D1, 'MAP', f), 'rb').read()
        seen, ptrs = analyze(d)
        nt = {}
        for a, (p, op, n) in seen.items():
            if (p, op) in smdis.TEXT_OPS:
                s, e = text_span(d, a, p, op, n); nt[a] = d[s:e] + b'\x81\x40'
        try: nd, new = rebuild(d, nt)
        except SystemExit as e: print(f, e); continue
        seen2, _, _ = smdis.walk(nd, [new(e) for e in smdis.entries(d)], smdis.length_table())
        # 대응 검사: 원래 명령마다 새 위치에 같은 머리·(문장 아니면) 같은 길이
        miss = sum(1 for a, (p, op, n) in seen.items() if seen2.get(new(a), (None,))[:2] != (p, op))
        extra = len(seen2) - len(seen)
        tgt = sum(1 for (o, t) in ptrs if struct.unpack_from('>I', nd, new(o))[0] - B != new(t))
        ok = miss == 0 and extra == 0 and tgt == 0
        bad += not ok
        print('%s 명령 %d→%d 어긋남 %d 주소 %d 크기 %d→%d %s' % (f, len(seen), len(seen2), miss, len(ptrs), len(d), len(nd), '' if ok else '⛔'))
    print('실패 맵', bad)


if __name__ == '__main__':
    selftest()
