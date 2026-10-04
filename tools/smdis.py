# -*- coding: utf-8 -*-
r"""맵 스크립트 역어셈블러(2026-10-04, 검증 중) — 모든 명령은 짝수 주소의 [FD|FE|FF][op] + 인자.
  FD 00 점프 · FD 01 호출 · FD 02/05 복귀 · FD 03/04 조건 점프 (모두 u32 절대주소 = 파일 + 0x200000)
  FF 00/01 대사: [FF op][2바이트][SJIS…00] 다음 짝수 주소(가설)
  나머지 길이 = tools/smops.py 처리 함수 분석(2 + 포인터 전진량), LEN_FIX 로 덮어씀
  python tools/smdis.py [MAPnnn.BIN] → 도달 명령 수·오류
"""
import os, re, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
BASE = 0x200000
D1 = os.path.join(ROOT, 'work', 'disc', 'd1')
LEN_FIX = {(0xFF, 0x30): 8, (0xFF, 0x71): 4, (0xFF, 0x72): 4, (0xFF, 0x73): 4, (0xFF, 0x64): 8, (0xFF, 0x65): 8,
           (0xFF, 0x6F): 6, (0xFF, 0x1F): 8, (0xFF, 0x70): 6, (0xFF, 0x63): 8}
TEXT_OPS = {(0xFF, 0x00): 2, (0xFF, 0x01): 2, (0xFF, 0x81): 4, (0xFF, 0x87): 4}     # 문장 시작 오프셋(명령 머리부터)
CTRL_ARG = {0x01: 1, 0x02: 1, 0x07: 2, 0x09: 1, 0x19: 1}                                                                         # 문장 안 제어 코드 인자 길이(맞추는 중)


def length_table():
    L = {}
    for ln in open(os.path.join(ROOT, 'work', 'ops_guess.txt'), encoding='utf-8'):
        m = re.match(r'(F[DEF]) ([0-9A-F]{2})  \S+  저장=\[(.*)\]', ln)
        if not m: continue
        key = (int(m.group(1), 16), int(m.group(2), 16))
        vals = [int(x) for x in re.findall(r'-?\d+', m.group(3))]
        pos = [v for v in vals if v > 0]
        L[key] = 2 + (max(pos) if pos else 0)
    L.update(LEN_FIX)
    return L


def text_end(d, p):
    """문장: SJIS 2바이트 · 제어 01‥1F(+CTRL_ARG 인자) · 그 밖 1바이트, 00 끝 → 다음 짝수 주소(맞춤 바이트는 아무 값)"""
    q = p
    while q < len(d) and d[q] != 0:
        b = d[q]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF: q += 2
        elif b < 0x20: q += 1 + CTRL_ARG.get(b, 0)
        else: q += 1
    q += 1
    return q + (q & 1)


def cond_len(d, p):
    """조건식: 항(첫 워드 위 4비트 0‥2 = 1워드, 3‥7 = 2워드) 을 FFFC(AND)/FFFD(OR) 로 잇고 0000 끝 — 0x0600D528/D3C4"""
    q = p
    while True:
        w = struct.unpack_from('>H', d, q)[0]; q += 2 if (w >> 12) <= 2 else 4
        if (w >> 12) > 7: raise ValueError('항 종류 %X' % w)
        c = struct.unpack_from('>H', d, q)[0]; q += 2
        if c == 0: return q - p
        if c not in (0xFFFC, 0xFFFD): raise ValueError('잇기 %04X' % c)


def walk(d, entries, L):
    seen = {}; work = list(entries); err = collections.Counter(); errs = []
    while work:
        a = work.pop(); prev = None
        while True:
            if a in seen or not (0 <= a < len(d) - 1): break
            if a & 1: err['홀수'] += 1; errs.append((a, '홀수')); break
            p, op = d[a], d[a + 1]
            if p not in (0xFD, 0xFE, 0xFF): err['머리'] += 1; errs.append((a, 'head %02X%02X after %s' % (p, op, prev))); break
            if (p, op) in TEXT_OPS:
                n = text_end(d, a + TEXT_OPS[(p, op)]) - a
            elif (p, op) == (0xFF, 0x36):
                n = 6 if d[a + 2] == 3 else 4
            elif p == 0xFD and op in (3, 4):
                try: n = 6 + cond_len(d, a + 6)
                except (ValueError, struct.error) as e: err['조건'] += 1; errs.append((a, 'cond %s' % e)); break
            elif (p, op) in L:
                n = L[(p, op)]
            else:
                err['모름'] += 1; errs.append((a, 'unk %02X%02X' % (p, op))); break
            seen[a] = (p, op, n); prev = '%02X%02X' % (p, op)
            if p == 0xFD:
                if op in (2, 5): break
                t = struct.unpack_from('>I', d, a + 2)[0] - BASE
                if 0 <= t < len(d): work.append(t)
                else: err['대상'] += 1; errs.append((a, 'tgt %X' % t))
                if op == 0: break
            a += n
    return seen, err, errs


def entries(d):
    """파일 안 짝수 위치 u32 중 «짝수 주소 + FD/FE/FF 머리»를 가리키는 값(데이터 표의 스크립트 포인터 후보)"""
    out = set()
    for i in range(0, len(d) - 3, 2):
        v = struct.unpack_from('>I', d, i)[0] - BASE
        if 0 <= v < len(d) - 1 and not v & 1 and ((d[v] == 0xFF and d[v + 1] < 0x90) or (d[v] == 0xFE and d[v + 1] < 0x40) or (d[v] == 0xFD and d[v + 1] < 6)):
            out.add(v)
    return sorted(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    L = length_table(); tot = collections.Counter(); first = {}
    fs = sys.argv[1:] or sorted(f for f in os.listdir(os.path.join(D1, 'MAP')) if f.endswith('.BIN'))
    for f in fs:
        d = open(os.path.join(D1, 'MAP', f), 'rb').read()
        seen, err, errs = walk(d, entries(d), L)
        tot.update(err); tot['명령'] += len(seen)
        for a, e in errs: first.setdefault(e.split()[0] + ' ' + e.split()[1] if ' ' in e else e, (f, hex(a)))
        if len(fs) <= 3: print(f, len(seen), dict(err), errs[:8])
    print('합계', dict(tot))
    for k, v in sorted(first.items())[:40]: print('  ', k, v)


if __name__ == '__main__':
    main()
