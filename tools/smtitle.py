# -*- coding: utf-8 -*-
r"""타이틀 화면 그림 (2026-10-04)
  SYSTEM/LDDATA.PAK = [u32 BE 개수 16][u32 BE 시작 ×16] · 타이틀 = 7 타일(8bpp 8×8, VRAM 0 부터, 64 KB = 1024칸)
  · 8 팔레트(256색 RGB555 BE) · 9 맵(40×30, 2워드 PN: w0 팔레트 0 · w1 = 타일 바이트 주소/0x20) — VDP2 NBG2
python tools/smtitle.py dump  → work/title/orig.png(320×240) · orig_idx.png(인덱스)"""
import os, struct, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'work', 'title')
TILES, PAL, MAP = 7, 8, 6                                     # ★맵은 6번(9번은 다른 화면 — 같은 타일 7번을 씀)


def entries(d):
    n = struct.unpack_from('>I', d, 0)[0]
    o = [struct.unpack_from('>I', d, 4 + 4 * i)[0] for i in range(n)] + [len(d)]
    return [(o[i], o[i + 1]) for i in range(n)]


def palette(d):
    a, b = entries(d)[PAL]
    w = struct.unpack('>%dH' % ((b - a) // 2), d[a:b])
    return np.array([[(x & 31) << 3, ((x >> 5) & 31) << 3, ((x >> 10) & 31) << 3] for x in w], np.uint8)


def to_index(d):
    """맵 → 320×240 인덱스 그림"""
    E = entries(d); ta, _ = E[TILES]; ma, _ = E[MAP]
    img = np.zeros((240, 320), np.uint8)
    for cy in range(30):
        for cx in range(40):
            w0, w1 = struct.unpack_from('>HH', d, ma + (cy * 40 + cx) * 4)
            a = ta + w1 * 0x20
            t = np.frombuffer(d[a:a + 64], np.uint8).reshape(8, 8)
            if w0 & 0x4000:
                t = t[::-1]
            if w0 & 0x8000:
                t = t[:, ::-1]
            img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = t
    return img


def from_index(d, img):
    """320×240 인덱스 그림 → 타일(중복 제거)·맵을 다시 써서 새 PAK 바이트 (팔레트 그대로)"""
    E = entries(d); (ta, tb), (ma, mb) = E[TILES], E[MAP]
    tiles = {}; order = []; mp = bytearray()
    for cy in range(30):
        for cx in range(40):
            t = img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].tobytes()
            if t not in tiles:
                tiles[t] = len(order); order.append(t)
            mp += struct.pack('>HH', 0, tiles[t] * 2)
    blob = b''.join(order)
    if len(blob) > tb - ta:
        raise SystemExit('⛔타이틀 타일 %d칸 > %d칸' % (len(order), (tb - ta) // 64))
    n = bytearray(d)
    n[ta:tb] = blob + bytes(tb - ta - len(blob))
    n[ma:mb] = mp
    return bytes(n), len(order)


def main():
    sys.path.insert(0, HERE)
    import disc
    os.makedirs(OUT, exist_ok=True)
    d = disc.read(1, 'SYSTEM/LDDATA.PAK')
    P = palette(d); idx = to_index(d)
    Image.fromarray(P[idx]).save(os.path.join(OUT, 'orig.png'))
    Image.fromarray(idx).save(os.path.join(OUT, 'orig_idx.png'))
    n2, k = from_index(d, idx)
    print('왕복 그림 같음', (to_index(n2) == idx).all(), '타일', k)


if __name__ == '__main__':
    main()
