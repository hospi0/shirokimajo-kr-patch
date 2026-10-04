# -*- coding: utf-8 -*-
r"""SYSTEM/BOOK*.BIN 책 문서 되넣기(2026-10-04)
  구조: 머리 = u32 구역 표 → 구역마다 u32 «줄 문자열 오프셋» 표(파일 안 오프셋) → 줄 문자열(SJIS, 00 끝). 줄바꿈 = 줄마다 따로.
  문자열 = 4바이트 정렬 u32 값이 가리키는 곳에서 00 까지 SJIS(전각 1자 이상) — 그 u32 의 앞뒤도 문자열 대상인 경우(줄 오프셋 표)만.
  번역 = sm_ko(원문 show 문자열 일치). 새 줄이 원래 자리(다음 문자열/표 전까지 00 포함)에 들어가면 제자리,
  넘치면 파일 끝에 붙이고 그 줄을 가리키는 u32 를 전부 고친다(파일이 커짐).
  from smbook import build; new = build(data, KO, encode)"""
import collections, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smtext


def targets(d):
    ptr = collections.defaultdict(list)
    for i in range(0, len(d) - 3, 4):
        v = struct.unpack_from('>I', d, i)[0]
        if 0 < v < len(d):
            ptr[v].append(i)
    out = {}
    for o, refs in ptr.items():
        e = o; full = 0; ok = True
        while e < len(d) and d[e]:
            b = d[e]
            if smtext.lead(b):
                if e + 1 >= len(d):
                    ok = False; break
                try:
                    d[e:e + 2].decode('cp932')
                except UnicodeDecodeError:
                    ok = False; break
                full += 1; e += 2
            elif 0x20 <= b < 0x7F or 0xA1 <= b <= 0xDF or b in (0x0D, 0x0A):
                e += 1
            else:
                ok = False; break
        if ok and full and e < len(d):
            out[o] = (e, refs)
    # 줄 오프셋 표 안의 값만 포인터로 인정: 앞이나 뒤 4바이트도 문자열 대상(또는 표 끝 0)인 u32 — 우연히 같은 값인 데이터는 제외
    val = lambda i: struct.unpack_from('>I', d, i)[0] if 0 <= i <= len(d) - 4 else -1
    for o in list(out):
        e, refs = out[o]
        refs = [r for r in refs if val(r - 4) in out or val(r + 4) in out]
        if refs:
            out[o] = (e, refs)
        else:
            del out[o]
    return out


def build(d, lookup, encode, stat):
    """lookup(원문) → 번역 문자열 | None"""
    orig = bytes(d); d = bytearray(d); T = targets(orig); tail = bytearray()
    starts = sorted(T)
    # 다른 줄과 바이트가 겹치는 줄(줄 가운데를 가리키는 오프셋)은 제자리에 쓰면 서로 덮으므로 무조건 끝에 붙인다
    overlap = set()
    for i, o in enumerate(starts):
        for o2 in starts[i + 1:]:
            if o2 > T[o][0]:
                break
            overlap.update((o, o2))
    for o in starts:
        e, refs = T[o]
        src = smtext.show(orig[o:e])
        t = lookup(src)
        if t is None:
            stat['책 미번역'] += 1; continue
        b = encode(t)
        room = e + 1
        while room < len(orig) and orig[room] == 0 and room not in T:
            room += 1
        room -= o
        if len(b) + 1 <= room and o not in overlap:
            d[o:o + room] = b + bytes(room - len(b)); stat['책 제자리'] += 1
        else:
            new = len(d) + len(tail)
            tail += b + b'\x00'
            for r in refs:
                struct.pack_into('>I', d, r, new)
            stat['책 끝에 붙임'] += 1
    out = bytes(d) + bytes(tail)
    if len(out) % 2:
        out += b'\x00'
    return out
