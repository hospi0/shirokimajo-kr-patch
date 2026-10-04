# -*- coding: utf-8 -*-
r"""白き魔女 문장 추출(번역용 초안, 2026-10-04) — 명령 의미를 다 모르는 상태라 «SJIS 글자 덩어리 + 붙은 제어 바이트(01‥1F)»를 00/명령 경계로 자른다.
  제어 바이트는 {XX} 로 그대로 보존(되넣을 때 그대로 돌려놓을 것). 0D = \n 으로 표시.
  python tools/smtext.py → work/text/sm_all.tsv (모든 덩어리: 파일·위치·길이·원문) · work/text/sm.tsv (중복 제거 번역용: 번호·첫 위치·개수·원문·번역)
  대상: MAP/MAPnnn.BIN · SYSTEM/BOOK*.BIN · 0.BIN (디스크 1 — 두 디스크 공통 파일은 바이트 동일)
"""
import collections, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
D1 = os.path.join(ROOT, 'work', 'disc', 'd1')


def lead(b): return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF
def trail(b): return 0x40 <= b <= 0xFC and b != 0x7F


def is_text(b):
    """잡음(코드·표가 우연히 SJIS 로 읽힘) 거름: 반각 가나 없음 · 전각 글자 중 가나·문장부호·숫자가 30% 이상(이름 같은 가타카나만 줄 포함)"""
    try: t = b.decode('cp932', errors='strict')
    except UnicodeDecodeError: return False
    if any(0xA1 <= c <= 0xDF for c in b if True) and any('｡' <= ch <= 'ﾟ' for ch in t): return False
    full = [ch for ch in t if ord(ch) > 0x3000]
    if len(full) < 2: return False
    kana = sum(1 for ch in full if '぀' <= ch <= 'ヿ' or ch in '、。！？・…～「」（）　０１２３４５６７８９ー')
    return kana / len(full) >= 0.3


def segments(d):
    i = 0; n = len(d); out = []
    while i < n - 1:
        if lead(d[i]) and trail(d[i + 1]):
            try: (d[i:i + 2]).decode('cp932')
            except UnicodeDecodeError: i += 1; continue
            s = i
            while s > 0 and 0x01 <= d[s - 1] < 0x20: s -= 1            # 앞에 붙은 제어 바이트
            j = i; jp = 0
            while j < n and d[j] != 0:
                b = d[j]
                if lead(b) and j + 1 < n and trail(d[j + 1]):
                    try: d[j:j + 2].decode('cp932'); j += 2; jp += 1; continue
                    except UnicodeDecodeError: break
                if b < 0x20 or 0x20 <= b < 0x7F or 0xA1 <= b <= 0xDF: j += 1; continue
                break
            if jp >= 2 and j < n and d[j] == 0 and is_text(d[s:j]):
                out.append((s, j)); i = j + 1; continue
            i = j + 1 if j > i else i + 1
        else:
            i += 1
    return out


def show(b):
    s = []; i = 0
    while i < len(b):
        c = b[i]
        if lead(c): s.append(b[i:i + 2].decode('cp932')); i += 2; continue
        if c == 0x0D: s.append('\\n')
        elif c < 0x20 or c >= 0x7F and not 0xA1 <= c <= 0xDF: s.append('{%02X}' % c)
        else: s.append(bytes([c]).decode('cp932'))
        i += 1
    return ''.join(s)


def files():
    yield '0.BIN'
    for f in sorted(os.listdir(os.path.join(D1, 'SYSTEM'))):
        if f.startswith('BOOK') and f.endswith('.BIN'): yield 'SYSTEM/' + f
    for f in sorted(os.listdir(os.path.join(D1, 'MAP'))):
        if f.endswith('.BIN'): yield 'MAP/' + f


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    allr = []; first = {}; cnt = collections.Counter()
    for f in files():
        d = open(os.path.join(D1, f), 'rb').read()
        for s, e in segments(d):
            t = show(d[s:e]); allr.append('%s\t%06X\t%d\t%s' % (f, s, e - s, t)); cnt[t] += 1; first.setdefault(t, '%s:%06X' % (f, s))
    od = os.path.join(ROOT, 'work', 'text'); os.makedirs(od, exist_ok=True)
    open(os.path.join(od, 'sm_all.tsv'), 'w', encoding='utf-8').write('#파일\t위치\t길이\t원문\n' + '\n'.join(allr) + '\n')
    rows = ['#번호\t첫 위치\t개수\t원문\t번역']
    for k, t in enumerate(first):
        rows.append('%05d\t%s\t%d\t%s\t' % (k + 1, first[t], cnt[t], t))
    open(os.path.join(od, 'sm.tsv'), 'w', encoding='utf-8').write('\n'.join(rows) + '\n')
    jp = sum(sum(1 for ch in t if ord(ch) > 0x3000) for t in first)
    print('덩어리', len(allr), '/ 고유', len(first), '/ 고유 글자(전각)', jp)


if __name__ == '__main__':
    main()
