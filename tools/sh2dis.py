# -*- coding: utf-8 -*-
"""SH-2 역어셈블(테라 프로젝트 sh2_disasm 재사용) — python tools/sh2dis.py 파일 적재주소 시작주소 [개수]
  예) python tools/sh2dis.py 0.BIN 0x06015000 0x0601EE88 60"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
_src = open(r'C:/claude/project/terra-kr-patch/tools/sh2_disasm.py', encoding='utf-8').read().split("if __name__")[0]
_ns = {}; exec(_src, _ns)


def dis(g, load, addr, n=80):
    o = addr - load
    return ['%08X  %04X  %s' % (a, w, t) for a, w, t in _ns['disasm_sh2'](g[o:o + n * 2], addr, n)]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    g = open(sys.argv[1], "rb").read()
    print('\n'.join(dis(g, int(sys.argv[2], 16), int(sys.argv[3], 16), int(sys.argv[4]) if len(sys.argv) > 4 else 80)))
