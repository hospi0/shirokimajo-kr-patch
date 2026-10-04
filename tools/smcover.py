# -*- coding: utf-8 -*-
r"""책 표지 제목 그림 (2026-10-04)
  BOOKPRG 0x060E28A0: 정보 기록 [0] = 표지 그림(0 이면 기본 가죽) · [4‥6] = 표지 색(RGB) · +8 부터 8B 항목 [블록 포인터][x][y][?][0] 이 0 까지
  블록 = [팔레트 256색 RGB555 0x200B(앞 32색만 씀)][폭 u16 @+0x200][높이 u16 @+0x202][8bpp 화소 @+0x204] (무압축)
  ★처음엔 «팔레트+156 부터 120폭»으로 잘못 보고 덮어 +0x200 폭·높이를 지워 표지 제목이 사라졌음(실기 2026-10-04) — 머리는 건드리지 말 것.
  색 번호 = 밝기(1 가장 밝은 금색 → 30 어두운 가장자리, 0 투명) — 명조체 안티앨리어싱.
  python tools/smcover.py  → my files/그래픽/책표지_제목_비교(원본_한글).png"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONT = r'C:\Windows\Fonts\batang.ttc'

# 표지 제목(게임 안 표기와 같게 — 책 첫 쪽 제목 줄·«책등에 《…》» 대사). {책: [항목0 줄들, 항목1 줄들…]}, None = 원본 그대로.
# ⛔영어 제목(02 My Diary·03 Captain Thomas·29/30 mona)은 원본 그대로.
SUB = {4: 'Ⅰ', 5: 'Ⅱ', 6: 'Ⅲ', 7: 'Ⅳ', 8: 'Ⅴ', 9: 'Ⅵ', 10: 'Ⅶ', 11: 'Ⅷ', 12: 'Ⅸ'}
SAFI = {4: '～두 검사～', 5: '～어느 결투～', 6: '～흔들리는 자줏빛 연기～', 7: '～팔의 상처～', 8: '～회색 거리～', 9: '～악몽～',
        10: '～아버지의 검～', 11: '～재대결의 때～', 12: '～복수의 칼날～'}
TITLES = {0: [['마녀의 순례']], 1: [['각지의 샤리네']], 13: [['캡틴', '토머스의 대항해']], 14: [['해적왕 라몬의', '숨겨진 보물']],
          15: [['대마도사', '오르테가의', '용 퇴치']], 16: [['안데라의 호수']], 17: [['하얀 마녀의 말']], 18: [['요술사', '게페우스의 보물']],
          19: [['루피나스', '호숫가에서']], 20: [['괴걸', '와일드캣']],
          21: [['검사 교본 Ⅰ'], ['뱅커 훅 4세']], 22: [['검사 교본 Ⅱ'], ['뱅커 훅 4세']], 23: [['검사 교본 Ⅲ'], ['뱅커 훅 4세']],
          24: [['순례자의 마음가짐']], 25: [['이그니스의 샤리네', '～그 유래～']], 26: [['기념 노트']], 28: [['검은 파도를', '소환하는 법']],
          31: [['항해 일지']], 32: [['항해 일지']], 33: [['순례자 명부']], 34: [['순례자 명부']], 35: [['즐거운 요리']], 36: [['기념 노트']],
          37: [['마녀의 순례']], 38: [['마녀의 순례']], 39: [['마녀의 순례']]}
for _k in SUB:
    TITLES[_k] = [['여검사 사피 ' + SUB[_k], SAFI[_k]]]


def u32(b, i):
    return struct.unpack_from('>I', b, i)[0]


def blocks(b):
    """→ [(블록 위치, 폭, 높이)]"""
    info = u32(b, 0); k = info + 8; out = []
    while u32(b, k):
        p = u32(b, k); w, h = struct.unpack_from('>HH', b, p + 0x200)
        assert 0 < w <= 320 and 0 < h <= 240 and p + 0x204 + w * h <= len(b), (hex(p), w, h)
        out.append((p, w, h)); k += 8
    return out


def render(lines, w, h):
    """한글 줄들 → w×h 색 번호(1 밝음‥30 어두움, 0 투명). 한 줄 = 가운데, 여러 줄 = 첫 줄 왼쪽·끝 줄 오른쪽(원본 배치)"""
    from PIL import Image, ImageDraw, ImageFont
    lines = [t.replace('～', '∼') for t in lines]                   # 바탕체 「～」는 위에 붙은 작은 물결 — 가운데 물결 「∼」로
    n = len(lines); S = 4
    size = 24
    while size > 9 and n * (size + 2) > h:
        size -= 1
    lh = size + 2
    im = Image.new('L', (w * S, h * S), 0); d = ImageDraw.Draw(im)
    top = (h - n * lh) // 2
    sizes = []
    for t in lines:                                                   # 줄마다 폭에 맞게(긴 부제만 줄어듦)
        s = size
        while s > 9 and ImageFont.truetype(FONT, s * S).getlength(t) > (w - 2) * S:
            s -= 1
        sizes.append(s)
    for i, t in enumerate(lines):
        f = ImageFont.truetype(FONT, sizes[i] * S)
        tw = f.getlength(t)
        x = (w * S - tw) / 2 if n == 1 else (S if i == 0 else (w - 1) * S - tw if i == n - 1 else (w * S - tw) / 2)
        y = (top + i * lh) * S - f.getbbox('가')[1] + S
        d.text((x, y), t, fill=255, font=f)
    a = np.asarray(im.resize((w, h), Image.LANCZOS), np.float32) / 255.0
    return np.where(a > 0.12, np.clip(np.rint(1 + (1 - a) * 29), 1, 30), 0).astype(np.uint8)


def patch(b, items):
    nb = bytearray(b)
    for (p, w, h), lines in zip(blocks(b), items):
        if lines:
            nb[p + 0x204:p + 0x204 + w * h] = render(lines, w, h).tobytes()   # 머리(팔레트·폭·높이)는 그대로
    return bytes(nb)


def sheet(path):
    from PIL import Image, ImageDraw, ImageFont
    SD = os.path.join(ROOT, 'work', 'disc', 'd1', 'SYSTEM'); rows = []
    for k in sorted(TITLES):
        b = open(os.path.join(SD, 'BOOK%02d.BIN' % k), 'rb').read(); nb = patch(b, TITLES[k])
        for j, (p, w, h) in enumerate(blocks(b)):
            P = [struct.unpack_from('>H', b, p + 2 * i)[0] for i in range(256)]
            ims = []
            for src in (b, nb):
                im = Image.new('RGB', (w, h), (60, 30, 10))
                for y in range(h):
                    for x in range(w):
                        v = src[p + 0x204 + y * w + x]
                        if v:
                            c = P[v]; im.putpixel((x, y), ((c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8))
                ims.append(im.resize((w * 3, h * 3), 0))
            rows.append(('BOOK%02d' % k + ('' if not j else '-%d' % j), ims))
    F = ImageFont.truetype('malgun.ttf', 16)
    H = sum(r[1][0].size[1] + 10 for r in rows) + 30
    out = Image.new('RGB', (110 + 2 * (128 * 3 + 20), H), (20, 20, 20)); d = ImageDraw.Draw(out)
    d.text((110, 6), '원본', fill=(255, 255, 255), font=F); d.text((110 + 128 * 3 + 20, 6), '한글', fill=(255, 255, 255), font=F)
    y = 30
    for name, (a, b2) in rows:
        d.text((6, y + 6), name, fill=(255, 255, 255), font=F)
        out.paste(a, (110, y)); out.paste(b2, (110 + 128 * 3 + 20, y)); y += a.size[1] + 10
    out.save(path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p = os.path.join(ROOT, 'my files', '그래픽', '책표지_제목_비교(원본_한글).png'); sheet(p); print(p)
