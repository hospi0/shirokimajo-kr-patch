# -*- coding: utf-8 -*-
r"""RetroArch(Beetle Saturn) 상태 → work/mem/<이름>/ (2026-10-03)
  WorkRAML·WorkRAMH·VDP2_VRAM = swap16(빅엔디언) / VDP1_VRAM = 스왑 안 함(이 게임에서 명령 표로 검산) / CRAM 그대로 / VDP2_REGS u16 BE
  python tools/state.py <상태파일> <이름>
"""
import os, struct, sys
sys.path.insert(0, r'C:\claude\project\df2-kr-patch\tools')
import rzip, dump_state as ds
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dump(path, name):
    raw = open(path, 'rb').read()
    snap = rzip.unpack(path)[0] if raw[:5] == b'#RZIP' else raw
    out = os.path.join(ROOT, 'work', 'mem', name); os.makedirs(out, exist_ok=True)
    hits = ds.find_vars(snap); used = set()
    for want, tag, sw in (('VRAM', 'VDP1_VRAM', False), ('VRAM', 'VDP2_VRAM', True), ('CRAM', 'CRAM', False),
                          ('WorkRAML', 'WorkRAML', True), ('WorkRAMH', 'WorkRAMH', True)):
        for k, (i, nm, off, sz) in enumerate(hits):
            if nm == want and k not in used:
                used.add(k); d = snap[off:off + sz]
                open(os.path.join(out, tag + '.bin'), 'wb').write(ds.swap16(d) if sw else d); break
    i = snap.find(b'\x07RawRegs'); n = struct.unpack_from('<I', snap, i + 8)[0]
    open(os.path.join(out, 'VDP2_REGS.bin'), 'wb').write(struct.pack('>256H', *struct.unpack('<256H', snap[i + 12:i + 12 + n])))
    return out


if __name__ == '__main__':
    print(dump(sys.argv[1], sys.argv[2]))
