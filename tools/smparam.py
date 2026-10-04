# -*- coding: utf-8 -*-
r"""SYSTEM/PARAM.BIN 문자열 추출(2026-10-04) — 몬스터·아이템·마법 이름과 설명
  머리 = u32 20칸 구역 표.
    0 (0x50)   몬스터 레코드 0x4C B × 74 — 이름 칸 = 레코드 머리(32 B)
    2 (0x1CD0) 아이템 레코드 0x44 B × 202 — 이름 칸 = 레코드 머리(20 B)
    4 (0x6F8C) 마법 레코드 0x50 B × 71 — 이름 칸 = 레코드 머리, 뒤(0x8475‥)에 마법 설명 묶음
    3 (0x52BC) 아이템 설명 묶음 — «＄» = 줄바꿈, 00 으로 이어 붙음(파일 안에 설명을 가리키는 오프셋 없음 → 차례로 셈)
    6‥19 수치표
  레코드 이름 = 칸 머리부터 00 까지(한자만이어도) · 묶음 문자열 = 00 바로 뒤에서 시작하는 SJIS(전각 1자 이상).
  자리 = 끝 00 뒤 첫 비영 바이트까지(제자리 예산, 레코드 이름은 칸 크기로 자름).
python tools/smparam.py → work/text/sm_param.tsv + my files/tsv/sm_param_NNN.tsv(29KB 단위)"""
import collections, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smtext

# ★(2026-10-04 밤) 몬스터 = 구역 크기 0x1C80 / 0x4C = 96칸(74 로 잘라 76‥94번 «大イノシシ» 등 14마리 빠졌음) ·
#   마법 = 64칸(71 로 읽어 설명 묶음 앞 16줄이 빠지고 설명 한가운데를 «레코드»로 잘못 잡았음 — P0248·P0249 폐기)
RECS = [('몬스터', 0x50, 0x4C, 96, 32), ('아이템', 0x1CD0, 0x44, 202, 20), ('마법', 0x6F8C, 0x50, 64, 22)]
POOLS = [('아이템 설명', 0x52BC, 0x6F8C), ('마법 설명', 0x6F8C + 64 * 0x50 - 1, 0x85EC)]


def sjis_end(p, o, lim):
    e = o; full = 0
    while e < lim and p[e]:
        b = p[e]
        if smtext.lead(b):
            try:
                p[e:e + 2].decode('cp932')
            except UnicodeDecodeError:
                return None
            full += 1; e += 2
        elif 0x20 <= b < 0x7F or 0xA1 <= b <= 0xDF:
            e += 1
        else:
            return None
    return e if full and e < lim else None


def strings(p):
    out = []
    for kind, base, stride, n, field in RECS:
        for k in range(n):
            o = base + k * stride
            e = sjis_end(p, o, o + field)
            if e is None:
                continue
            room = e + 1
            while room < o + field and p[room] == 0:
                room += 1
            out.append((o, e, room - o, '%s %d' % (kind, k), smtext.show(p[o:e])))
    for kind, s, lim in POOLS:
        o = s + 1
        while o < lim:
            if p[o] and p[o - 1] == 0 and smtext.lead(p[o]):
                e = sjis_end(p, o, lim)
                if e is not None:
                    room = e + 1
                    while room < lim and p[room] == 0:
                        room += 1
                    out.append((o, e, room - o, kind, smtext.show(p[o:e])))
                    o = e + 1; continue
            o += 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = open(os.path.join(ROOT, 'work', 'disc', 'd1', 'SYSTEM', 'PARAM.BIN'), 'rb').read()
    rows = strings(p)
    head = '#번호\t위치\t자리(끝 00 포함)\t구분\t원문\t번역\n'
    tsv = os.path.join(ROOT, 'work', 'text', 'sm_param.tsv'); ids = {}   # 번호는 위치로 고정(번역 표 sm_param_ko 가 번호로 묶임) — 새 줄은 뒤 번호
    if os.path.exists(tsv):
        for l in open(tsv, encoding='utf-8'):
            if l.startswith('P'):
                f = l.split('\t'); ids[int(f[1], 16)] = int(f[0][1:])
    nxt = max(ids.values(), default=0); num = []
    for o, *_ in rows:
        if o not in ids:
            nxt += 1; ids[o] = nxt
        num.append(ids[o])
    lines = ['P%04d\t%05X\t%d\t%s\t%s\t' % (n, o, room, kind, t) for n, (o, e, room, kind, t) in sorted(zip(num, rows))]
    open(os.path.join(ROOT, 'work', 'text', 'sm_param.tsv'), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(lines) + '\n')
    chunks = [[]]; size = 0
    for l in lines:
        b = len((l + '\n').encode('utf-8'))
        if size + b > 29 * 1024 and chunks[-1]:
            chunks.append([]); size = 0
        chunks[-1].append(l); size += b
    if len(chunks) > 1 and sum(len((l + '\n').encode('utf-8')) for l in chunks[-1]) < 8 * 1024:
        chunks[-2] += chunks.pop()
    for i, c in enumerate(chunks if '--split' in sys.argv else []):   # my files/tsv 사본은 요청할 때만
        open(os.path.join(ROOT, 'my files', 'tsv', 'sm_param_%03d.tsv' % (i + 1)), 'w', encoding='utf-8', newline='\n').write(head + '\n'.join(c) + '\n')
    c = collections.Counter(kind.split()[0] for *_, kind, t in rows)
    jp = sum(1 for *_, t in rows for ch in t if ord(ch) > 0x3000)
    print('문자열 %d (%s) · 전각 %d자 · 파일 %d개' % (len(rows), dict(c), jp, len(chunks)))


if __name__ == '__main__':
    main()
