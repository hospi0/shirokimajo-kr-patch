# -*- coding: utf-8 -*-
r"""타이틀 로고 한글판 시안 (2026-10-04) — tools/smtitle.py 의 320×240 인덱스 그림에서
  «白き魔女» → «하얀 마녀», «もうひとつの英雄伝説» → «또 하나의 영웅전설» (양 끝 ～ 와 덩굴 장식·초록 잎·밑줄 휘선은 원본 그대로)
  ① 지우기: 상자 안 «초록이 아닌» 잉크만 (밑줄 휘선 = 열마다 맨 아래 덩어리의 아래 3줄은 남김)
  ② 색: 원본 글자 화소를 줄별로 «테두리(4이웃에 빈칸)·속» 평균색 실측 → 새 글자에 같은 상대 높이로 입힘
  ③ 모양: 큰 그림으로 그려 줄인 덮임률 ≥0.5 = 잉크, 안티는 직선 모서리 말고 곡선·계단 칸에만
  ④ 원본 팔레트 256색 중 가장 가까운 색(0번 투명 제외)
python tools/smtitle_kr.py → work/title/kr.png · kr_idx.png · cmp.png(원본|한글 3배)"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smtitle

FONT = r'C:\claude\utils\font\nanum-myeongjo\NanumMyeongjoExtraBold.ttf'
TITLE = dict(text='하얀 마녀', box=(91, 36, 229, 76), shear=0.20, erase=(88, 32, 232, 85), stroke=0.9,
             # 원본 결(실측 2026-10-04 사용자 지적): 맨 위 옅은 하늘색 → 위쪽 흰색 → 아래로 갈수록 짙은 파랑·보라
             grad=[(0.00, (176, 196, 228)), (0.12, (236, 240, 252)), (0.40, (220, 228, 244)),
                   (0.62, (150, 176, 220)), (0.82, (104, 120, 188)), (1.00, (84, 72, 136))],
             outline=(96, 112, 176), fullaa=True)
SUB = dict(text='또 하나의 영웅전설', box=(113, 93, 205, 103), shear=0.0, erase=(111, 91, 206, 105), stroke=0.0,
           solid=(188, 84, 56))                                   # 원본 부제 = 결 없이 한 색 + 흰색 쪽 안티(실측·사용자 지적 2026-10-04)
BG = 5
SWOOSH_END = 85                                                       # 원본 휘선은 전부 지우고(덩굴 시작 칸만 남김) 새로 그림
# 밑줄 휘선 = 한 줄로 휘는 «‿» 곡선(2차 베지어: 왼쪽 끝 → 가장 낮은 점 → «녀» ㅕ 세로획 아래). 사용자 요청 2026-10-04
#   왼쪽은 가늘고 옅게(원본 휘선 시작처럼), 오른쪽으로 갈수록 굵고 짙게 → ㅕ 아래와 한 획으로 이어짐
LINK = dict(a=(86.0, 74.6), mid=(150.0, 81.6), b=(220.6, 75.4), w=(1.2, 3.2), c0=(150, 168, 216), core=(88, 82, 142))


def is_green(rgb):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (G > B + 8) & (G > R + 8)                               # ★R 쪽도 엄격히 — 옅은 노르스름한 안티(232,232,216)까지 «잎»으로 봐서 부제 획에 구멍이 났음


def coverage(text, size, shear, w, h, stroke=0.0):
    """글자를 크게 그려 상자(w×h)에 맞춰 줄인 덮임률(0‥1) · stroke = 획 굵히기(최종 화소 단위, 큰 그림에서 윤곽을 두껍게 → 매끈)"""
    k = 8
    f = ImageFont.truetype(FONT, size * k)
    sw = int(round(stroke * k * size / max(h, 1)))
    l, t, r, b = f.getbbox(text, stroke_width=sw)
    im = Image.new('L', (r - l + size * k, b - t + 4 * k), 0)
    ImageDraw.Draw(im).text((size * k // 2 - l, 2 * k - t), text, font=f, fill=255, stroke_width=sw, stroke_fill=255)
    if shear:
        W, H = im.size
        im = im.transform((W + int(H * shear), H), Image.AFFINE, (1, shear, -H * shear, 0, 1, 0), Image.BICUBIC)
    a = np.array(im); ys, xs = np.nonzero(a > 0)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return np.array(Image.fromarray(a).resize((w, h), Image.BOX), float) / 255


def shape(cov):
    ink = cov >= 0.5
    H, W = ink.shape
    pad = np.pad(ink, 1)
    aa = np.zeros_like(cov)
    for y in range(H):
        for x in range(W):
            if ink[y, x] or cov[y, x] < 0.2:
                continue
            py, px = y + 1, x + 1
            straight = False
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if pad[py + dy, px + dx]:
                    qy, qx = dx, dy                                   # 모서리와 나란한 방향
                    a1 = (not pad[py + qy, px + qx]) and pad[py + qy + dy, px + qx + dx]
                    a2 = (not pad[py - qy, px - qx]) and pad[py - qy + dy, px - qx + dx]
                    if a1 and a2:
                        straight = True
            if not straight:
                aa[y, x] = cov[y, x]
    return ink, aa


def sample(rgb, mask, y0, y1):
    """원본 글자 화소의 줄별 (테두리색 = 어두운 25%, 속색 = 밝은 25%) — 위아래 빈 줄은 이웃 값"""
    E, I = [], []
    for y in range(y0, y1 + 1):
        c = rgb[y][mask[y]]
        if len(c) < 3:
            E.append(None); I.append(None); continue
        L = c.sum(1); o = np.argsort(L); q = max(1, len(o) // 4)
        E.append(c[o[:q]].mean(0)); I.append(c[o[-q:]].mean(0))
    def fill(L):
        L = list(L); last = next(v for v in L if v is not None)
        for k, v in enumerate(L):
            if v is None:
                L[k] = last
            else:
                last = v
        return np.array(L)
    return fill(E), fill(I)


def nearest(P, c):
    d = ((P[1:].astype(int) - c) ** 2).sum(1)
    return int(d.argmin()) + 1


def make():
    d = open(os.path.join(ROOT, 'work', 'disc', 'd1', 'SYSTEM', 'LDDATA.PAK'), 'rb').read()
    P = smtitle.palette(d); idx = smtitle.to_index(d).copy(); rgb = P[idx].astype(int)
    ink0 = idx != BG; green = is_green(rgb)
    keep = np.zeros_like(ink0)                                        # 밑줄 휘선 = 실측 윗변 곡선 아래(글자와 안 붙은 열에서 잰 점)
    CX = [86, 98, 110, 122, 134, 146, 158, 170, 182, 194, 206, 212]
    CY = [74, 76, 78, 80, 80, 81, 80, 79, 77, 73, 67, 64]
    for x in range(86, SWOOSH_END + 1):
        top = int(round(np.interp(x, CX, CY)))
        keep[top:TITLE['erase'][3] + 1, x] = True
    out = idx.copy()
    for spec in (TITLE, SUB):
        ex0, ey0, ex1, ey1 = spec['erase']
        m = np.zeros_like(ink0); m[ey0:ey1 + 1, ex0:ex1 + 1] = True
        glyph = m & ink0 & ~green & ~keep
        if spec is TITLE:                                             # «女» 오른쪽 끝 삐침이 장식 소용돌이 위(x 226‥240, y 40‥49)까지 뻗어 있음
            m2 = np.zeros_like(ink0); m2[40:50, 226:241] = True; glyph |= m2 & ink0 & ~green
        bx0, by0, bx1, by1 = spec['box']
        E, I = sample(rgb, glyph, by0, by1)
        out[glyph] = BG
        w, h = bx1 - bx0 + 1, by1 - by0 + 1
        cov = coverage(spec['text'], 40 if spec is TITLE else 12, spec['shear'], w, h, spec['stroke'])
        ink, aa = shape(cov)
        if spec.get('fullaa'):                                        # 원본 로고는 큰 그림을 줄인 것 → 가장자리 전체가 바탕으로 번짐(사용자 요청 2026-10-04)
            aa = np.where(~ink & (cov >= 0.12), cov, 0.0)
        if 'grad' in spec:                                            # 줄별 지정 결: 속 = 결, 테두리 = 결과 윤곽색 반반
            G = spec['grad']; ts = [a for a, _ in G]
            body = [np.array([np.interp(y / (h - 1), ts, [c[i] for _, c in G]) for i in range(3)]) for y in range(h)]
            I = np.array(body); E = (I + np.array(spec['outline'], float)) / 2
        pad = np.pad(ink, 1)
        edge = ink & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        bgc = P[BG].astype(float)
        if 'solid' in spec:                                           # 한 색 + 덮임률만큼 바탕(흰색)과 섞음 — 작은 글씨라 모든 가장자리에 안티
            col = np.array(spec['solid'], float)
            for y in range(h):
                for x in range(w):
                    Y, X = by0 + y, bx0 + x
                    a = min(1.0, cov[y, x] / 0.5)                     # 작은 글씨: 덮임 0.5 이상은 꽉 찬 색(가는 가로획이 옅어져 지워지던 것)
                    if a < 0.2 or green[Y, X]:
                        continue
                    out[Y, X] = nearest(P, bgc + (col - bgc) * a)
            continue
        for y in range(h):
            for x in range(w):
                Y, X = by0 + y, bx0 + x
                if green[Y, X] or keep[Y, X]:
                    continue                                          # 잎·휘선이 앞
                if ink[y, x]:
                    c = E[y] if (edge[y, x] or spec is SUB) else I[y]
                elif aa[y, x] > 0:
                    c = bgc + (E[y] - bgc) * min(1, aa[y, x] * 1.4)
                else:
                    continue
                out[Y, X] = nearest(P, c)
    link(P, out, green)
    return d, P, idx, out


def link(P, out, green):
    """밑줄 휘선 «‿» — 큰 그림에 굵기·색이 변하는 원을 찍어 줄인 덮임률로 칠함(잎이 앞)"""
    k = 8; (ax, ay), (mx, my), (cx, cy) = LINK['a'], LINK['mid'], LINK['b']; w0, w1 = LINK['w']
    bx, by = 2 * mx - (ax + cx) / 2, 2 * my - (ay + cy) / 2           # 가운데 점을 지나는 조절점
    X0, Y0, X1, Y1 = 80, 64, 228, 90
    im = Image.new('L', ((X1 - X0) * k, (Y1 - Y0) * k), 0); dr = ImageDraw.Draw(im)
    N = 400
    for i in range(N + 1):
        t = i / N
        x = (1 - t) ** 2 * ax + 2 * (1 - t) * t * bx + t * t * cx
        y = (1 - t) ** 2 * ay + 2 * (1 - t) * t * by + t * t * cy
        r = (w0 + (w1 - w0) * min(1.0, t * 1.8)) / 2 * k
        X, Y = (x - X0) * k, (y - Y0) * k
        dr.ellipse((X - r, Y - r, X + r, Y + r), fill=255)
    cov = np.array(im.resize((X1 - X0, Y1 - Y0), Image.BOX), float) / 255
    bgc = P[BG].astype(float); c0 = np.array(LINK['c0'], float); c1 = np.array(LINK['core'], float)
    for y in range(Y1 - Y0):
        for x in range(X1 - X0):
            a = min(1.0, cov[y, x] / 0.7)
            Y, X = Y0 + y, X0 + x
            if a < 0.2 or green[Y, X]:
                continue
            if out[Y, X] != BG and a < 0.7:
                continue                                              # 글자 잉크 위에는 옅은 가장자리를 덮지 않음
            t = min(1.0, max(0.0, (X - ax) / (cx - ax)) * 2.2)
            col = c0 + (c1 - c0) * t
            out[Y, X] = nearest(P, bgc + (col - bgc) * a)


def main():
    d, P, idx, out = make()
    os.makedirs(smtitle.OUT, exist_ok=True)
    Image.fromarray(P[out]).save(os.path.join(smtitle.OUT, 'kr.png'))
    Image.fromarray(out).save(os.path.join(smtitle.OUT, 'kr_idx.png'))
    a = Image.fromarray(P[idx]).crop((30, 25, 290, 115)); b = Image.fromarray(P[out]).crop((30, 25, 290, 115))
    c = Image.new('RGB', (260, 184), (0, 0, 0)); c.paste(a, (0, 0)); c.paste(b, (0, 94))
    c.resize((780, 552), Image.NEAREST).save(os.path.join(smtitle.OUT, 'cmp14.png'))
    n2, k = smtitle.from_index(d, out)
    print('타일', k, '/', 1024)


if __name__ == '__main__':
    main()
