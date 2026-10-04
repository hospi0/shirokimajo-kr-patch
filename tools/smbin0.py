# -*- coding: utf-8 -*-
r"""0.BIN 문자열(메뉴·장 제목·이름·시스템 문구) 추출 — «u32 포인터가 가리키는 SJIS 문자열» 기준 (2026-10-04)
  첫 추출(smtext)은 가나 비율로 거르는 바람에 한자만인 메뉴 낱말(道具 등)을 놓쳤고, 앞 문자열의 맞춤 바이트(09)를
  {09} 로 붙여 뽑았다 → 0.BIN 은 포인터 대상에서 다시 뽑는다.
  0.BIN 적재 0x06004000. 문자열 = 대상부터 00 까지(SJIS·반각·제어 01‥1F), 전각 글자 1자 이상.
  자리(room) = 대상부터 «다음 포인터 대상» 또는 00 이 아닌 바이트 전까지(끝 00 포함) — 제자리 예산.
  번역 = sm_ko 에 같은 원문(또는 앞에 {09} 붙은 원문)이 있으면 그 번역에서 {09}+인자 글자 흔적을 걷어 가져옴.
python tools/smbin0.py → work/text/sm_bin0.tsv (번호 B0001·위치·자리·포인터 수·원문·기존 번역)"""
import collections, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smtext

LOAD = 0x06004000


def pointers(d):
    ptr = collections.defaultdict(list)
    for i in range(0, len(d) - 3, 2):
        v = struct.unpack_from('>I', d, i)[0]
        if LOAD <= v < LOAD + len(d):
            ptr[v - LOAD].append(i)
    return ptr


def string_at(d, o):
    e = o; full = 0
    while e < len(d) and d[e]:
        b = d[e]
        if smtext.lead(b):
            if e + 1 >= len(d) or not smtext.trail(d[e + 1]):
                return None
            try:
                d[e:e + 2].decode('cp932')
            except UnicodeDecodeError:
                return None
            full += 1; e += 2; continue
        if b < 0x20 or 0x20 <= b < 0x7F or 0xA1 <= b <= 0xDF:
            e += 1; continue
        return None
    if e >= len(d) or not full or e - o > 300:
        return None
    return e


def strings(d):
    ptr = pointers(d); out = []
    targets = sorted(ptr)
    for o in targets:
        e = string_at(d, o)
        if e is None:
            continue
        t = smtext.show(d[o:e])
        room = e + 1
        while room < len(d) and d[room] == 0 and room not in ptr:
            room += 1
        out.append((o, e, room - o, len(ptr[o]), t))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = open(os.path.join(ROOT, 'work/disc/d1/0.BIN'), 'rb').read()
    ko = {}
    for l in open(os.path.join(ROOT, 'work/trans/sm_ko.tsv'), encoding='utf-8'):
        if not l.startswith('#'):
            f = l.rstrip('\n').split('\t')
            if f[4]:
                ko[f[3]] = f[4]
    rows = strings(d); n = 0; have = 0
    with open(os.path.join(ROOT, 'work/text/sm_bin0.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('#번호\t위치\t자리(끝 00 포함)\t포인터 수\t원문\t기존 번역\n')
        for o, e, room, np_, t in rows:
            tr = ko.get(t, '')
            if not tr:
                for k, v in ko.items():
                    if k.startswith('{09}') and k[5:] == t and v.startswith('{09}'):
                        tr = v[4:]; break                                   # «{09}ス텔라» → «ス텔라» (사람이 손볼 것)
            n += 1; have += bool(tr)
            w.write('B%04d\t%06X\t%d\t%d\t%s\t%s\n' % (n, o, room, np_, t, tr))
    print('0.BIN 문자열 %d · 기존 번역 있음 %d' % (n, have))


if __name__ == '__main__':
    main()
