# -*- coding: utf-8 -*-
r"""월드맵 지명판(2026-10-04) — SYSTEM/SLMAPDAT.BIN 0xD4DC 부터 80×16 4bpp(0x280 B) × 34장, 색 표 0xD4BC(16색)
  (실기 스샷 «ディーネ / 緑の高原» 판 = VDP1 명령 2(늘림) src 0x7C180·0x7C680 → 파일 칸 2·1 과 바이트 일치)
  원본 글자 규칙: 바탕(돌 무늬, 34장 최빈값) 위에 밝은 색 두 개 — 가로로 이어진 획 = 색 2, 나머지(세로·점) = 색 1. 그림자·테두리 없음.
  글자 칸 = 3‥13행(11줄) · 5‥74열(70px). 원본처럼 짧은 이름은 판 폭에 맞춰 벌린다(낱말 사이는 4px 더).
  글꼴 Galmuri11(11×11, bdf 직독).
python tools/smplate.py → work/build/plates.png (확인용 확대 그림)"""
import collections, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf

BASE = 0xD4DC; SZ = 0x280; N = 34; PAL = 0xD4BC
X0, X1, Y0 = 5, 75, 3                  # 글자 칸 [X0, X1) · 위 행(원본 잉크 5‥74열)
WORD_GAP = 4
HALF = 6                               # 반각 = 12px 칸의 절반
NAMES = ['라그픽 마을', '녹색 고원', '디네', '라구나', '니일리', '알데', '테그라', '치타', '네르바 성', '튀에르',
         '쌍룡 계곡 관문', '다이스', '다트', '삼도교', '볼트', '이그니스', '안데라', '정적의 숲', '시풀', '북 히츠 가도',
         '오르도스', '하이젠', '루이즈 관문', '홀크', '홀크 요새', '망사 관문', '바라카', '유적', '메마른 사막', '기드넬',
         '딜트 관문', '아로자', '돌페스', '루드']
JP = ['ラグピック村', '緑の高原', 'ディーネ', 'ラグーナ', 'ニーリ', 'アルデ', 'テグラ', 'チッタ', 'ネルバ城', 'テュエール',
      '双竜谷の関所', 'ダイス', 'ダーツ', '三都橋', 'ボルト', 'イグニス', 'アンデラ', '静寂の森', 'シフール', '北ヒーツ街道',
      'オルドス', 'ハイゼン', 'ルイズの関所', 'ホルク', 'ホルクの砦', '望砂の関所', 'バラカ', '遺跡', '乾きの砂漠', 'ギドネル',
      'ディルトの関所', 'アロザ', 'ドルフェス', 'ルード']


def unpack(blk):
    return [[(blk[y * 40 + x // 2] >> 4) if x % 2 == 0 else blk[y * 40 + x // 2] & 15 for x in range(80)] for y in range(16)]


def pack(px):
    return bytes((px[y][x] << 4) | px[y][x + 1] for y in range(16) for x in range(0, 80, 2))


def background(d):
    """34장 최빈값 — 글자 칸 안(3‥13행·3‥76열)은 글자색(1·2·4·5·f)을 빼고 고른다
    (안 빼면 여러 판이 같은 자리에 찍은 마지막 글자 획이 바탕으로 뽑혀 오른쪽 끝에 점이 남음 — 5행 71열, 사용자 지적 2026-10-04)"""
    P = [unpack(d[BASE + k * SZ:BASE + (k + 1) * SZ]) for k in range(N)]
    ink = {1, 2, 4, 5, 15}

    def pick(y, x):
        c = collections.Counter(P[k][y][x] for k in range(N))
        if 3 <= y <= 13 and 3 <= x <= 76:
            c = collections.Counter({k: v for k, v in c.items() if k not in ink}) or c
        return c.most_common(1)[0][0]
    return [[pick(y, x) for x in range(80)] for y in range(16)]


def glyph(ch):
    w, h, ox, oy, rows = bdf.load('Galmuri11')[ord(ch)]
    bits = [[(int(r, 16) >> (len(r) * 4 - 1 - x)) & 1 for x in range(w)] for r in rows]
    return w, bits


def layout(name):
    """→ [(x, 글자)] — 음절 사이 간격 g 를 판 폭에 맞춰 고르게(낱말 사이는 +WORD_GAP)"""
    words = name.split(' ')
    syl = [c for w in words for c in w]; n = len(syl)
    wgaps = len(words) - 1
    ink = sum(glyph(c)[0] for c in syl)
    pad = {2: 2 * HALF, 3: HALF}.get(n, 0)                                # 양쪽 들임: 두 글자 = 전각, 세 글자 = 반각(양 끝으로 벌리면 횡함 — 사용자 2026-10-05)
    x0 = X0 + pad; room = X1 - X0 - 2 * pad; wg = WORD_GAP
    if wgaps and ink + wgaps * wg > room:                                 # 넘칠 때만 낱말 사이를 줄임(최소 2px — «쌍룡 계곡 관문»)
        wg = (room - ink) // wgaps
    if wg < 2:
        raise SystemExit('⛔지명판 넘침 %s: %dpx > %d' % (name, ink + wgaps * 2, room))
    g = 0 if n == 1 else (room - ink - wgaps * wg) / (n - 1)
    out = []; x = x0 if n > 1 else x0 + (room - ink) / 2
    for wi, w in enumerate(words):
        for ci, c in enumerate(w):
            out.append((round(x), c)); x += glyph(c)[0] + g
        x += wg
    return out


def draw(bg, name):
    px = [row[:] for row in bg]
    ink = [[0] * 80 for _ in range(16)]
    for x0, c in layout(name):
        w, bits = glyph(c)
        for y, r in enumerate(bits):
            for x, b in enumerate(r):
                if b and 0 <= x0 + x < 80:
                    ink[Y0 + y][x0 + x] = 1
    for y in range(16):
        for x in range(80):
            if ink[y][x]:
                px[y][x] = 2 if (x > 0 and ink[y][x - 1]) or (x < 79 and ink[y][x + 1]) else 1
    return px


def build(d):
    """SLMAPDAT 원본 → 새 바이트"""
    assert len(NAMES) == len(JP) == N
    out = bytearray(d); bg = background(d)
    for k, nm in enumerate(NAMES):
        out[BASE + k * SZ:BASE + (k + 1) * SZ] = pack(draw(bg, nm))
    return bytes(out)


def preview(d, path, S=4):
    import struct
    from PIL import Image
    pal = []
    for i in range(16):
        c = struct.unpack_from('>H', d, PAL + i * 2)[0]
        pal.append(((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3))
    new = build(d); cols = 4
    img = Image.new('RGB', (cols * (80 * S + 12) + 8, ((2 * N + cols - 1) // cols) * (16 * S + 8) + 8), (30, 30, 30))
    for k in range(N):
        for j, src in enumerate((d, new)):                               # 원본 · 한글 나란히
            px = unpack(src[BASE + k * SZ:BASE + (k + 1) * SZ])
            idx = 2 * k + j; ox = 8 + (idx % cols) * (80 * S + 12); oy = 8 + (idx // cols) * (16 * S + 8)
            for y in range(16):
                for x in range(80):
                    for yy in range(S):
                        for xx in range(S):
                            img.putpixel((ox + x * S + xx, oy + y * S + yy), pal[px[y][x]])
    img.save(path)


if __name__ == '__main__':
    import disc
    d = disc.read(1, 'SYSTEM/SLMAPDAT.BIN')
    p = os.path.join(ROOT, 'work', 'build', 'plates.png'); preview(d, p); print(p)
