# -*- coding: utf-8 -*-
"""번역 병합·검사 → work/trans/sm_ko.tsv (한 파일, 열 = 원문 sm.tsv 와 같음)
  출처: GitHub 가지(클라우드 번역 sm_001‥) + my files/번역/sm_NNN*.tsv(이름 _ko·_translated 섞임, 엑셀식 따옴표 풀기) → 손질표 work/trans/fix.tsv. 뒤 출처가 앞을 덮는다.
  검사(번호마다): 원문이 work/text/sm.tsv 와 같은지 · 제어 코드 {XX}·%·%d/%s 순서 = 원문 · 빈 번역 · 가나 남음(미번역 조각)
  \\n 개수 차이는 경고만(조판 단계에서 다시 접는다).
python tools/trcheck.py [--branch origin/<가지>]  → work/trans/sm_ko.tsv · work/trans/check.tsv"""
import os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = 'origin/claude/laughing-davinci-i7tcmo'
TOK = re.compile(r'\{[0-9A-F]{2}\}|%[a-z]?')
KANA = re.compile(r'[ぁ-ゖァ-ヺ]')


def rows(text):
    for ln in text.split('\n'):
        ln = ln.rstrip('\r')
        if ln and not ln.startswith('#'):
            f = ln.split('\t')
            yield f


def unq(f):
    """엑셀식 따옴표 칸(원문에 " 가 있으면 "…" 로 감싸고 안의 " 는 "") 풀기"""
    return [x[1:-1].replace('""', '"') if len(x) >= 2 and x[0] == x[-1] == '"' else x for x in f]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    br = sys.argv[sys.argv.index('--branch') + 1] if '--branch' in sys.argv else BRANCH
    src = {f[0]: f for f in rows(open(os.path.join(ROOT, 'work/text/sm.tsv'), encoding='utf-8').read())}
    tr = {}; origin = {}
    files = subprocess.run(['git', 'ls-tree', '--name-only', br, 'work/text/split/'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout.split()
    for p in sorted(files):
        t = subprocess.run(['git', 'show', '%s:%s' % (br, p)], cwd=ROOT, capture_output=True, encoding='utf-8').stdout
        for f in rows(t):
            if len(f) >= 5 and f[4].strip():
                tr[f[0]] = (f[3], f[4]); origin[f[0]] = 'github:' + os.path.basename(p)
    mydir = os.path.join(ROOT, 'my files', '번역')
    for n in sorted(os.listdir(mydir)):
        if n.endswith('.tsv'):
            for f in rows(open(os.path.join(mydir, n), encoding='utf-8-sig').read()):
                f = unq(f)
                if len(f) >= 5 and f[4].strip():
                    tr[f[0]] = (f[3], f[4]); origin[f[0]] = n
    fx = os.path.join(ROOT, 'work', 'trans', 'fix.tsv')                # 손질표(마지막에 덮음)
    if os.path.exists(fx):
        for f in rows(open(fx, encoding='utf-8').read()):
            tr[f[0]] = (src[f[0]][3], f[1]); origin[f[0]] = 'fix.tsv'
    probs = []
    for k, (o, t) in tr.items():
        if k not in src:
            probs.append((k, '번호 없음', origin[k], t)); continue
        if o != src[k][3]:
            probs.append((k, '원문 다름', origin[k], o))
        if TOK.findall(t) != TOK.findall(src[k][3]):
            probs.append((k, '제어 코드', origin[k], '%s → %s' % (''.join(TOK.findall(src[k][3])), ''.join(TOK.findall(t)))))
        if KANA.search(t):
            probs.append((k, '가나 남음', origin[k], t))
        if t.count('\\n') != src[k][3].count('\\n'):
            probs.append((k, '줄 수(경고)', origin[k], '%d → %d' % (src[k][3].count('\\n'), t.count('\\n'))))
    miss = [k for k in src if k not in tr]
    os.makedirs(os.path.join(ROOT, 'work', 'trans'), exist_ok=True)
    with open(os.path.join(ROOT, 'work/trans/sm_ko.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('#번호\t첫 위치\t개수\t원문\t번역\n')
        for k, f in src.items():
            w.write('\t'.join(f[:4] + [tr[k][1] if k in tr else '']) + '\n')
    with open(os.path.join(ROOT, 'work/trans/check.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('#번호\t종류\t출처\t내용\n')
        for p in sorted(probs):
            w.write('\t'.join(p) + '\n')
    import collections
    c = collections.Counter(p[1] for p in probs)
    print('원문 %d · 번역 %d · 빈 칸 %d' % (len(src), len(tr), len(miss)))
    print('출처:', dict(collections.Counter(v.split(':')[0] if v.startswith('github') else 'my files' for v in origin.values())))
    print('문제:', dict(c))
    if miss:
        print('빈 번호 구간:', miss[:5], '…', miss[-5:])


if __name__ == '__main__':
    main()
