# -*- coding: utf-8 -*-
"""BDF 픽셀 폰트 직독 — ⛔TTF 래스터라이즈 금지(획이 뭉갠다).

  Galmuri7            7×7  DWIDTH 8   -> 8×8 칸
  Galmuri11-Condensed 7×11 DWIDTH 8   -> 8×16 칸 (이 게임의 «탁점 행+글자 행»에 맞음)
"""
import io, os, re

DIR = r'C:\claude\utils\font\Galmuri-v2.40.3'
_cache = {}


def load(name):
    if name in _cache:
        return _cache[name]
    txt = io.open(os.path.join(DIR, name + '.bdf'), encoding='utf-8', errors='replace').read()
    g = {}
    for m in re.finditer(r'STARTCHAR (\S+)\nENCODING (-?\d+)\n(.*?)ENDCHAR', txt, re.S):
        cp = int(m.group(2)); blk = m.group(3)
        b = re.search(r'BBX (-?\d+) (-?\d+) (-?\d+) (-?\d+)', blk)
        bm = re.search(r'BITMAP\n(.*)', blk, re.S)
        if not b or not bm or cp < 0:
            continue
        w, h, ox, oy = (int(x) for x in b.groups())
        rows = [r.strip() for r in bm.group(1).strip().split('\n') if r.strip()]
        g[cp] = (w, h, ox, oy, rows)
    _cache[name] = g
    return g


def bitmap(name, ch, cell_w=8, cell_h=8, top=None):
    """글자를 cell_w×cell_h 비트맵(행마다 정수, MSB=왼쪽)으로. 없으면 None."""
    g = load(name).get(ord(ch))
    if g is None:
        return None
    w, h, ox, oy, rows = g
    asc = {'Galmuri7': 7, 'Galmuri9': 9, 'Galmuri11-Condensed': 11, 'Galmuri11': 11}[name]
    y0 = (cell_h - asc) // 2 if top is None else top
    out = [0] * cell_h
    for i, r in enumerate(rows):
        v = int(r, 16); nb = len(r) * 4
        y = y0 + i + (asc - h - oy)
        if not (0 <= y < cell_h):
            continue
        line = 0
        for x in range(w):
            if (v >> (nb - 1 - x)) & 1:
                px = x + ox
                if 0 <= px < cell_w:
                    line |= 1 << (cell_w - 1 - px)
        out[y] |= line
    return out


def gb_tile(bits8):
    """8행 비트맵 -> GB 2bpp 16바이트 (플레인1=0, 검은 글자)."""
    t = bytearray()
    for row in bits8:
        t.append(row & 0xFF); t.append(0x00)
    return bytes(t)
