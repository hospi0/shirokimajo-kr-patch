# -*- coding: utf-8 -*-
r"""뒤 트랙(디스크 2 트랙 2 MODE2) 섹터 머리 주소(MSF)를 +n 섹터 — 트랙 1 이 커졌을 때 (2026-10-04)
  섹터 머리 = 동기 12B + MSF(BCD) 3B + 모드. MODE1(프리갭) 은 ECC 가 머리를 포함 → cdmode1.fix 로 다시 계산.
  MODE2 Form1 ECC 는 머리를 0 으로 놓고 계산(주소 무관) · Form2 는 ECC 없음 → 주소만 고친다.
python tools/shifttrack.py 원본.bin 결과.bin 섹터수"""
import sys
import iso, cdmode1

SYNC = iso.SYNC


def unbcd(b):
    return (b >> 4) * 10 + (b & 15)


def shift(src, dst, n):
    m1 = m2 = 0
    with open(src, 'rb') as fi, open(dst, 'wb') as fo:
        while True:
            s = fi.read(2352)
            if not s:
                break
            s = bytearray(s)
            if s[:12] == SYNC:
                f = (unbcd(s[12]) * 60 + unbcd(s[13])) * 75 + unbcd(s[14]) + n
                s[12:15] = bytes([iso.bcd(f // 4500), iso.bcd(f // 75 % 60), iso.bcd(f % 75)])
                if s[15] == 1:
                    s = bytearray(cdmode1.fix(s)); m1 += 1
                else:
                    m2 += 1
            fo.write(s)
    return m1, m2


if __name__ == '__main__':
    print(shift(sys.argv[1], sys.argv[2], int(sys.argv[3])))
