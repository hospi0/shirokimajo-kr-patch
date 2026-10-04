# -*- coding: utf-8 -*-
r"""白き魔女 한글 빌더 v1 (2026-10-04) — 맵 대사(MAP*.BIN 문장 명령) + 한글 글꼴(KANJI12.FON)
  ① 번역 work/trans/sm_ko.tsv(tools/trcheck.py). ★번역 한 줄 = 문장 명령의 «조각»(추출이 00 에서 잘랐는데 문장 안에 인자 00 인
     제어 코드 {02}{00}·{09}{00} 가 있다) → 문장 명령 안의 추출 조각(smtext.segments)마다 번역으로 갈아 끼우고 사이 바이트는 그대로.
     원본을 같은 방식으로 되인코딩해 바이트가 같은 문장만 손댄다.
  ② 조판(토큰 기준 — {09}\n 처럼 0D 가 인자일 수 있다): 줄 204px(전각·한글 12 · 반각 6 — 엔진이 전각 17자에서 자동으로 꺾음,
     원문 간판 02902 «…停泊港» 에서 확인) · 쪽({0E}{0F}{10}) 줄 수 ≤ max(3, 원문 쪽 표시 줄). 넘치는 쪽만 낱말 단위 재배치
     (부호 뒤에서 끊기 우대) → 그래도 안 되면 {0F} 로 쪽 나눔 · 한 줄보다 긴 낱말(전각 공백 간판)은 엔진 줄바꿈에 맡김. 부호 뒤 공백 1칸 삭제.
  ③ 쓰는 순간 검사(⛔빌드 금지): 제어 코드(인자 포함) 순서 = 원문 · 글꼴에 없는 글자
  ④ 한글(·SJIS 에 없는 글자) → «원문 어디에도 안 쓰인» JIS 한자 칸(구·점 순) 배정, KANJI12.FON 그 칸 = 갈무리11 12×12
  ⑤ 되넣기 = «밀지 않는» 트램펄린: 새 명령이 원래 길이와 같으면 제자리 · 6B 이상 짧으면 제자리 + FD 00 [다음 명령]
     · 그 밖이면 원래 자리 FD 00 [새 자리] → 파일 끝에 [머리][문장 00 맞춤][FD 00 원래 다음 명령]. 맵 버퍼 128KB 검사.
     · 되역어셈블: 원래 명령 머리마다 같은 명령이거나 FD 00 이어야 함 · 역어셈블 오류가 늘면 안 됨.
  ⏳안 하는 것(일본어 그대로): 0.BIN 메뉴·장 제목, SYSTEM/BOOK*, 문장 명령 밖 문자열(MAP000 데이터 표 등)
python tools/smkr.py [--write|--install]  → work/build/ [+ work/out/d1·d2 트랙 1 (+ F: 두 디스크)]"""
import bisect, collections, glob, hashlib, math, os, re, shutil, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import smdis, smbuild, smtext, poc_font, disc, isotree, bdf, smvoice

LIMIT = 204
LIMIT_BUF = 0x20000
DESC_COLS = 9                       # 아이템·마법 설명 창 한 줄 칸 수(스샷 실측 2026-10-04)
B = smdis.BASE
OUT = os.path.join(ROOT, 'work', 'build')
NL = '\\n'
ARG = r'(?:\{[0-9A-F]{2}\}|\\n|.)'
CTRL = re.compile(r'\{(?:01|02|09|19)\}' + ARG + r'|\{07\}' + ARG + ARG + r'|\{[0-9A-F]{2}\}')
PAGE_TOK = ('{0E}', '{0F}', '{10}')
PUNCT = set(',.!?:;)]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥')
PUNCT_END = tuple(',.!?…・。、！？」』)')
F_DIR = r'F:\hospi\roms\ss roms\Shiroki Majo - Mou Hitotsu no Eiyuu Densetsu (Japan) (Disc %d)'


def tokens(t):
    """→ [(종류, 문자열)] 종류 c = 제어(인자 포함) · n = 줄바꿈 · t = 글자"""
    out = []; i = 0
    while i < len(t):
        m = CTRL.match(t, i)
        if m:
            out.append(('c', m.group())); i = m.end(); continue
        if t.startswith(NL, i):
            out.append(('n', NL)); i += 2; continue
        out.append(('t', t[i])); i += 1
    return out


def split_tok(t, is_sep):
    """토큰 기준 나누기 → (조각들, 구분자들)"""
    parts = ['']; seps = []
    for k, v in tokens(t):
        if is_sep(k, v):
            seps.append(v); parts.append('')
        else:
            parts[-1] += v
    return parts, seps


def cw(ch):
    return 6 if ord(ch) < 0x80 or 0xFF61 <= ord(ch) <= 0xFF9F else 12


def width(s):
    return sum(cw(v) for k, v in tokens(s) if k == 't')


def lines_of(pg):
    return split_tok(pg, lambda k, v: k == 'n')[0]


def words_of(s):
    return split_tok(s, lambda k, v: (k, v) == ('t', ' '))[0]


def nospace_after_punct(t):
    tk = tokens(t); out = []
    for i, (k, v) in enumerate(tk):
        if k == 't' and v == ' ' and i and tk[i - 1][0] == 't' and tk[i - 1][1] in PUNCT and not (i + 1 < len(tk) and tk[i + 1] == ('t', ' ')) and not (i >= 2 and tk[i - 2] == ('t', ' ')):
            continue
        out.append(v)
    return ''.join(out)


def kr_dots(t):
    """일본식 말줄임 ・・+ → … (5개 이상 ……) · 바로 뒤 . 。 ． 흡수 — 보이는 글자만(제어 인자는 그대로)"""
    tk = tokens(t); out = []; i = 0
    while i < len(tk):
        if tk[i] == ('t', '・'):
            j = i
            while j < len(tk) and tk[j] == ('t', '・'):
                j += 1
            if j - i >= 2:
                out.append('……' if j - i >= 5 else '…')
                if j < len(tk) and tk[j][0] == 't' and tk[j][1] in '.。．':
                    j += 1
                i = j; continue
        out.append(tk[i][1]); i += 1
    return ''.join(out)


def norm(t):
    return nospace_after_punct(kr_dots(t))


