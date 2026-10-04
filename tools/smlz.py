# -*- coding: utf-8 -*-
r"""BATTLE.BIN 류 이름 묶음 + LZSS 해제(2026-10-04) — 0.BIN 해제 루틴 0x0604718C 를 옮김
  묶음 항목: [u32 BE 항목 길이(머리 포함)][이름 00][u32 LE 원래 크기][압축 데이터]  (BATTLE.BIN 은 LowRAM 0x2D8804 에 적재,
            이름 찾기 0x06020D8C — 예: status.spr → 0x060A2644)
  압축: 256B 고리 버퍼(0 으로 채움, 쓰기 시작 0xEF). 플래그 바이트 MSB 부터, 1 = 리터럴 1바이트 · 0 = [오프셋 1바이트] +
        길이 니블(새 바이트를 읽어 위 니블 → 다음 복사는 그 바이트의 아래 니블을 씀) + 2.
python tools/smlz.py 파일 [출력 폴더]  → 항목 목록 (+ 풀어서 저장)"""
import os, struct, sys


def entries(d):
    out = []; o = 0
    while o + 4 <= len(d):
        n = struct.unpack_from('>I', d, o)[0]
        if n == 0:
            break
        e = d.index(b'\0', o + 4)
        name = d[o + 4:e].decode('latin1')
        size = struct.unpack_from('<I', d, e + 1)[0]
        out.append((name, o, e + 1, size))
        o = o + n                                                        # 길이는 항목 머리부터
    return out


def decompress(d, p, size=None):
    """p = 원래 크기(u32 LE) 위치"""
    if size is None:
        size = struct.unpack_from('<I', d, p)[0]
    p += 4
    ring = bytearray(256); w = 0xEF; out = bytearray()
    flags = 0; bits = 0; run = 0; src = 0; half = None
    while len(out) < size:
        if run == 0:
            if bits == 0:
                flags = d[p]; p += 1; bits = 8
            bit = flags & 0x80; flags = (flags << 1) & 0xFF; bits -= 1
            if bit:
                c = d[p]; p += 1
                ring[w] = c; w = (w + 1) & 0xFF; out.append(c); continue
            src = d[p]; p += 1
            if half is None:
                b = d[p]; p += 1; half = b & 0x0F; run = (b >> 4) + 2
            else:
                run = half + 2; half = None
        c = ring[src]; src = (src + 1) & 0xFF; run -= 1
        ring[w] = c; w = (w + 1) & 0xFF; out.append(c)
    return bytes(out), p


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    d = open(sys.argv[1], 'rb').read()
    od = sys.argv[2] if len(sys.argv) > 2 else None
    if od:
        os.makedirs(od, exist_ok=True)
    for name, o, p, size in entries(d):
        try:
            data, end = decompress(d, p, size)
            note = '끝 %d/%d' % (end - o - 4, struct.unpack_from('>I', d, o)[0])
        except IndexError:
            data, note = b'', '⚠해제 실패'
        print('%-14s @%06X 원래 %6d  %s' % (name, o, size, note))
        if od and data:
            open(os.path.join(od, name), 'wb').write(data)
