# -*- coding: utf-8 -*-
r"""스크립트 명령 길이표 추정(2026-10-04) — 0.BIN(0x06004000) 분기기 0x0600FB5A:
  앞 바이트 FD → 표 0x0600CE20 · FE → 0x0600D078 · FF → 0x0600CE38(필드) / 0x06038D20(다른 모드)
  처리 함수 안에서 «스크립트 포인터 전역 0x0609408C 를 읽고 ADD #n 한 값을 다시 저장» 하는 n 을 찾는다(분기기가 이미 2 전진).
  python tools/smops.py → 표 출력(명령 · 함수 · 길이 후보 · 호출 여부)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
B = 0x06004000; PTR = 0x0609408C
d = open(os.path.join(ROOT, 'work', 'disc', 'd1', '0.BIN'), 'rb').read()
h = lambda a: struct.unpack_from('>H', d, a - B)[0]
u = lambda a: struct.unpack_from('>I', d, a - B)[0]
TABLES = {'FD': (0x0600CE20, 6), 'FE': (0x0600D078, None), 'FF': (0x0600CE38, None), 'FFb': (0x06038D20, 121)}


def analyze(fn, limit=400):
    regs = {}          # reg → ('P',) 포인터 주소 / ('V', off) 포인터 값+off
    pend = False
    stores = []; calls = 0; a = fn; seen_rts = False
    for _ in range(limit):
        w = h(a); n = (w >> 8) & 15; m = (w >> 4) & 15; op = w >> 12
        if op == 0xD:
            lit = u(((a + 4) & ~3) + (w & 0xFF) * 4); regs[n] = ('P',) if lit == PTR else None
        elif op == 6 and (w & 15) == 2:      # MOV.L @Rm,Rn
            regs[n] = ('V', 0) if regs.get(m) == ('P',) else None
        elif op == 6 and (w & 15) == 3:      # MOV Rm,Rn
            regs[n] = regs.get(m)
        elif op == 6 and (w & 15) in (4, 5, 6):   # MOV.x @Rm+,Rn
            r = regs.get(m); regs[n] = None
            if r and r[0] == 'V' and m != n: regs[m] = ('V', r[1] + {4: 1, 5: 2, 6: 4}[w & 15])
        elif op == 7:                        # ADD #imm,Rn
            imm = w & 0xFF; imm = imm - 256 if imm > 127 else imm
            r = regs.get(n); regs[n] = ('V', r[1] + imm) if r and r[0] == 'V' else None
        elif op == 2 and (w & 15) == 2:      # MOV.L Rm,@Rn
            if regs.get(n) == ('P',):
                r = regs.get(m); stores.append(r[1] if r and r[0] == 'V' else '?')
        elif w == 0x000B:
            if seen_rts: break
            seen_rts = True; a += 2; continue    # 지연 슬롯
        elif (w & 0xF0FF) == 0x400B or (w & 0xF000) == 0xB000 or (w & 0xF0FF) == 0x0003:
            calls += 1; a += 2; pend = True                       # 지연 슬롯 먼저 처리
            continue
        else:
            if op in (6, 3, 0xE, 5, 8, 9, 0xC) or (op == 4): regs.pop(n, None) if op != 8 else None
        if pend:
            pend = False
            regs.pop(0, None)                              # 이 컴파일러는 호출 뒤에도 R1‥R7 을 그대로 씀(FF 08)
        if seen_rts: break
        a += 2
    return stores, calls


def table(name):
    base, cnt = TABLES[name]; out = []; k = 0
    while True:
        if cnt is not None and k >= cnt: break
        f = u(base + 4 * k)
        if not (B <= f < B + len(d)): break
        if cnt is None and k and base + 4 * k in [t[0] for t in TABLES.values() if t[0] != base]: break
        out.append((k, f) + analyze(f)); k += 1
        if k > 256: break
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for name in ('FD', 'FE', 'FF'):
        for k, f, st, c in table(name):
            print('%s %02X  %08X  저장=%s  호출=%d' % (name[:2], k, f, st, c))
