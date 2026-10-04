# -*- coding: utf-8 -*-
r"""PARAM 번역 용어 통일(2026-10-04) — my files/번역/sm_param_*.tsv(사용자 번역, 손대지 않음) → work/trans/sm_param_ko.tsv
  대사 번역(sm_ko)에서 다수인 표기로 맞춤. 원문에 그 낱말이 든 줄에서만 바꾼다(이름·설명 모두). 자리(바이트) 검사.
python tools/smparam_unify.py"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

# 원문 낱말 → (사용자 번역 표기 → 통일 표기)
UNIFY = [
    ('大イノシシ', '큰멧돼지', '큰 멧돼지'),
    ('アザラシ', '물개', '바다표범'),
    ('大ネズミ', '큰쥐', '큰 쥐'),
    ('大ワシ', '큰독수리', '큰 독수리'),
    ('暴れザル', '난폭한 원숭이', '날뛰는 원숭이'),
    ('ガルガ', '갈가', '가르가'),
    ('銅の鍵', '구리열쇠', '구리 열쇠'),
    ('闇縛り', '어둠결박', '암흑 속박'),
]
FIX = {'P0247': '제로'}                                   # «零。» 자리 5
SHORT = 'work/trans/sm_param_short.tsv'                    # 넘치는 설명 줄인 것(마지막에 덮음)


def nbytes(t):
    return sum(2 if ord(c) > 0x7F else 1 for c in t)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src = {l.split('\t')[0]: l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work/text/sm_param.tsv'), encoding='utf-8') if not l.startswith('#')}
    tr = {}
    d = os.path.join(ROOT, 'my files', '번역')
    for n in sorted(os.listdir(d)):
        if n.startswith('sm_param') and n.endswith('.tsv'):
            for l in open(os.path.join(d, n), encoding='utf-8-sig'):
                if not l.startswith('#') and l.strip():
                    f = l.rstrip('\r\n').split('\t')
                    if len(f) > 5 and f[5].strip():
                        tr[f[0]] = f[5].strip()
    for l in open(os.path.join(ROOT, SHORT), encoding='utf-8'):
        if not l.startswith('#') and l.strip():
            k, t = l.rstrip('\r\n').split('\t')[:2]; FIX[k] = t
    for k in [k for k in tr if k not in src]:                    # 추출 범위 고침(2026-10-04 밤)으로 없어진 번호(P0248·P0249 = 설명 한가운데를 잘못 잡은 칸)
        del tr[k]
    for l in open(os.path.join(ROOT, 'work/trans/sm_param_extra_ko.tsv'), encoding='utf-8'):   # 놓쳤던 몬스터·마법 설명(Claude 번역)
        if not l.startswith('#') and l.strip():
            k, t = l.rstrip('\r\n').split('\t')[:2]; tr.setdefault(k, t)
    ch = 0; over = []
    for k, t in list(tr.items()):
        jp = src[k][4]; t2 = FIX.get(k, t)
        for w, a, b in UNIFY:
            if w in jp and a in t2:
                t2 = t2.replace(a, b)
        if t2 != t:
            ch += 1; tr[k] = t2
        room = int(src[k][2])
        if nbytes(t2) + 1 > room:
            over.append((k, room, t2))
    with open(os.path.join(ROOT, 'work/trans/sm_param_ko.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('#번호\t번역(사용자 번역 + 용어 통일 tools/smparam_unify.py)\n')
        for k in src:
            if k in tr:
                w.write('%s\t%s\n' % (k, tr[k]))
    print('번역 %d · 통일·줄임으로 바뀜 %d · 빈 %d · 자리 넘침 %s' % (len(tr), ch, len(src) - len(tr), over))


if __name__ == '__main__':
    main()
