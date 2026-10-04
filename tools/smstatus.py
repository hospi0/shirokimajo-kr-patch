# -*- coding: utf-8 -*-
r"""상태창 캐릭터 이름 그림 한글 (2026-10-04)
  출처: SYSTEM/BATTLE.BIN 묶음의 «status.spr»(LZSS, tools/smlz) = 가로 128px 4bpp 그림판(64 B/줄, 128줄).
        왼쪽 = 상태 패널 배경, x 40‥79 · y 8k‥8k+7 = 캐릭터 k 이름 띠 40×8 (0.BIN 0x0602270C 가 40×8 스프라이트로 VDP1 에 올림).
  원본 띠 짜임: 글자 획 = 어두운 색(2·1·5…) + 둘레 밝은 테두리 9, 글자 뒤 장식 줄(7/2/5/9 네 줄, x 39 에 끝 모양).
  한글: 바탕 띠 9(원본 모양) 위에 갈무리7 획 = 밝은 색 1‥4(위→아래) · 8방향 테두리 9 · 장식 줄 = 원본 크리스(1번) 띠의 4‥7행 줄을 이름 끝 +2 부터 이어 붙임.
  압축: 원래 해제 루틴과 같은 LZSS(256B 고리·쓰기 0xEF·니블 길이 짝) — 탐욕 최장 일치, 왕복 검증.
python tools/smstatus.py  → work/view/status_names.png (원본 | 한글)"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smlz, bdf

NAMES = ['줄리오', '크리스', '샤라', '구스', '로디', '필리', '알프', '모리슨', '조안나', '스텔라', '바다트', '밤밤', '듀르젤', '루레']
X0, W, H = 40, 40, 8
REF = 1                                   # 장식 줄을 빌려 올 띠(크리스: 줄이 x22‥39)
REF_LINE_X = 22
SHADE = [1, 1, 2, 2, 3, 3, 4, 4]             # 팔레트(색 뱅크 0x47C0, CRAM 바이트 뒤집어 읽음): 1 가장 밝음 → 5, 9 = 어두운 회색


def getp(s, x, y):
    return (s[y * 64 + x // 2] >> (4 if x % 2 == 0 else 0)) & 15


def setp(s, x, y, v):
    i = y * 64 + x // 2
    s[i] = (s[i] & 0x0F) | (v << 4) if x % 2 == 0 else (s[i] & 0xF0) | v


def glyphs(text):
    G = bdf.load('Galmuri7'); out = []; x = 1
    mask = [[0] * W for _ in range(H)]
    for ch in text:
        w, h, ox, oy, rows = G[ord(ch)]
        for i, r in enumerate(rows):
            y = 6 - (oy + h - 1) + i                         # 밑선 = 6행 (7×7 한글 0‥6행)
            v = int(r, 16) >> (len(r) * 4 - w) if r else 0
            for k in range(w):
                if v >> (w - 1 - k) & 1 and 0 <= y < H and 0 <= x + ox + k < W:
                    mask[y][x + ox + k] = 1
        x += 8
    return mask, x - 1


def render(spr):
    s = bytearray(spr)
    ref = [[getp(spr, X0 + x, REF * 8 + y) for x in range(W)] for y in range(H)]
    for k, name in enumerate(NAMES):
        mask, end = glyphs(name)
        strip = [[0] * W for _ in range(H)]
        start = end + 2
        # 바탕 띠 = 어두운 회색 9 — ★원본 규칙(14명 띠 전부 대조, 실기 2026-10-04): 0‥3행은 획 둘레 1px 만(아래 테두리 칠하기),
        #   4‥7행만 x0 부터 장식 줄까지 꽉 채움. (옛: 1‥3행을 이름 끝+2 까지 직사각형으로 채워 글자 위가 회색 덩어리 — 원본 «オ» 끝 모양)
        for y in range(4, H):
            for x in range(0, start):
                strip[y][x] = 9
        for y in range(H):
            for x in range(W):
                if mask[y][x]:
                    strip[y][x] = SHADE[y]                           # 획 = 밝은 색 1‥4(위→아래 그라데이션, 원본과 같음)
                elif any(0 <= y + dy < H and 0 <= x + dx < W and mask[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    strip[y][x] = 9                                  # 테두리 = 어두운 회색 9
        assert start <= REF_LINE_X + 6, ('이름이 너무 김', name, end)
        for y in range(4, H):                                        # 장식 줄 = 4‥7행만
            for x in range(start, W):
                rx = max(x, REF_LINE_X)
                if ref[y][rx] and not strip[y][x]:
                    strip[y][x] = ref[y][rx]
        for y in range(H):
            for x in range(W):
                setp(s, X0 + x, k * 8 + y, strip[y][x])
    return bytes(s)


def compress(data):
    """원래 해제 루틴과 짝이 맞는 LZSS — 일치 길이 2‥17, 오프셋 = 고리 절대 위치"""
    ring = bytearray(256); w = 0xEF; out = bytearray(); i = 0
    flag_pos = None; nbits = 0; pend_nib = None              # 다음 복사가 쓸 아래 니블 자리(바이트 위치)
    while i < len(data):
        if nbits == 0:
            flag_pos = len(out); out.append(0); nbits = 8
        best_len, best_off = 0, 0
        for off in range(256):
            l = 0; tmp = bytearray(ring); ww = w
            while l < 17 and i + l < len(data):
                c = tmp[(off + l) & 0xFF]
                if c != data[i + l]:
                    break
                tmp[ww] = c; ww = (ww + 1) & 0xFF; l += 1
            if l > best_len:
                best_len, best_off = l, off
                if l == 17:
                    break
        bit = 0x80 >> (8 - nbits)
        if best_len >= 2:
            out.append(best_off)
            if pend_nib is None:
                pend_nib = len(out); out.append((best_len - 2) << 4)
            else:
                out[pend_nib] |= best_len - 2; pend_nib = None
            for k in range(best_len):
                c = ring[(best_off + k) & 0xFF]; ring[w] = c; w = (w + 1) & 0xFF
            i += best_len
        else:
            out[flag_pos] |= bit
            c = data[i]; out.append(c); ring[w] = c; w = (w + 1) & 0xFF; i += 1
        nbits -= 1
    return bytes(out)


def battle_with(battle, name, data):
    """BATTLE.BIN 묶음에서 항목 name 의 압축 데이터를 바꿔 다시 짠다(다른 항목은 바이트 그대로)"""
    out = bytearray()
    for nm, o, p, size in smlz.entries(battle):
        n = struct.unpack_from('>I', battle, o)[0]
        if nm == name:
            comp = compress(data)
            assert smlz.decompress(struct.pack('<I', len(data)) + comp, 0)[0] == data, '압축 왕복 다름'
            head = battle[o + 4:p]
            ent = head + struct.pack('<I', len(data)) + comp
            out += struct.pack('>I', 4 + len(ent)) + ent
        else:
            out += battle[o:o + n]
    return bytes(out)


def build(battle):
    ent = {nm: (o, p, size) for nm, o, p, size in smlz.entries(battle)}
    o, p, size = ent['status.spr']
    spr, _ = smlz.decompress(battle, p, size)
    new = render(spr)
    return battle_with(battle, 'status.spr', new), spr, new


def preview(a, b, out):
    from PIL import Image
    im = Image.new('L', (W * 2 + 4, H * len(NAMES)), 0)
    for k in range(len(NAMES)):
        for y in range(H):
            for x in range(W):
                for j, s in enumerate((a, b)):
                    v = getp(s, X0 + x, k * 8 + y)
                    if v:
                        im.putpixel((j * (W + 4) + x, k * 8 + y), 255 if v == 9 else 60 + v * 12)
    im.resize((im.width * 6, im.height * 6), Image.NEAREST).save(out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    bt = open(os.path.join(ROOT, 'work', 'disc', 'd1', 'SYSTEM', 'BATTLE.BIN'), 'rb').read()
    nb, a, b = build(bt)
    preview(a, b, os.path.join(ROOT, 'work', 'view', 'status_names.png'))
    ent0 = {nm: o for nm, o, *_ in smlz.entries(bt)}; ent1 = {nm: o for nm, o, *_ in smlz.entries(nb)}
    print('BATTLE.BIN %d → %d B (status.spr 압축 %d → %d)' % (len(bt), len(nb),
          struct.unpack_from('>I', bt, ent0['status.spr'])[0], struct.unpack_from('>I', nb, ent1['status.spr'])[0]))