def recenter(sl, tl):
    """원문 줄이 전각 공백으로 들여써(가운데 맞춤) 있으면 번역 줄 앞 공백을 원문 가운데에 맞춰 다시 — 전각 12px·반각 6px"""
    m = re.match(r'[　 ]+', sl)
    if not m or not sl.startswith('　'):
        return tl
    c = sum(12 if ch == '　' else 6 for ch in m.group()) + width(sl[m.end():]) / 2
    body = tl.lstrip('　 ')
    px = max(0, c - width(body) / 2)
    n = int(px // 12)
    return '　' * n + (' ' if px - n * 12 >= 6 else '') + body


def shown_lines(pg):
    return sum(max(1, math.ceil(width(l) / LIMIT)) for l in lines_of(pg))


def wrap(words, n, LIMIT=LIMIT):
    """낱말들 → n 줄(각 줄 ≤ LIMIT). 기준 = (부호로 안 끝나는 줄 수, 가장 긴 줄, 남는 폭 제곱 합) — 뒤쪽 최적 DP"""
    import functools
    W = len(words)

    @functools.lru_cache(maxsize=None)
    def best(i, left):
        if left == 1:
            last = ' '.join(words[i:]); w = width(last)
            return None if w > LIMIT else ((0, w, (LIMIT - w) ** 2), (last,))
        out = None
        for j in range(i + 1, W - left + 2):
            s = ' '.join(words[i:j]); w = width(s)
            if w > LIMIT:
                break
            sub = best(j, left - 1)
            if sub:
                (p, m, q), ls = sub
                key = ((0 if s.endswith(PUNCT_END) else 1) + p, max(w, m), (LIMIT - w) ** 2 + q)
                if out is None or key < out[0]:
                    out = (key, (s,) + ls)
        return out
    r = best(0, n)
    return list(r[1]) if r else None


def fit_page(pg, maxl, LIMIT=LIMIT):
    lines = lines_of(pg)
    if all(width(l) <= LIMIT for l in lines) and len(lines) <= maxl:
        return pg, 0
    words = words_of(' '.join(lines))
    if any(width(w) > LIMIT for w in words):                           # 전각 공백으로 칸 맞춘 간판 등 — 원문처럼 엔진 자동 줄바꿈에 맡김
        return pg, 3
    for n in range(len(lines), maxl + 1):
        if n > len(words):
            break
        r = wrap(words, n, LIMIT)
        if r:
            return NL.join(r), 1
    n = max(maxl + 1, len(lines))                                          # 쪽 나눔
    while n <= len(words):
        r = wrap(words, n, LIMIT)
        if r:
            return '{0F}'.join(NL.join(r[k:k + maxl]) for k in range(0, len(r), maxl)), 2
        n += 1
    raise ValueError('접기 실패: %s' % pg)


# ★검은 화면 나레이션(머리 빈 줄 2개 이상 — 장 제목·막간 설명·«こうして巡礼の旅の前夜は…»): 화면 26칸(312px), 줄마다 가운데 맞춤
#   (원문 앞 전각 공백 = (26 − 글자 칸) ÷ 2 내림, 실측 2026-10-04). 대화창 규칙(204px·원래 줄 수)으로 접으면 낱말이 줄마다 흩어진다.
NARR_W = 312


def narr_split(pg):
    """쪽 머리 제어 코드(«{19}{FF}» 장 화면 명령 등)를 떼어 냄 → (머리, 나머지)"""
    m = re.match(r'(?:\{[0-9A-F]{2}\})*', pg)
    return pg[:m.end()], pg[m.end():]


def narr_head(pg):
    """나레이션 쪽이면 머리 빈 줄 수(≥1), 아니면 0 — 머리 빈 줄 뒤 본문 줄이 전부 전각 공백(가운데 맞춤)으로 시작하고 제어 코드가 없을 때
    (쪽 머리 제어 코드는 빼고 봄 — 실기 2026-10-04 «{19}{FF}» 때문에 나레이션으로 안 잡혔음)"""
    pg = narr_split(pg)[1]
    ls = lines_of(pg); n = 0
    while n < len(ls) - 1 and not ls[n]:
        n += 1
    body = [l for l in ls[n:] if l]
    if not n or not body or '{' in pg or not all(l.startswith('　') for l in body):
        return 0
    return n


def fit_narr(pg):
    pre, pg = narr_split(pg)
    return pre + fit_narr_body(pg)


def fit_narr_body(pg):
    ls = lines_of(pg); head = narr_head(pg)
    body = [l.lstrip('　') for l in ls[head:]]
    tail = 0
    while body and not body[-1]:
        body.pop(); tail += 1
    if any(width(l) > NARR_W for l in body):
        words = words_of(' '.join(b for b in body if b))
        if any(width(w) > NARR_W for w in words):
            raise SystemExit('⛔나레이션 낱말이 화면 폭 초과: %r' % pg)
        body = []; cur = ''
        for w in words:
            if cur and width(cur + ' ' + w) > NARR_W:
                body.append(cur); cur = w
            else:
                cur = (cur + ' ' + w) if cur else w
        body.append(cur)
    body = ['　' * ((NARR_W - width(l)) // 24) + l if l else l for l in body]
    return NL.join([''] * head + body + [''] * tail)


# ★거리 표지판(«東　水晶湖　　　　　２９６ミロ»): 원문은 전각 칸으로 숫자 열을 맞추고, 줄바꿈 없이 204px 꽉 찬 줄로 엔진 자동 줄바꿈에
#   기대기도 한다(08678). 번역 이름 길이·반각 공백·반각 숫자로 열이 반 칸씩 어긋나고(실기 스샷 2026-10-04 «루데라 국경문»),
#   일반 접기가 이름 한가운데를 끊었다(«트리프\n관문») → 원문 숫자 열 px(줄 머리부터, 204 자동 줄바꿈 고려)에 채움 공백을 다시 맞춘다
SIGN_J = re.compile(r'[　 ]{2,}[０-９0-9]+ミロ')
SIGN_K = re.compile(r'[　 ]+([０-９0-9]+)미로')
SIGN_DIR = re.compile(r'[동서남북]{1,2}　')


def sign_cols(sp):
    """원문 쪽 → 줄마다 숫자 열 px 목록(줄 머리 기준, 204 자동 줄바꿈 나머지)"""
    cols = []
    for ln in lines_of(sp):
        txt = ''.join(v for k, v in tokens(ln) if k == 't')
        for m in re.finditer(r'[　 ]{2,}([０-９0-9]+)ミロ', txt):
            cols.append(width(txt[:m.start(1)]) % LIMIT)
    return cols


def align_signs(sp, tp, key=''):
    cols = sign_cols(sp); out = []; ci = 0
    for ln in lines_of(tp):
        if not SIGN_K.search(ln) or CTRL.search(ln):
            out.append(ln); continue
        res = ''; pos = 0; cur = ''                                     # cur = 지금 화면 줄에 쌓인 글
        for m in SIGN_K.finditer(ln):
            seg = ln[pos:m.start()]
            if seg[:1] == '　' or SIGN_DIR.match(seg):
                pre, head = '', seg
            else:
                d = list(SIGN_DIR.finditer(seg))
                if not d:
                    raise SystemExit('⛔%s 표지판 줄 머리(방향) 못 찾음: %s' % (key, ln))
                pre, head = seg[:d[-1].start()], seg[d[-1].start():]
            res += pre; cur += pre
            if cur and width(cur) % LIMIT:                              # 원문은 앞 글이 204px 꽉 차서 자동 줄바꿈 — 번역은 명시 줄바꿈
                res += NL; cur = ''
            if ci >= len(cols):
                raise SystemExit('⛔%s 표지판 줄 수가 원문보다 많음: %s' % (key, tp))
            head = head.rstrip('　 '); px = cols[ci] - width(head); ci += 1
            if px < 12:
                raise SystemExit('⛔%s 표지판 이름이 숫자 열(%dpx)을 넘음: %s' % (key, cols[ci - 1], head))
            row = head + '　' * (px // 12) + (' ' if px % 12 else '') + ''.join(chr(ord(c) + 0xFEE0) if c < '\x80' else c for c in m.group(1)) + '미로'
            res += row; cur += row; pos = m.end()
        out.append(res + ln[pos:])
    if ci != len(cols):
        raise SystemExit('⛔%s 표지판 줄 수 %d ≠ 원문 %d: %s' % (key, ci, len(cols), tp))
    return NL.join(out)


def fit(src, t):
    """→ (새 번역, 상태 0 그대로·1 재배치·2 쪽 나눔·3 엔진 줄바꿈)"""
    is_pg = lambda k, v: k == 'c' and v in PAGE_TOK
    sp, _ = split_tok(src, is_pg); tp, seps = split_tok(t, is_pg)
    maxl = max(3, max(shown_lines(p) for p in sp))
    if len(sp) == len(tp) and all(narr_head(p) for p in sp):
        return ''.join(nospace_after_punct(fit_narr(pg)) + (seps[i] if i < len(seps) else '') for i, pg in enumerate(tp)), 1
    st = 0; out = ''
    for i, pg in enumerate(tp):
        if len(sp) == len(tp) and SIGN_J.search(sp[i]):
            pg2 = align_signs(sp[i], pg)
            st = max(st, 1 if pg2 != pg else 0); out += pg2 + (seps[i] if i < len(seps) else ''); continue
        pg2, s = fit_page(pg, maxl); st = max(st, s)
        if len(sp) == len(tp):
            sl, tl = lines_of(sp[i]), lines_of(pg2)
            if len(sl) == len(tl):
                pg2 = NL.join(recenter(a, b) for a, b in zip(sl, tl))
        out += pg2 + (seps[i] if i < len(seps) else '')
    return out, st


def show(b):
    try:
        return smtext.show(b)
    except UnicodeDecodeError:
        return None


def ctrl_seq(t):
    return [v for k, v in tokens(t) if k == 'c']


def load_extra():
    """보충 번역 — 원문(show2) → (번호, 번역): work/trans/sm_extra_ko.tsv(번호·번역, 원문은 work/text/sm_extra.tsv)
    → my files/번역/sm_extra*.tsv(엑셀식 따옴표 풀기)가 같은 번호를 덮음"""
    ex = {}; dd = os.path.join(ROOT, 'my files', '번역')
    src = {}
    for l in open(os.path.join(ROOT, 'work', 'text', 'sm_extra.tsv'), encoding='utf-8'):
        if not l.startswith('#'):
            f = l.rstrip('\r\n').split('\t'); src[f[0]] = f[3]
    for l in open(os.path.join(ROOT, 'work', 'text', 'sm_left.tsv'), encoding='utf-8'):
        if not l.startswith('#'):
            f = l.rstrip('\r\n').split('\t'); src[f[0]] = f[2]
    for nm in ('sm_left_ko.tsv',):                                      # 화자 인자 어긋남으로 일본어가 남던 문장(tools/smleft)
        pth = os.path.join(ROOT, 'work', 'trans', nm)
        if os.path.exists(pth):
            for l in open(pth, encoding='utf-8'):
                if not l.startswith('#') and l.strip():
                    k, t = l.rstrip('\r\n').split('\t')[:2]
                    ex[src[k]] = (k, restore_args(src[k], norm(t)))
    mine = os.path.join(ROOT, 'work', 'trans', 'sm_extra_ko.tsv')
    if os.path.exists(mine):
        for l in open(mine, encoding='utf-8'):
            if not l.startswith('#') and l.strip():
                k, t = l.rstrip('\r\n').split('\t')[:2]
                ex[src[k]] = (k, restore_args(src[k], norm(t)))
    for n in sorted(os.listdir(dd)) if os.path.isdir(dd) else []:
        if n.startswith('sm_extra') and n.endswith('.tsv'):
            for l in open(os.path.join(dd, n), encoding='utf-8-sig'):
                if l.startswith('#'):
                    continue
                f = [x[1:-1].replace('""', '"') if len(x) >= 2 and x[0] == x[-1] == '"' else x for x in l.rstrip('\r\n').split('\t')]
                if len(f) >= 5 and f[4].strip():
                    ex[f[3]] = (f[0], restore_args(f[3], norm(f[4])))
    return ex


def load():
    ko = {}
    for l in open(os.path.join(ROOT, 'work/trans/sm_ko.tsv'), encoding='utf-8'):
        if l.startswith('#'):
            continue
        f = l.rstrip('\n').split('\t')
        if f[4]:
            ko[f[3]] = (f[0], restore_args(f[3], norm(f[4])))
    return ko


def restore_args(src, t):
    """제어 코드 개수·종류는 같은데 인자만 다르면(예 {02}潤 → {02}순: 인자 바이트가 SJIS 앞 바이트라 글자로 보임) 원문 토큰으로 되돌림"""
    a = ctrl_seq(src); b = ctrl_seq(t)
    if a == b or len(a) != len(b) or any(x[:4] != y[:4] for x, y in zip(a, b)):
        return t
    it = iter(a); out = []
    for k, v in tokens(t):
        out.append(next(it) if k == 'c' else v)
    return ''.join(out)


def free_kanji():
    used = set()
    for l in open(os.path.join(ROOT, 'work/text/sm_all.tsv'), encoding='utf-8'):
        used.update(l)
    out = []
    for c in range(0x4E00, 0xA000):
        ch = chr(c)
        try:
            b = ch.encode('cp932')
        except UnicodeEncodeError:
            continue
        v = int.from_bytes(b, 'big')
        if 0x889F <= v <= 0xEAA4 and ch not in used:
            out.append((poc_font.jis_index(ch), b, ch))
    return [(b, ch) for _, b, ch in sorted(out)]


def need_glyph(ch):
    if '\uac00' <= ch <= '\ud7a3':
        return True
    try:
        ch.encode('cp932'); return False
    except UnicodeEncodeError:
        return True


def encode(t, KM, k=''):
    out = bytearray()
    for kind, v in tokens(t):
        if kind == 'n':
            out.append(0x0D)
        elif kind == 'c':
            for m in re.finditer(r'\{([0-9A-F]{2})\}|\\n|(.)', v):
                if m.group(1):
                    out.append(int(m.group(1), 16))
                elif m.group(0) == NL:
                    out.append(0x0D)
                else:
                    out += m.group(2).encode('cp932')
        elif v in KM:
            out += KM[v]
        else:
            try:
                out += v.encode('cp932')
            except UnicodeEncodeError:
                raise SystemExit('⛔%s 글꼴에 없는 글자 %r' % (k, v))
    return bytes(out)


def compose(d, s0, e0, segs, KO):
    """문장 명령 [s0, e0) → (원문 문자열, 번역 문자열, 쓴 번호들) | 이유 문자열"""
    o = ''; t = ''; keys = []; pos = s0
    for s, e in segs:
        if s < s0 or e > e0:
            continue
        g = show(d[pos:s]); x = show(d[s:e])
        if g is None or x is None:
            return '풀기 실패'
        o += g + x
        if x in KO:
            k, tr = KO[x]; t += g + tr; keys.append(k)
        else:
            t += g + x
        pos = e
    g = show(d[pos:e0])
    if g is None:
        return '풀기 실패'
    o += g; t += g
    if encode(o, {}) != bytes(d[s0:e0]):
        return '되인코딩 다름'
    if not keys:
        return '번역 없음'
    return o, t, keys


def name_tables(d):
    """맵 안 이름 칸 표: 32B 칸 = SJIS 이름(00 끝, 최대 31B) + 나머지 00, 3칸 이상 연속 → [(칸 위치, 이름)]"""
    def rec(o):
        e = o
        while e < o + 32 and d[e]:
            e += 1
        if e == o or e >= o + 32 or any(d[e:o + 32]):
            return None
        try:
            return d[o:e].decode('cp932')
        except UnicodeDecodeError:
            return None
    out = []; o = 0
    while o < len(d) - 64:
        if d[o] and rec(o) and rec(o + 32):                       # (첫 칸 앞이 다른 데이터일 수 있다 — MAP001 «ジュリオの父»)
            run = []
            while o < len(d) - 32 and rec(o):
                run.append((o, rec(o))); o += 32
            if len(run) >= 3:
                out += run
            continue
        o += 2
    return out


def bin0_plan():
    """0.BIN 문자열(tools/smbin0 → work/text/sm_bin0.tsv) + 번역 work/trans/sm_bin0_ko.tsv → [(위치, 자리, 원문, 번역, 번호)]
    반각 공백 2칸 이상으로 들여쓴(가운데 맞춤) 원문은 번역 앞 공백을 원문 가운데(반각 칸 단위)에 맞춰 다시 — % 서식이 있으면 그대로."""
    src = {}
    for l in open(os.path.join(ROOT, 'work', 'text', 'sm_bin0.tsv'), encoding='utf-8'):
        if not l.startswith('#'):
            f = l.rstrip('\r\n').split('\t'); src[f[0]] = (int(f[1], 16), int(f[2]), f[4])
    out = []
    for l in open(os.path.join(ROOT, 'work', 'trans', 'sm_bin0_ko.tsv'), encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        k, t = l.rstrip('\r\n').split('\t')[:2]
        o, room, sj = src[k]
        t = kr_dots(t)
        lead = len(sj) - len(sj.lstrip(' '))
        if lead >= 2 and '%' not in sj and not t.startswith(' '):
            cols = lambda x: sum(1 if ord(ch) < 0x80 else 2 for kd, ch in tokens(x) if kd == 't')
            c = lead + cols(sj[lead:]) / 2
            t = ' ' * max(0, int(round(c - cols(t) / 2))) + t
        if ctrl_seq(t) != ctrl_seq(sj) or t.count('%') != sj.count('%'):
            raise SystemExit('⛔%s 0.BIN 제어 코드·서식이 원문과 다름: %s / %s' % (k, sj, t))
        out.append((o, room, sj, t, k))
    return out


def place(d, ops, KM, stat):
    """ops: [(명령 주소, 길이, 문장 시작, 새 문장 문자열, 번호)] → 새 파일.
    옮길 문장 블록([머리][문장 00 맞춤][FD 00 다음 명령])은 먼저 «빈자리»(옮긴 명령의 옛 자리 a+6‥a+n · 짧아진 명령 뒤 남은 곳)에
    큰 것부터 최적 맞춤으로 넣고, 남는 것만 파일 끝에."""
    nd = bytearray(d); holes = []; moves = []
    for a, n, s0, t, k in ops:
        body = bytes(d[a:s0]) + encode(t, KM, k) + b'\x00'
        if len(body) & 1:
            body += b'\x00'
        if len(body) == n:
            nd[a:a + n] = body; stat['제자리'] += 1
        elif len(body) <= n - 6:
            nd[a:a + len(body)] = body
            nd[a + len(body):a + len(body) + 6] = b'\xFD\x00' + struct.pack('>I', B + a + n); stat['제자리+점프'] += 1
            if n - len(body) - 6 >= 8:
                holes.append([a + len(body) + 6, n - len(body) - 6])
        else:
            if n < 6:
                raise SystemExit('⛔%s 명령 %d B 라 트램펄린 불가' % (k, n))
            moves.append((a, n, body)); stat['옮김'] += 1
            if n - 6 >= 8:
                holes.append([a + 6, n - 6])
    tail = bytearray(b'\x00' if len(d) & 1 else b''); base = len(d) + (len(d) & 1)
    for a, n, body in sorted(moves, key=lambda m: -len(m[2])):
        blk = body + b'\xFD\x00' + struct.pack('>I', B + a + n)
        fit_h = [h for h in holes if h[1] >= len(blk)]
        if fit_h:
            h = min(fit_h, key=lambda h: h[1]); new = h[0]
            nd[new:new + len(blk)] = blk; h[0] += len(blk); h[1] -= len(blk); stat['빈자리 재사용'] += 1
        else:
            new = base + len(tail); tail += blk
        nd[a:a + 6] = b'\xFD\x00' + struct.pack('>I', B + new)
    return bytes(nd) + bytes(tail)


def main():
    sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    KO = load(); EX = load_extra(); L = smdis.length_table()
    import smextra
    D1 = os.path.join(ROOT, 'work', 'disc', 'd1', 'MAP'); MAPS = sorted(x for x in os.listdir(D1) if x.endswith('.BIN'))
    # ①②③ 문장 명령마다 조각 갈아 끼우기 · 조판 · 검사
    plan = {}; why = collections.Counter(); st = collections.Counter(); refit = {}; done_keys = set(); memo = {}
    # ★걷기 시작점 보충: FF49(선택지)는 가변 길이인데 길이 표가 7 고정 → 선택지 바로 뒤 대사(취소 경로 «また、お寄りください。»
    #   MAP006 0x182C8 — 실기 스샷 2026-10-05 일본어)를 못 걸었다. 번역 위치(sm_ko 파일:오프셋) 바로 앞이 FF 00 인데
    #   걷기에 안 잡혔으면 그 FF 00 을 시작점으로 더한다(되역어셈블 검사에도 같은 시작점).
    LOCS = collections.defaultdict(set)
    for l in open(os.path.join(ROOT, 'work/trans/sm_ko.tsv'), encoding='utf-8'):
        f5 = l.rstrip('\n').split('\t')
        if not l.startswith('#') and len(f5) >= 5 and f5[4] and f5[1].startswith('MAP/') and ':' in f5[1]:
            a, b = f5[1].split(':'); LOCS[a[4:]].add(int(b, 16))
    ENTS = {}; xent = 0
    for f in MAPS:
        d = open(os.path.join(D1, f), 'rb').read()
        ent = smdis.entries(d)
        seen, err, _ = smdis.walk(d, ent, L)
        cs = sorted(seen)

        def covered(o):
            i = bisect.bisect_right(cs, o) - 1
            return i >= 0 and o < cs[i] + seen[cs[i]][2]
        more = []                                                       # (번역 위치가 화자 {02}{xx}·{09}{00}·\n 뒤를 가리키면 FF 00 은 2‥8 B 앞 — MAP007 0x14AD9 = 7 B)
        for o in sorted(LOCS[f]):
            c = next((o - k for k in range(2, 9) if o - k >= 0 and not (o - k) & 1 and d[o - k:o - k + 2] == b'\xff\x00'), None)
            if c is not None and not covered(c) and not covered(o) and c not in more:
                more.append(c)
        if more:
            ent = list(ent) + more; xent += len(more)
            seen, err, _ = smdis.walk(d, ent, L)
        ENTS[f] = ent
        segs = smtext.segments(d); ops = []
        for a in sorted(seen):
            p, op, n = seen[a]
            if (p, op) not in smdis.TEXT_OPS:
                continue
            s0, e0 = smbuild.text_span(d, a, p, op, n)
            inside = [(s, e) for s, e in segs if s0 <= s < e0]
            try:                                                           # 보충 번역(문장 명령 통째 — smextra·smleft)이 있으면 먼저
                o2 = smextra.show2(d[s0:e0])
            except UnicodeDecodeError:
                o2 = None
            if o2 in EX and encode(o2, {}) == bytes(d[s0:e0]):
                r = (o2, EX[o2][1], [EX[o2][0]])
            else:
                r = compose(d, s0, e0, inside, KO)
            if isinstance(r, str):
                why[r] += 1; continue
            o, t, keys = r
            if (o, t) not in memo:
                if ctrl_seq(t) != ctrl_seq(o):
                    raise SystemExit('⛔%s 제어 코드가 원문과 다름\n  %s\n  %s' % (keys, ctrl_seq(o), ctrl_seq(t)))
                try:
                    memo[(o, t)] = fit(o, t)
                except ValueError as e:
                    raise SystemExit('⛔%s %s' % (keys, e))
                t2, s = memo[(o, t)]; st[s] += 1
                if s:
                    refit['/'.join(keys)] = (s, t, t2)
            t2, s = memo[(o, t)]
            ops.append((a, n, s0, t2, '/'.join(keys))); done_keys.update(keys)
        plan[f] = (d, seen, err, ops)
    # ③' 이름 칸 표(화자 이름 등 — 32B 칸 제자리)
    # ★표가 1‥2칸뿐인 이름(MAP004 «イーリン» 단독 칸 — 실기 스샷 2026-10-04 화자 이름이 일본어)은 name_tables(3칸 이상)에 안 잡힌다
    #   → sm_ko 위치(파일:오프셋)가 32B 이름 칸 모양이면 이름으로. 추출이 1바이트 앞에서 시작해 원문 첫 글자가 깨진 줄
    #   («闔i書官のルトス» = 칸 0xDC08 «司書官のルトス»)은 위치 o-1 로 찾고 번역 앞에 깨진 머리가 복사돼 있으면 뗀다.
    KOLOC = {}
    for l in open(os.path.join(ROOT, 'work/trans/sm_ko.tsv'), encoding='utf-8'):
        f5 = l.rstrip('\n').split('\t')
        if not l.startswith('#') and len(f5) >= 5 and f5[4] and f5[1].startswith('MAP/') and ':' in f5[1]:
            a, b = f5[1].split(':'); KOLOC[(a[4:], int(b, 16))] = (f5[0], f5[3], norm(f5[4]))

    def slot(d, o):
        e = o
        while e < o + 32 and d[e]:
            e += 1
        if e == o or e >= o + 32 or any(d[e:o + 32]):
            return None
        try:
            return d[o:e].decode('cp932')
        except UnicodeDecodeError:
            return None
    names = {}; RECN = {}
    for f, (d, seen, *_) in plan.items():
        tab = name_tables(d); got = {o for o, _ in tab}
        cs = sorted(seen)

        def in_cmd(o):                                                  # 대본 명령 안 문장(MAP022 0x13568)은 이름 칸이 아니다
            i = bisect.bisect_right(cs, o) - 1
            return i >= 0 and o < cs[i] + seen[cs[i]][2]
        for (lf, lo), (k, src, t) in KOLOC.items():
            if lf != f or ctrl_seq(src) or NL in src:
                continue
            for o in (lo, lo + 1):
                if o >= 0x100 and all(abs(o - g) >= 32 for g in got) and not in_cmd(o) and not in_cmd(lo) and slot(d, o) and (src == slot(d, o) if o == lo else src.endswith(slot(d, o)[1:])):
                    tab.append((o, slot(d, o))); got.add(o)                 # (0x100 앞 = 맵 머리 지명 — ③-4 가 따로 씀)
        for o, nm in tab:
            if nm not in KO:
                hit = KOLOC.get((f, o)) or KOLOC.get((f, o - 1)) or KOLOC.get((f, o - 2))
                if not hit:
                    continue
                hs, ht = hit[1], hit[2]
                m = re.match(r'(?:\{[0-9A-F]{2}\})+', hs)                  # 앞 바이트가 제어 코드로 읽힌 줄(«{10}商人ロベット»·«{1E}ыB夫のシラフ»)
                if m and ht.startswith(m.group()):
                    hs, ht = hs[m.end():], ht[m.end():]
                if hs == nm and hit[1] != nm:
                    KO[nm] = (hit[0], ht)
                elif hs == nm or not hs.endswith(nm[1:]) or ctrl_seq(hs):
                    continue
                else:
                    junk = hs[:len(hs) - len(nm) + 1]
                    KO[nm] = (hit[0], ht[len(junk):] if ht.startswith(junk) else ht)
            if nm in KO:
                k, t = KO[nm]
                if ctrl_seq(t):
                    raise SystemExit('⛔%s 이름에 제어 코드 %s' % (k, t))
                names.setdefault(f, []).append((o, t, k))
        # ★32B 칸이 아닌 이름·문구(2026-10-05 빠진 줄 전수 조사) — 원래 길이 안에서만 쓴다(RECN: (위치, 번역, 번호, 자리))
        #   ① NPC 기록 안 이름: 추출이 1‥2 B 앞 «제어 코드 머리»부터 시작(«{1E}ыB夫のシラフ» → 0x160D8 «坑夫のシラフ»,
        #      «{11}{18}フュエンテの兵士», «{14}ハック») → 짝수 위치 lo+1·lo+2 의 이름, 자리 = 원래 이름 바이트 수
        #   ② 32B 칸을 NUL 없이 꽉 채운 문구가 이어 붙어 한 줄로 추출(MAP035 0xFB1A «そして今は、裏の森が…» 2칸)
        #      → 번역을 문장(. 끝)마다 칸 하나씩, 칸당 32 B 까지(원문 첫 칸도 32 B 꽉 참)
        for (lf, lo), (k, src, t) in KOLOC.items():
            if lf != f or lo < 0x100 or in_cmd(lo) or NL in src:           # (0x100 앞 = 맵 머리 지명 — ③-4 가 따로 씀)
                continue
            m = re.match(r'(?:\{[0-9A-F]{2}\})+', src)
            if m and t.startswith(m.group()) and not ctrl_seq(src[m.end():]):
                for o in (lo + 1, lo + 2):
                    nm = slot(d, o) if not o & 1 else None
                    e = d.find(b'\0', o)
                    if nm and src[m.end():].endswith(nm[1:]) and all(abs(o - g) >= 32 for g in got) and not in_cmd(o):
                        RECN.setdefault(f, []).append((o, t[m.end():], k, e - o)); got.add(o); break
                continue
            if m or ctrl_seq(src):
                continue
            try:
                sb = src.encode('cp932')
            except UnicodeEncodeError:
                continue
            if len(sb) >= 64 and len(sb) % 32 == 0 and d[lo:lo + len(sb)] == sb and lo not in got:
                parts = [x + '.' for x in t.split('.') if x]
                if len(parts) != len(sb) // 32:
                    raise SystemExit('⛔%s 32B 칸 %d개인데 번역 문장 %d개: %s' % (k, len(sb) // 32, len(parts), t))
                for i, x in enumerate(parts):
                    RECN.setdefault(f, []).append((lo + 32 * i, x, k, 32))
                got.add(lo)
    for f in sorted(RECN):
        for o, t, k, lim in RECN[f]:
            print('  기록 이름·꽉 찬 칸 %s %s 0x%X (%d B): %s' % (k, f, o, lim, t))
    B0 = bin0_plan()
    # ③-4 맵 머리 지명 칸(저장 목록 등): u32 @0x94 = 0x002000A4 → 0xA4 의 이름, 자리 = 첫 비영 바이트까지
    HEADKO = {}
    for l in open(os.path.join(ROOT, 'work', 'trans', 'sm_maphead_ko.tsv'), encoding='utf-8'):
        if not l.startswith('#') and l.strip():
            a, b = l.rstrip('\r\n').split('\t')[:2]; HEADKO[a] = b
    heads = {}
    for f, (d, *_) in plan.items():
        if struct.unpack_from('>I', d, 0x94)[0] != 0x002000A4:
            continue
        e = d.index(b'\0', 0xA4); hr = e
        while hr < len(d) and d[hr] == 0:
            hr += 1
        nm = show(d[0xA4:e])
        if nm in HEADKO:
            heads[f] = (hr - 0xA4, HEADKO[nm], nm)
    # ③-5 PARAM.BIN(몬스터·아이템·마법 이름과 설명) — tools/smparam 추출 + work/trans/sm_param_ko.tsv(tools/smparam_unify) 제자리
    PSRC = {}
    for l in open(os.path.join(ROOT, 'work', 'text', 'sm_param.tsv'), encoding='utf-8'):
        if not l.startswith('#'):
            f = l.rstrip('\r\n').split('\t'); PSRC[f[0]] = (int(f[1], 16), int(f[2]), f[4], f[3])
    PAR = []; pfw = collections.Counter(); PDESC = {}
    for l in open(os.path.join(ROOT, 'work', 'trans', 'sm_param_ko.tsv'), encoding='utf-8'):
        if not l.startswith('#') and l.strip():
            k, t = l.rstrip('\r\n').split('\t')[:2]
            t = kr_dots(t); o, room, sj, kind = PSRC[k]
            if '설명' in kind:
                # ★아이템·마법 설명 창 렌더러는 2바이트 글자만 읽는다(책과 같음) — 반각 공백 1바이트가 끼면 뒤 짝이 어긋나
                #   글자가 깨지고 ＄(줄바꿈)가 «$» 글자로 찍힘(실기 2026-10-04 «순례의 증표인») → 반각을 전부 전각으로
                t = ''.join('　' if c == ' ' else chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in t)
                pfw['전각'] += 1
                # ★설명 창 폭 = 9칸(스샷 실측 2026-10-04: 글자 간격 63px, 창 안쪽 115‥730, 글자 시작 130 · 원문 최대 줄도 9칸)
                #   9칸 넘는 줄은 9칸 안의 마지막 전각 공백을 ＄ 로 바꿔 접는다(둘 다 2 B → 바이트 예산 그대로)
                ls = t.split('＄'); n = 0
                while n < len(ls):
                    if len(ls[n]) > DESC_COLS and '　' in ls[n][:DESC_COLS + 1]:
                        i = ls[n].rindex('　', 0, DESC_COLS + 1)
                        ls[n:n + 1] = [ls[n][:i], ls[n][i + 1:]]; pfw['줄 접음'] += 1
                    n += 1
                t = '＄'.join(ls)
                PDESC[k] = kind                                          # 설명은 제자리가 아니라 묶음째 다시 짠다(아래 ③''' — 공백 빼지 않음)
                wide = [x for x in t.split('＄') if len(x) > DESC_COLS]
                if wide:
                    raise SystemExit('⛔%s 설명 줄 %d칸 넘침(창 %d칸): %s' % (k, max(map(len, wide)), DESC_COLS, t))
            # (장비 이름 스프라이트 폭은 0.BIN 견본 문자열 B0175 «装備している物Ｒ» 16 B 로 잡힌다 — 그 문자열은 번역하지 않는다)
            PAR.append((o, room, sj, t, k))
    # ③-6 책(SYSTEM/BOOK*.BIN) — tools/smbook: 줄 오프셋 표가 가리키는 줄마다 번역(sm_ko → 빠진 줄은 work/trans/sm_book_ko.tsv)
    import smbook
    BOOKKO = {}
    for l in open(os.path.join(ROOT, 'work', 'trans', 'sm_book_ko.tsv'), encoding='utf-8'):
        if not l.startswith('#') and l.strip():
            a, b = l.rstrip('\r\n').split('\t')[:2]; BOOKKO[a] = norm(b)

    def book_lookup(src):
        if src in KO:
            return KO[src][1]
        return BOOKKO.get(src)
    SD = os.path.join(ROOT, 'work', 'disc', 'd1', 'SYSTEM')
    BOOKS = sorted(x for x in os.listdir(SD) if re.match(r'BOOK[0-9][0-9][.]BIN$', x))          # BOOKDAT.BIN(공용 데이터) 제외
    book_texts = set()
    for bf in BOOKS:
        bd = open(os.path.join(SD, bf), 'rb').read()
        for o, (e, refs) in smbook.targets(bd).items():
            t = book_lookup(smtext.show(bd[o:e]))
            if t is not None:
                book_texts.add(t)
    # ④ 글자 칸 · 글꼴
    chars = sorted({v for f in plan for *_, t, k in plan[f][3] for kind, v in tokens(t) if kind == 't' and need_glyph(v)}
                   | {v for f in names for _, t, _ in names[f] for kind, v in tokens(t) if kind == 't' and need_glyph(v)}
                   | {v for f in RECN for _, t, _, _ in RECN[f] for kind, v in tokens(t) if kind == 't' and need_glyph(v)}
                   | {v for *_, t, _ in B0 for kind, v in tokens(t) if kind == 't' and need_glyph(v)}
                   | {v for _, t, _ in heads.values() for kind, v in tokens(t) if kind == 't' and need_glyph(v)}
                   | {v for *_, t, _ in PAR for kind, v in tokens(t) if kind == 't' and need_glyph(v)}
                   | {v for t in book_texts for kind, v in tokens(t) if kind == 't' and need_glyph(v)}
                   | {v for t in smvoice.texts() for kind, v in tokens(t) if kind == 't' and need_glyph(v)})
    fk = free_kanji()
    assert len(chars) <= len(fk), ('한자 칸 부족', len(chars), len(fk))
    G = bdf.load('Galmuri11')
    miss = [ch for ch in chars if ord(ch) not in G]
    if miss:
        raise SystemExit('⛔갈무리11 에 없는 글자 %s' % miss)
    # ★칸 배정 고정: 세이브에 이름(코드)이 저장되므로 빌드마다 칸이 바뀌면 옛 세이브 이름이 깨진다(실기 «존륵연» = 줄리오)
    #   → work/trans/sm_kmap.tsv(글자 → 한자 칸)를 유지하고 새 글자만 남은 빈 칸에 덧붙인다
    kmap_p = os.path.join(ROOT, 'work', 'trans', 'sm_kmap.tsv'); kmap = {}
    if os.path.exists(kmap_p):
        for l in open(kmap_p, encoding='utf-8'):
            if not l.startswith('#') and l.strip():
                a, b = l.rstrip('\r\n').split('\t')[:2]; kmap[a] = b
    # 색인 ≥ smvoice.TEXT_FROM 의 빈 한자 칸은 음성 자막 글 전용(한글 배정 금지)
    free_order = [kj for _, kj in fk if poc_font.jis_index(kj) < smvoice.TEXT_FROM]; taken = set(kmap.values())
    assert all(poc_font.jis_index(kj) < smvoice.TEXT_FROM for kj in taken), '한글 칸이 자막 전용 구역에 있음'
    rest = iter(kj for kj in free_order if kj not in taken)
    for ch in chars:
        if ch not in kmap:
            kmap[ch] = next(rest)
    with open(kmap_p, 'w', encoding='utf-8', newline='\n') as w:
        w.write('#글자\t한자 칸(KANJI12 — 한 번 배정하면 바꾸지 않는다)\n')
        for ch, kj in kmap.items():
            w.write('%s\t%s\n' % (ch, kj))
    KM = {ch: kmap[ch].encode('cp932') for ch in chars}
    F = bytearray(disc.read(1, 'SYSTEM/KANJI12.FON'))
    for ch in chars:
        k = poc_font.jis_index(kmap[ch])
        F[k * 18:k * 18 + 18] = np.packbits(poc_font.cell(ch).reshape(-1)).tobytes()
    # ④' 말풍선 «カートリッジRAM» = 0.BIN 0x208D0 문자열 «αβγδεζ» 의 KANJI12 그리스 문자 6칸에 그려 둔 그림 → «카트리지RAM» 72px 를 6칸으로 나눠 그림
    strip = np.zeros((12, 72), np.uint8); x = 0
    for ch in '카트리지RAM':
        w, h, ox, oy, rows = bdf.load('Galmuri11' if '가' <= ch <= '힣' else 'Galmuri9')[ord(ch)]   # RAM 은 한 단계 작게(72px 안)
        top = 12 - 1 - (h + oy)
        for i, r in enumerate(rows):
            v = int(r, 16); nbits = len(r) * 4
            for c in range(w):
                if (v >> (nbits - 1 - c)) & 1 and 0 <= top + i < 12 and 0 <= x + ox + c < 72:
                    strip[top + i, x + ox + c] = 1
        x += 12 if '가' <= ch <= '힣' else w + ox + 1
    assert x <= 72, ('카트리지RAM 폭', x)
    for i, gk in enumerate('αβγδεζ'):
        k = poc_font.jis_index(gk)
        F[k * 18:k * 18 + 18] = np.packbits(strip[:, i * 12:(i + 1) * 12].reshape(-1)).tobytes()
    # ④'' 음성(SAP) 자막 — tools/smvoice: 갈고리 코드·자막 표를 KANJI12 JIS 9‥12구(글자 없는 줄)에, 0.BIN 포인터 4곳은 아래 b0 에서
    vslots = [poc_font.jis_index(kj) for _, kj in fk if poc_font.jis_index(kj) >= smvoice.TEXT_FROM]
    vblob, vpatch, vfont, vinfo = smvoice.build(lambda t: encode(t, KM, 'voice'), vslots)
    F[smvoice.ROW0 * 18:smvoice.ROW0 * 18 + len(vblob)] = vblob
    for o, b in vfont:                                                    # 자막 글(글꼴 빈 한자 칸 안)
        F[o:o + len(b)] = b
    print(vinfo)
    files = {'SYSTEM/KANJI12.FON': bytes(F)}
    # ③'' 0.BIN 문자열 제자리(자리 = 다음 포인터 대상/00 아닌 바이트 전까지)
    b0 = bytearray(disc.read(1, '0.BIN')); n0 = 0
    for o, room, sj, t, k in B0:
        b = encode(t, KM, k)
        while len(b) + 1 > room and b.startswith(b' '):                  # 가운데 맞춤 공백부터 줄임
            b = b[1:]
        if len(b) + 1 > room:
            raise SystemExit('⛔%s 0.BIN 자리 넘침 %d > %d: %s' % (k, len(b) + 1, room, t))
        assert show(bytes(b0[o:o + room]).split(b'\x00')[0]) == sj, ('0.BIN 원문 자리 다름', k)
        b0[o:o + room] = b + bytes(room - len(b)); n0 += 1
    for a, v in vpatch:                                                   # 음성 자막 갈고리(포인터만)
        o = a - smvoice.L0
        assert struct.unpack_from(">I", b0, o)[0] in (smvoice.ORIG_UPD, smvoice.ORIG_42, smvoice.ORIG_V20, smvoice.ORIG_SYNC), hex(a)
        struct.pack_into('>I', b0, o, v)
    files['0.BIN'] = bytes(b0)
    pb = bytearray(disc.read(1, 'SYSTEM/PARAM.BIN')); p0 = bytes(pb)
    for o, room, sj, t, k in PAR:
        assert show(bytes(pb[o:o + room]).split(b'\x00')[0]) == sj, ('PARAM 원문 자리 다름', k)
        if k in PDESC:
            continue
        b = encode(t, KM, k)
        if len(b) + 1 > room:
            raise SystemExit('⛔%s PARAM 자리 넘침 %d > %d: %s' % (k, len(b) + 1, room, t))
        pb[o:o + room] = b + bytes(room - len(b))
    # ③''' 설명 묶음 다시 짜기 — 레코드가 설명을 «구역 기준 u32 오프셋»으로 가리킨다(아이템 +0x40 / 마법 +0x4C, 132/132·21/21 일치,
    #   2026-10-04). 원문 길이 칸에 가두면 공백을 빼야 했다(«신비한단검») → 묶음(첫 설명 ‥ 마지막 설명 끝) 안에서 이어 쓰고 포인터 고침.
    #   묶음 안 다른 참조는 전부 빈 설명(00 바이트) → 묶음 끝 00 하나로. 묶음 밖(quux·Sentinel 더미, 오프셋 0)은 안 건드림.
    import smparam
    pdk = {PSRC[k][0]: k for k in PDESC}; pkt = {k: t for o, room, sj, t, k in PAR}; pds = collections.Counter()
    for kind, base, rs, n, fo in (('아이템 설명', 0x1CD0, 0x44, 202, 0x40), ('마법 설명', 0x6F8C, 0x50, 64, 0x4C)):
        ds = [(o, e) for o, e, room, kd, s in smparam.strings(p0) if kd == kind]
        s0 = ds[0][0]; s1 = ds[-1][1] + 1
        pb[s0:s1] = bytes(s1 - s0); pos = s0; new = {}; seen = {}
        for o, e in ds:
            b = encode(pkt[pdk[o]], KM, pdk[o]) if o in pdk else p0[o:e]
            if b not in seen:
                seen[b] = pos; pb[pos:pos + len(b)] = b; pos += len(b) + 1
            new[o] = seen[b]
        if pos > s1 - 1:
            raise SystemExit('⛔%s 묶음 넘침 %d > %d' % (kind, pos - s0, s1 - 1 - s0))
        used = set()
        for r in range(n):
            a = base + struct.unpack_from('>I', p0, base + r * rs + fo)[0]
            if not s0 <= a < s1:
                continue
            if a in new:
                v = new[a]; used.add(a)
            elif p0[a] == 0:
                v = s1 - 1; pds['빈 설명 참조'] += 1
            else:
                raise SystemExit('⛔%s 레코드 %d 가 설명 한가운데를 가리킴 0x%X' % (kind, r, a))
            struct.pack_into('>I', pb, base + r * rs + fo, v - base)
        if set(new) - used:
            raise SystemExit('⛔%s 아무 레코드도 안 가리키는 설명 %s' % (kind, [hex(x) for x in set(new) - used]))
        pds[kind] = '%d/%d B' % (pos - s0, s1 - s0)
    files['SYSTEM/PARAM.BIN'] = bytes(pb)
    # ③'''' 월드맵 지명판 그림 34장(SLMAPDAT 0xD4DC, 80×16 4bpp) — tools/smplate(실기 스샷 «ディーネ / 緑の高原»)
    import smplate
    files['SYSTEM/SLMAPDAT.BIN'] = smplate.build(disc.read(1, 'SYSTEM/SLMAPDAT.BIN'))
    print('PARAM.BIN 문자열 %d · 설명 전각화 %s · 설명 묶음 다시 짬 %s' % (len(PAR), dict(pfw), dict(pds)))
    bst = collections.Counter()
    for bf in BOOKS:
        bd = open(os.path.join(SD, bf), 'rb').read()
        # ★책 렌더러는 2바이트 글자만 읽는다 — 반각(공백·쉼표·마침표 1바이트)이 끼면 그 뒤 짝이 어긋나 엉뚱한 글자·검은 네모(실기 2026-10-04)
        #   → 책 줄은 반각을 전부 전각으로(공백 → 「　」), 인코딩 뒤 1바이트 글자가 남으면 빌드 중단
        def book_enc(t, bf=bf):
            t = ''.join('　' if c == ' ' else chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in t)
            b = encode(t, KM, bf); i = 0
            while i < len(b):
                if not smtext.lead(b[i]):
                    raise SystemExit('⛔%s 책 줄에 1바이트 글자 0x%02X: %r' % (bf, b[i], t))
                i += 2
            return b
        # ★쪽 넘침(전각이면 173쪽 중 119쪽이 원래 줄 수 초과) → tools/smbook2: 책 파일을 다시 짜며 12칸으로 접고 넘치면 쪽 추가(실기 2026-10-04)
        import smbook2, smcover
        bk = int(bf[4:6]); bd0 = bd
        if bk in smcover.TITLES:                                     # 표지 제목 그림(8bpp 120×H, tools/smcover) — 다시 짜기 전 원본 자리에서 바꿈
            bd = smcover.patch(bd, smcover.TITLES[bk]); bst['책 표지 제목'] += 1
        nb = smbook2.build(bd, book_lookup, lambda t, bf=bf: encode(t, KM, bf), bst)
        if nb != bd0:
            files['SYSTEM/' + bf] = nb
    print('책 %s' % dict(bst))
    import smstatus                                                       # ③''' 상태창 이름 그림(BATTLE.BIN status.spr)
    files['SYSTEM/BATTLE.BIN'] = smstatus.build(disc.read(1, 'SYSTEM/BATTLE.BIN'))[0]
    import smtitle, smtitle_kr                                            # ③'''' 타이틀 로고 «하얀 마녀 ~또 하나의 영웅전설~»(LDDATA.PAK 7·8·6, tools/smtitle_kr)
    files['SYSTEM/LDDATA.PAK'] = smtitle.from_index(disc.read(1, 'SYSTEM/LDDATA.PAK'), smtitle_kr.make()[3])[0]
    print('0.BIN 문자열 %d 제자리' % n0)
    # ⑤ 맵 되넣기 + 검사
    stat = collections.Counter(); room = []
    for f, (d, seen, err, ops) in plan.items():
        if not ops and f not in names and f not in heads and f not in RECN:
            continue
        out = bytearray(place(d, ops, KM, stat) if ops else d)
        if f in heads:
            hr, t, nm = heads[f]; b = encode(t, KM, nm)
            if len(b) + 1 > hr:
                raise SystemExit('⛔%s 맵 머리 지명 넘침 %d > %d: %s' % (f, len(b) + 1, hr, t))
            out[0xA4:0xA4 + hr] = b + bytes(hr - len(b)); stat['맵 지명'] += 1
        for o, t, k in names.get(f, []):
            b = encode(t, KM, k)
            if len(b) > 31:                                              # 넘칠 때만 전각 괄호·숫자 → 반각
                t = t.translate(str.maketrans('（）０１２３４５６７８９', '()0123456789')); b = encode(t, KM, k)
            if len(b) > 31:
                raise SystemExit('⛔%s 이름 %d B > 31: %s' % (k, len(b), t))
            out[o:o + 32] = b + bytes(32 - len(b)); stat['이름 칸'] += 1
        for o, t, k, lim in RECN.get(f, []):                              # 원래 길이 자리(NPC 기록 이름 · 꽉 찬 32B 칸)
            b = encode(nospace_after_punct(t), KM, k)
            if len(b) > lim:
                raise SystemExit('⛔%s 자리 넘침 %d B > %d: %s' % (k, len(b), lim, t))
            out[o:o + lim] = b + bytes(lim - len(b)); stat['기록 이름·꽉 찬 칸'] += 1
        out = bytes(out)
        seen2, err2, _ = smdis.walk(out, ENTS[f], L)
        bad = sum(1 for a, (p, op, n) in seen.items() if seen2.get(a, (None, None))[:2] not in ((p, op), (0xFD, 0)))
        if bad or sum(err2.values()) > sum(err.values()):
            raise SystemExit('⛔%s 되역어셈블 어긋남 %d · 오류 %d → %d' % (f, bad, sum(err.values()), sum(err2.values())))
        if len(out) > LIMIT_BUF:
            raise SystemExit('⛔%s 맵 버퍼 넘침 %d > %d (%+d)' % (f, len(out), LIMIT_BUF, len(out) - len(d)))
        room.append((LIMIT_BUF - len(out), f))
        files['MAP/' + f] = out
    # ⑥ 동영상 자막(tools/smsub → work/kr/Mnn.CPK) — 디스크별 파일이라 disc.listing 으로 걸러져 해당 디스크에만 들어감
    for p in sorted(glob.glob(os.path.join(ROOT, 'work', 'kr', 'M[0-9][0-9].CPK'))):
        files['CPK/' + os.path.basename(p)] = open(p, 'rb').read()
    os.makedirs(OUT, exist_ok=True)
    for nm, data in files.items():
        p = os.path.join(OUT, nm.replace('/', os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(data)
    with open(os.path.join(OUT, 'refit.tsv'), 'w', encoding='utf-8', newline='\n') as w:
        w.write('#번호\t상태(1 재배치·2 쪽 나눔·3 엔진 줄바꿈)\t번역\t조판\n')
        for k, (s, t, t2) in sorted(refit.items()):
            w.write('%s\t%d\t%s\t%s\n' % (k, s, t, t2))
    allk = set(v[0] for v in KO.values())
    print('문장 명령: 번역 넣음 %d · 손 안 댐 %s' % (sum(len(v[3]) for v in plan.values()), dict(why)))
    print('걷기 시작점 보충 %d · 번역 줄 사용 %d / %d · 조판 그대로 %d · 재배치 %d · 쪽 나눔 %d · 엔진 줄바꿈 %d' % (xent, len(done_keys), len(allk), st[0], st[1], st[2], st[3]))
    print('글자 칸 %d (여유 %d) · 되넣기 %s · 바뀐 맵 %d · 버퍼 여유 최소 %s' % (len(chars), len(fk) - len(chars), dict(stat), len(files) - 1, sorted(room)[:3]))
    if '--write' in sys.argv or '--install' in sys.argv:
        for n in (1, 2):
            have = disc.listing(n)
            fs = {k: v for k, v in files.items() if k in have}
            dst = os.path.join(ROOT, 'work', 'out', 'd%d' % n, os.path.basename(disc.TRACK[n]))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            print('디스크 %d:' % n)
            isotree.patch(disc.TRACK[n], dst, fs)
            print('  트랙 1', hashlib.md5(open(dst, 'rb').read()).hexdigest())
            outs = [dst]
            grow = (os.path.getsize(dst) - os.path.getsize(disc.TRACK[n])) // 2352
            if n == 2 and grow:                                              # 트랙 2(MODE2) 섹터 머리 주소도 +grow (tools/shifttrack)
                import shifttrack
                t2 = disc.TRACK[2].replace('(Track 1).bin', '(Track 2).bin')
                d2 = os.path.join(os.path.dirname(dst), os.path.basename(t2))
                shifttrack.shift(t2, d2, grow); outs.append(d2)
                print('  트랙 2 머리 주소 +%d → %s' % (grow, hashlib.md5(open(d2, 'rb').read()).hexdigest()))
            if '--install' in sys.argv:
                for o in outs:
                    shutil.copyfile(o, os.path.join(F_DIR % n, os.path.basename(o)))
                print('  F: 설치')


if __name__ == '__main__':
    main()
