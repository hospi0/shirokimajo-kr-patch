# -*- coding: utf-8 -*-
r"""트랙 1(MODE1/2352) 파일 바꿔 넣기 — 파일 배치 (2026-09-27)
  원본 배치: LBA 30 부터 파일 466개가 빈틈없이 LBA 순으로 이어지고(디렉터리 순서와는 다름), 마지막 파일 뒤 150섹터 = 뒷간격(0 데이터).
  게임은 ISO 디렉터리(LBA 20‥29)로 파일을 찾는다(실행 파일 이름 표 = 파일 «번호», LBA 아님).
  규칙:
    · 새 파일이 원래 섹터 수 안에 들어가면 제자리(남는 곳은 0)
    · 넘치면 «파일 영역 맨 끝»(마지막 파일 뒤)으로 옮긴다 — 다른 파일은 한 섹터도 안 움직인다
      (옛 자리는 원래 내용 그대로 둔다 = 아무도 안 읽음)
    · 디렉터리 기록의 LBA·크기(양 엔디안), PVD 볼륨 크기, 뒷간격 150섹터(헤더 MSF 새로)
    · 쓴 섹터는 헤더(동기·MSF·모드 1) + EDC/ECC 재계산(tools cdmode1)
  from iso import patch; patch(src_bin, dst_bin, {'C03.BIN': bytes, …}, force_move=())
"""
import os, shutil, struct, sys
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')      # 맨 뒤에 — 앞에 넣으면 그쪽 poc.py 등이 이 프로젝트 것을 가린다
import cdmode1

SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def bcd(n):
    return (n // 10) << 4 | n % 10


def header(lba):
    f = lba + 150
    return SYNC + bytes([bcd(f // 4500), bcd(f // 75 % 60), bcd(f % 75), 1])


def sector(lba, data):
    s = bytearray(2352)
    s[0:16] = header(lba)
    s[16:16 + len(data)] = data
    return bytes(cdmode1.fix(s))


def read_user(fh, lba, n=1):
    out = bytearray()
    for i in range(n):
        fh.seek((lba + i) * 2352 + 16); out += fh.read(2048)
    return bytes(out)


def entries(fh):
    """[(이름, LBA, 크기, 디렉터리 안 오프셋)] — 루트 하나뿐"""
    pvd = read_user(fh, 16)
    root = pvd[156:190]
    dl, ds = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    d = read_user(fh, dl, (ds + 2047) // 2048)
    out = []; i = 0
    while i < len(d):
        n = d[i]
        if n == 0:
            i = (i // 2048 + 1) * 2048; continue
        rec = d[i:i + n]; nl = rec[32]
        name = rec[33:33 + nl].decode('latin1').split(';')[0]
        if name not in ('\x00', '\x01') and not rec[25] & 2:
            out.append((name, struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0], i))
        i += n
    return dl, bytearray(d), out


def patch(src, dst, files, force_move=(), log=print):
    shutil.copyfile(src, dst)
    total = os.path.getsize(src) // 2352
    with open(dst, 'r+b') as fh:
        dl, dirdata, ents = entries(fh)
        E = {nm: (l, s, off) for nm, l, s, off in ents}
        end = max(l + (s + 2047) // 2048 for _, l, s, _ in ents)      # 파일 영역 끝(뒷간격 시작)
        post = total - end
        cur = end
        moved = []
        for nm, data in files.items():
            l, s, off = E[nm]
            have = (s + 2047) // 2048
            need = max(1, (len(data) + 2047) // 2048)
            if need <= have and nm not in force_move:
                lba = l; n = have
            else:
                lba = cur; n = need; cur += need; moved.append(nm)
            pad = data + bytes(n * 2048 - len(data))
            for k in range(n):
                fh.seek((lba + k) * 2352); fh.write(sector(lba + k, pad[k * 2048:(k + 1) * 2048]))
            struct.pack_into('<I', dirdata, off + 2, lba); struct.pack_into('>I', dirdata, off + 6, lba)
            struct.pack_into('<I', dirdata, off + 10, len(data)); struct.pack_into('>I', dirdata, off + 14, len(data))
            log('  %-12s %8d → %8d B  LBA %6d%s' % (nm, s, len(data), lba, ' (끝으로 옮김, 옛 LBA %d)' % l if lba != l else ''))
        for k in range(len(dirdata) // 2048):                            # 디렉터리
            fh.seek((dl + k) * 2352); fh.write(sector(dl + k, dirdata[k * 2048:(k + 1) * 2048]))
        grow = cur - end
        if grow:
            pvd = bytearray(read_user(fh, 16))
            vs = struct.unpack_from('<I', pvd, 80)[0] + grow
            struct.pack_into('<I', pvd, 80, vs); struct.pack_into('>I', pvd, 84, vs)
            fh.seek(16 * 2352); fh.write(sector(16, pvd))
            for k in range(post):                                         # 뒷간격을 뒤로
                fh.seek((cur + k) * 2352); fh.write(sector(cur + k, bytes(2048)))
            fh.truncate((cur + post) * 2352)
        log('  옮긴 파일 %d개 %s · 트랙 1 %d → %d 섹터' % (len(moved), moved, total, cur + post))
    return moved


def tree(fh, lba=None, size=None, base=''):
    """하위 디렉터리까지 {경로: (LBA, 크기, 디렉터리 LBA, 디렉터리 안 오프셋)} (2026-09-28 유나 3 — 장 폴더 파일용)"""
    if lba is None:
        root = read_user(fh, 16)[156:190]
        lba, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    d = read_user(fh, lba, (size + 2047) // 2048); out = {}; i = 0
    while i < len(d):
        n = d[i]
        if n == 0:
            i = (i // 2048 + 1) * 2048; continue
        rec = d[i:i + n]; name = rec[33:33 + rec[32]].decode('latin1').split(';')[0]
        el, sz = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
        if name not in ('\x00', '\x01'):
            if rec[25] & 2:
                out.update(tree(fh, el, sz, base + name + '/'))
            else:
                out[base + name] = (el, sz, lba, i)
        i += n
    return out


def patch_sub(dst, files, log=print):
    """이미 만든 트랙(dst)에서 하위 폴더 파일을 제자리로(원래 섹터 수 안에서만 — 넘치면 중단). 디렉터리 기록 크기 갱신 + 섹터 ECC"""
    with open(dst, 'r+b') as fh:
        T = tree(fh)
        for nm, data in files.items():
            l, s, dl, off = T[nm]
            have = max(1, (s + 2047) // 2048); need = max(1, (len(data) + 2047) // 2048)
            if need > have:
                raise SystemExit('⛔%s: %d B 가 원래 %d 섹터를 넘는다' % (nm, len(data), have))
            pad = data + bytes(have * 2048 - len(data))
            for k in range(have):
                fh.seek((l + k) * 2352); fh.write(sector(l + k, pad[k * 2048:(k + 1) * 2048]))
            ds = dl + off // 2048
            sec = bytearray(read_user(fh, ds)); o = off % 2048
            struct.pack_into('<I', sec, o + 10, len(data)); struct.pack_into('>I', sec, o + 14, len(data))
            fh.seek(ds * 2352); fh.write(sector(ds, bytes(sec)))
            log('  %-22s %8d → %8d B  LBA %6d (제자리)' % (nm, s, len(data), l))
        T2 = tree(fh)
        for nm, data in files.items():
            l, s, _, _ = T2[nm]
            assert s == len(data) and read_user(fh, l, (s + 2047) // 2048)[:s] == data, ('되읽기 불일치', nm)


def verify(dst, files):
    """디렉터리로 다시 읽어 내용이 같은지 + 전 섹터 EDC/ECC(바꾼 곳 표본)"""
    with open(dst, 'rb') as fh:
        _, _, ents = entries(fh)
        for nm, l, s, _ in ents:
            if nm in files:
                got = read_user(fh, l, (s + 2047) // 2048)[:s]
                assert got == files[nm], ('되읽기 불일치', nm)
                for k in (0, (s - 1) // 2048):
                    fh.seek((l + k) * 2352); sec = fh.read(2352)
                    assert bytes(cdmode1.fix(bytearray(sec))) == sec, ('ECC', nm, k)
    return True
