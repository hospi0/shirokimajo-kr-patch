# -*- coding: utf-8 -*-
r"""PoC 1 (2026-10-04): KANJI12.FON 한자 칸 몇 개를 한글로 → 대사·장 제목·메뉴가 다 바뀌는지
  KANJI12.FON = JIS 구·점 순 12×12 1bpp, 18 B/글자, 색인 = (구−1)×94 + (점−1)
  python tools/poc_font.py [--install]  → work/out/d1/트랙 1 (+ F: 디스크 1 트랙 1 교체)
"""
import os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf, disc, iso

SWAP = {'明': '명', '日': '일', '準': '준', '備': '비', '序': '서', '章': '장', '設': '설', '定': '정', '母': '모'}
F_DIR = r'F:\hospi\roms\ss roms\Shiroki Majo - Mou Hitotsu no Eiyuu Densetsu (Japan) (Disc 1)'


def jis_index(ch):
    b = ch.encode('cp932'); s1, s2 = b[0], b[1]
    ku = (s1 - (0x81 if s1 < 0xA0 else 0xC1)) * 2 + 1 + (1 if s2 >= 0x9F else 0)
    ten = (s2 - 0x9E) if s2 >= 0x9F else (s2 - 0x3F - (1 if s2 >= 0x80 else 0))
    return (ku - 1) * 94 + (ten - 1)


def cell(ch):
    w, h, ox, oy, rows = bdf.load('Galmuri11')[ord(ch)]
    a = np.zeros((12, 12), np.uint8); top = 12 - 1 - (h + oy)            # 바닥선 = 11행
    for i, r in enumerate(rows):
        v = int(r, 16); nb = len(r) * 4
        for x in range(w):
            if (v >> (nb - 1 - x)) & 1 and 0 <= top + i < 12 and 0 <= ox + x < 12: a[top + i, ox + x] = 1
    return a


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    F = bytearray(disc.read(1, 'SYSTEM/KANJI12.FON'))
    for jp, kr in SWAP.items():
        k = jis_index(jp); bits = np.packbits(cell(kr).reshape(-1)).tobytes()
        F[k * 18:k * 18 + 18] = bits; print(jp, '→', kr, '색인', k)
    out = os.path.join(ROOT, 'work', 'out', 'd1'); os.makedirs(out, exist_ok=True)
    name = os.path.basename(disc.TRACK[1]); dst = os.path.join(out, name)
    shutil.copyfile(disc.TRACK[1], dst)
    iso.patch_sub(dst, {'SYSTEM/KANJI12.FON': bytes(F)})
    if '--install' in sys.argv:
        shutil.copyfile(dst, os.path.join(F_DIR, name)); print('F: 설치', F_DIR)


if __name__ == '__main__':
    main()
