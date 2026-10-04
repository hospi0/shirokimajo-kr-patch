# -*- coding: utf-8 -*-
r"""트랙 1 하위 폴더 파일 바꿔 넣기(커지면 파일 영역 끝으로 옮김) — 2026-10-04
  게임은 파일을 «이름»으로 찾는다(0.BIN 에 MAP·KANJI12 이름 문자열, LBA 표 없음) → 디렉터리 기록만 고치면 된다.
  규칙(tools/iso.patch 와 같음): 원래 섹터 수 안이면 제자리 · 넘치면 파일 영역 맨 끝(마지막 파일 뒤) · 옛 자리는 그대로
        · 디렉터리 기록 LBA·크기(양 엔디안) · PVD 볼륨 크기 · 뒷간격(0 섹터)을 뒤로 · 쓴 섹터 EDC/ECC
  from isotree import patch; patch(src_bin, dst_bin, {'MAP/MAP001.BIN': bytes, …})"""
import os, shutil, struct
import iso


def patch(src, dst, files, log=print):
    shutil.copyfile(src, dst)
    total = os.path.getsize(src) // 2352
    with open(dst, 'r+b') as fh:
        T = iso.tree(fh)
        # ★디스크 2 는 트랙 2(MODE2)의 END*.GRP 등도 이 디렉터리에 있다 → 끝은 트랙 1 안 파일로만, 트랙 1 이 커지면 그 기록들을 +grow
        end = max(l + (s + 2047) // 2048 for l, s, _, _ in T.values() if l < total)
        outside = {nm: v for nm, v in T.items() if v[0] >= total}
        post = total - end; cur = end; moved = []
        for nm, data in files.items():
            l, s, dl, off = T[nm]
            have = max(1, (s + 2047) // 2048); need = max(1, (len(data) + 2047) // 2048)
            if need <= have:
                lba = l; n = have
            else:
                lba = cur; n = need; cur += need; moved.append(nm)
            pad = data + bytes(n * 2048 - len(data))
            for k in range(n):
                fh.seek((lba + k) * 2352); fh.write(iso.sector(lba + k, pad[k * 2048:(k + 1) * 2048]))
            ds = dl + off // 2048; o = off % 2048
            sec = bytearray(iso.read_user(fh, ds))
            struct.pack_into('<I', sec, o + 2, lba); struct.pack_into('>I', sec, o + 6, lba)
            struct.pack_into('<I', sec, o + 10, len(data)); struct.pack_into('>I', sec, o + 14, len(data))
            fh.seek(ds * 2352); fh.write(iso.sector(ds, bytes(sec)))
            if lba != l:
                log('  %-20s %8d → %8d B  LBA %6d (끝으로, 옛 %d)' % (nm, s, len(data), lba, l))
        grow = cur - end
        if grow:
            pvd = bytearray(iso.read_user(fh, 16))
            vs = struct.unpack_from('<I', pvd, 80)[0] + grow
            struct.pack_into('<I', pvd, 80, vs); struct.pack_into('>I', pvd, 84, vs)
            fh.seek(16 * 2352); fh.write(iso.sector(16, bytes(pvd)))
            for k in range(post):
                fh.seek((cur + k) * 2352); fh.write(iso.sector(cur + k, bytes(2048)))
            fh.truncate((cur + post) * 2352)
            for nm, (l, s, dl, off) in outside.items():                   # 뒤 트랙 파일 = 절대 LBA 가 grow 만큼 밀림
                ds = dl + off // 2048; o = off % 2048
                sec = bytearray(iso.read_user(fh, ds))
                assert struct.unpack_from('<I', sec, o + 2)[0] == l
                struct.pack_into('<I', sec, o + 2, l + grow); struct.pack_into('>I', sec, o + 6, l + grow)
                fh.seek(ds * 2352); fh.write(iso.sector(ds, bytes(sec)))
            if outside:
                log('  뒤 트랙 파일 %d개 LBA +%d' % (len(outside), grow))
        T2 = iso.tree(fh)
        for nm, data in files.items():                                   # 되읽기
            l, s, _, _ = T2[nm]
            assert s == len(data) and iso.read_user(fh, l, (s + 2047) // 2048)[:s] == data, ('되읽기 불일치', nm)
        log('  파일 %d개 (옮김 %d) · 트랙 1 %d → %d 섹터' % (len(files), len(moved), total, cur + post))
    return moved
