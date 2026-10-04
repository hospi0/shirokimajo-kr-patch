# -*- coding: utf-8 -*-
r"""白き魔女 ~もうひとつの英雄伝説~ (새턴 JP, 2장) 원본 디스크 — 파일 목록·읽기·꺼내기 (2026-10-04)
  디스크 1 = 트랙 1 MODE1 데이터 + 트랙 2 음악 · 디스크 2 = 트랙 1 MODE1 + 트랙 2 MODE2(동영상?) + 트랙 3 음악
  python tools/disc.py [1|2] [extract]  → work/disc/d1|d2/
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, r'C:\claude\project\darksavior-kr-patch\tools')
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')
import iso

R = r'C:\claude\roms\ss\Shiroki Majo - Mou Hitotsu no Eiyuu Densetsu (Japan) (Disc %d)\Shiroki Majo - Mou Hitotsu no Eiyuu Densetsu (Japan) (Disc %d) (Track 1).bin'
TRACK = {1: R % (1, 1), 2: R % (2, 2)}
DISC = os.path.join(ROOT, 'work', 'disc')
_t = {}


def listing(n):
    if n not in _t:
        with open(TRACK[n], 'rb') as fh:
            _t[n] = iso.tree(fh)
    return _t[n]


def read(n, name):
    l, s, *_ = listing(n)[name]
    with open(TRACK[n], 'rb') as fh:
        return iso.read_user(fh, l, (s + 2047) // 2048)[:s]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    t = listing(n)
    for k, v in sorted(t.items(), key=lambda kv: kv[1][0]):
        print('%-32s LBA %7d  %10d B' % (k, v[0], v[1]))
    if 'extract' in sys.argv:
        for k in t:
            p = os.path.join(DISC, 'd%d' % n, k.replace('/', os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(read(n, k))
        print('→', len(t))


if __name__ == '__main__':
    main()
