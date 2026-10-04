# -*- coding: utf-8 -*-
"""번역 글자 조사: 한글 음절 수 · SJIS 로 못 쓰는 글자 · 원문 전체에 «안 쓰인» JIS 한자 수(한글 칸 후보)
python tools/smchars.py"""
import collections, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{(?:01|02|09|19)\}.|\{07\}..|\{[0-9A-F]{2}\}|\\n')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    hang = collections.Counter(); bad = collections.Counter(); ex = {}
    for l in open(os.path.join(ROOT, 'work/trans/sm_ko.tsv'), encoding='utf-8'):
        if l.startswith('#'):
            continue
        f = l.rstrip('\n').split('\t')
        for ch in TOK.sub('', f[4]):
            if '가' <= ch <= '힣':
                hang[ch] += 1
            else:
                try:
                    ch.encode('cp932')
                except UnicodeEncodeError:
                    bad[ch] += 1; ex.setdefault(ch, f[0])
    used = set()
    for l in open(os.path.join(ROOT, 'work/text/sm_all.tsv'), encoding='utf-8'):
        used.update(l)
    kanji = [chr(c) for c in range(0x4E00, 0xA000)]
    free = 0
    for ch in kanji:
        try:
            b = ch.encode('cp932')
        except UnicodeEncodeError:
            continue
        if 0x889F <= int.from_bytes(b, 'big') <= 0xEAA4 and ch not in used:
            free += 1
    print('한글 음절', len(hang), '· 못 쓰는 글자', dict(bad), ex)
    print('원문에 안 쓰인 JIS 한자', free)


if __name__ == '__main__':
    main()
