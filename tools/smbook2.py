# -*- coding: utf-8 -*-
r"""SYSTEM/BOOKnn.BIN 책 — 쪽을 늘려 다시 짜기 (2026-10-04)
  읽는 쪽 = BOOKPRG.BIN(0x060E0000). 책 버퍼는 파일 크기만큼 동적 할당(0x060E2348) → 파일이 커져도 됨.
  구조(34권 전수 대조):
    머리 = u32 목록(0 끝): [0] 정보 기록 20B [0][배치 4B][팔레트 포인터][값][포인터 또는 0] · [1] 8B 기록 · [2‥] 쪽 기록
           (책을 열면 [2] 부터 0 까지 세어 쪽 수로 씀 — 0x060E25A6)
    쪽 기록 = [줄 표][0][그림] (+ 그림 쪽만 [값][값] 더 읽음) — 원본은 본문 쪽 12B·그림 쪽 20B 로 겹쳐 놓음 → 다시 짤 땐 전부 20B
    줄 표 = u32 줄 문자열 포인터(0 끝) · 줄 문자열 = SJIS 전각만(★2바이트 전용 렌더러) 00 끝
    그림·팔레트(정보 [2]·[4], 그림 쪽 [2]) = 문자열 뒤에 모여 있음 → 바이트 그대로 뒤에 붙이고 포인터만 옮김
  배치(원본 실측 2026-10-04): 한 줄 12칸 · «13 0B 03» 책 = 본문 7줄 + 줄 사이 「　」 빈 줄 / «07 08 18» 책 = 본문 13줄 붙여 씀.
  번역: 원문 줄마다 번역(lookup) → 쪽 안에서 문단(원문 「　」 들여쓰기 줄부터)별로 이어 붙여 12칸으로 다시 접고, 넘치면 쪽 추가.
        그림·빈 쪽이 원래 좌우(쪽 번호 홀짝)에 오도록 필요하면 빈 쪽을 끼움.
  build(d, lookup, enc) → 새 파일 바이트 · lookup(원문 줄) → 번역 | None · enc(전각 문자열) → SJIS 바이트"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import smtext

SP = '　'
PUNCT = tuple('，．、。！？…」』）')


def u32(b, i):
    return struct.unpack_from('>I', b, i)[0]


def full(t):
    """반각 → 전각(책 렌더러는 2바이트만)"""
    return ''.join(SP if c == ' ' else chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in t)


def parse(b):
    hdr = []; i = 0
    while u32(b, i):
        hdr.append(u32(b, i)); i += 4
    info = b[hdr[0]:hdr[0] + 20]; rec1 = b[hdr[1]:hdr[1] + 8]
    pages = []
    for r in hdr[2:]:
        t, img = u32(b, r), u32(b, r + 8)
        rows = []
        if t:
            k = t
            while u32(b, k):
                o = u32(b, k); e = b.index(b'\0', o)
                rows.append(smtext.show(b[o:e])); k += 4
        pages.append(dict(rec=b[r:r + 20] if img else b[r:r + 12] + bytes(8), t=t, img=img, rows=rows))
    return hdr, info, rec1, pages


W = 12                                                                 # 한 줄 12칸(원본 실측) — 끝 부호 하나는 13칸째에 매달 수 있음


def kind(rs):
    """쪽 종류: alt = 줄 사이 「　」 빈 줄(본문 줄·빈 줄 번갈이) · free = 제목 쪽 등 자유 배치(빈 줄 40% 이상·3줄 미만) · prose = 붙여 쓴 본문"""
    if is_alt(rs):
        return 'alt'
    if len(rs) < 3 or sum(1 for r in rs if not r.strip(SP)) * 10 >= len(rs) * 4:
        return 'free'
    return 'prose'


def limits(pages):
    """→ {종류: 쪽당 본문 줄 수} (원본 같은 종류 쪽의 최대)"""
    R = {'alt': 0, 'prose': 0}
    for p in pages:
        k = kind(p['rows']) if p['rows'] else None
        if k == 'alt':
            R['alt'] = max(R['alt'], (len(p['rows']) + 1) // 2)
        elif k == 'prose':
            R['prose'] = max(R['prose'], len(p['rows']))
    return R


def fits(x):
    return len(x) <= W or (len(x) == W + 1 and x.endswith(PUNCT))


def wrap(words, W, first):
    """낱말(전각 공백으로 나뉜) → 줄들. first = 첫 줄 들여쓰기.
    부호 바로 뒤도 줄 바꿀 수 있는 자리(같은 줄이면 공백 없이 붙임 — «…다.이미…» 처럼 부호 뒤 공백을 지운 문장)"""
    toks = []                                                          # (조각, 앞 이음)
    for w in words:
        parts = [x for x in re.split('(?<=[%s])' % ''.join(PUNCT), w) if x]
        for j, x in enumerate(parts):
            toks.append((x, '' if j else SP))
    out = []; cur = first
    for w, glue in toks:
        if not fits(w):
            raise SystemExit('⛔책 낱말이 줄 폭 %d 초과: %r' % (W, w))
        g = glue if cur.strip(SP) else ''
        if cur.strip(SP) and not fits(cur + g + w):
            out.append(cur); cur = w
        else:
            cur = cur + g + w
    if cur.strip(SP):
        out.append(cur)
    return out


def is_alt(rs):
    return len(rs) % 2 == 1 and len(rs) >= 3 and all(rs[i] == SP for i in range(1, len(rs), 2)) and rs[0] != SP


ROWS = 13                                                              # 한 쪽 = 13줄 격자(원본 최대 13 항목)

# ★번역 줄이 일본어 줄바꿈 자리에서 낱말을 끊어 둔 곳(«돌 / 아다니는»·«샤 / 리네»·«말 / 에 따라») — 줄을 이을 때 붙일지 말뭉치로 판정
#   (실기 2026-10-04 «있 고,»·«돌 아다니는»·«무료 가»). 앞·뒤 조각이 따로 쓰인 적 없거나, 붙인 꼴이 쓰였거나, 뒤가 조사·어미 단독이면 붙임.
STRICT = {'가', '은', '는', '을', '를', '에', '에서', '의', '로', '으로', '과', '와', '도', '다', '고', '며', '면', '서', '께', '게', '지', '요', '만', '까지', '부터', '처럼', '보다'}
_VOC = None


def vocab():
    global _VOC
    if _VOC is None:
        import collections
        _VOC = collections.Counter()
        root = os.path.dirname(HERE)
        for fn in ('sm_ko.tsv', 'sm_book_ko.tsv', 'sm_extra_ko.tsv', 'sm_left_ko.tsv', 'sm_bin0_ko.tsv', 'sm_param_ko.tsv'):
            p = os.path.join(root, 'work', 'trans', fn)
            if not os.path.exists(p):
                continue
            for l in open(p, encoding='utf-8'):
                if l.startswith('#'):
                    continue
                for w in re.split(r'[^가-힣]+', l.rstrip('\n').split('\t')[-1].replace('\\n', ' ')):
                    if w:
                        _VOC[w] += 1
    return _VOC


def glue(prev, nxt):
    """줄 끝 prev + 다음 줄 첫 머리 nxt 를 이을 때 사이 글자('' 붙임 / 「　」)"""
    if not prev or prev.endswith(PUNCT):
        return ''
    a = re.split(r'[^가-힣]+', prev)[-1]; b = re.split(r'[^가-힣]+', nxt)[0]
    if not a or not b or not re.match('[가-힣]', prev[-1]) or not re.match('[가-힣]', nxt[0]):
        return SP
    V = vocab(); ca, cb, cj = V[a], V[b], V[a + b]
    if (ca == 0 and cb == 0) or nxt.split(SP)[0] in STRICT or (cj and (ca == 0 or cb == 0 or cj >= min(ca, cb))):
        return ''
    return SP


def page_items(rows, tr):
    """쪽 → (머리 빈 줄 수, sep, 문단들 [[줄 번역들], 들여쓰기, 앞 gap, 소제목])"""
    idx = [i for i, r in enumerate(rows) if r.strip(SP)]
    sep = 1 if len(idx) >= 2 and all(b - a >= 2 for a, b in zip(idx, idx[1:])) else 0
    paras = []; prev = None
    for i in idx:
        r, t = rows[i], tr[i]
        gap = 0 if prev is None else i - prev - 1 - sep
        ind = len(r) - len(r.lstrip(SP))
        head = ind >= 2
        if prev is None or gap > 0 or ind >= 1 or head or paras[-1][3]:
            paras.append([[t], ind, max(gap, 0), head])
        else:
            paras[-1][0].append(t)
        prev = i
    return (idx[0] if idx else 0), sep, paras


def flow(run, lookup, stat):
    """이어지는 본문 쪽들(run = [줄들…]) → 새 쪽들(항목 목록). 원본 쪽 경계는 문장 한가운데일 수 있다(«…所持する習わし» / «があります…»)
    → 쪽마다 따로 접지 않고 한 흐름으로 이어 접는다(실기 2026-10-04 «공통» 한 줄 남고 쪽 넘김). 머리 빈 줄 = 첫 쪽만."""
    def tr_of(r):
        t = lookup(r) if r.strip(SP) else None
        if t is None and re.search('[ぁ-んァ-ヶ一-龥]', r):
            stat['책 미번역 일본어'] += 1
        return full(t) if t is not None else r
    trs = [[tr_of(r) for r in rows] for rows in run]
    if all(fits(x) for tr in trs for x in tr):                        # 줄마다 다 들어가면 쪽·줄 자리 그대로
        stat['책 쪽 그대로'] += len(run)
        return trs
    lead = None; sep = None; paras = []
    for k, (rows, tr) in enumerate(zip(run, trs)):
        ld, sp, ps = page_items(rows, tr)
        if lead is None:
            lead, sep = ld, sp
        if not ps:
            continue
        if k and paras and ps[0][1] == 0 and not ps[0][3] and not paras[-1][3] and ps[0][2] == 0:
            paras[-1][0] += ps[0][0]; ps = ps[1:]                      # 쪽 경계에서 이어지는 문단
        paras += ps
    items = []
    for ts, ind, gap, head in paras:
        if gap:
            items.append(('gap', gap))
        txt = ''
        for x in ts:
            x = x.strip(SP)
            txt += glue(txt, x) + x if txt else x
        ind2 = ind
        while ind2 and head and not fits(SP * ind2 + txt):
            ind2 -= 1                                                 # 소제목: 넘치면 들여쓰기부터 줄임
        for ln in wrap([w for w in txt.split(SP) if w], W, SP * (ind2 if head else min(ind, 1))):
            items.append(('line', ln))
    pages = []; cur = [SP] * (lead or 0); gap = 0
    for k, v in items:
        if k == 'gap':
            gap += v; continue
        before = (sep + gap) if any(x != SP for x in cur) else 0
        if len(cur) + before + 1 > ROWS:
            while cur and cur[-1] == SP:
                cur.pop()
            pages.append(cur); cur = []; before = 0
        cur += [SP] * before + [v]; gap = 0
    while cur and cur[-1] == SP:
        cur.pop()
    if cur:
        pages.append(cur)
    stat['책 흐름 다시 접음'] += 1; stat['책 쪽 늘어남'] += len(pages) - len(run)
    return pages


def build(d, lookup, enc, stat):
    hdr, info, rec1, pages = parse(d)
    R = limits(pages)
    if not any(p['rows'] for p in pages):
        return d
    blobs = [x for x in [u32(info, 8), u32(info, 16)] + [p['img'] for p in pages if p['img']] if x]
    B0 = min(blobs) if blobs else len(d)
    texts_end = max([d.index(b'\0', u32(d, k)) for p in pages if p['t'] for k in range(p['t'], p['t'] + 4 * (len(p['rows']) + 1), 4) if u32(d, k)] + [0])
    if B0 < texts_end:
        raise SystemExit('⛔책 그림이 문자열 앞에 있음 0x%X < 0x%X' % (B0, texts_end))
    newp = []                                                      # (종류, 줄들 | 원래 기록)
    run = []; run_sep = [None]

    def flush():
        for rows in flow(run, lookup, stat) if run else []:
            newp.append(('text', rows))
        run.clear(); run_sep[0] = None
    for i, p in enumerate(pages):
        if not p['t']:
            flush()
            if len(newp) % 2 != i % 2:                               # 그림·빈 쪽은 원래 좌우 자리
                newp.append(('blank', None)); stat['책 빈 쪽 끼움'] += 1
            newp.append(('raw', p['rec'])); continue
        rs = p['rows']
        idx = [j for j, r in enumerate(rs) if r.strip(SP)]
        sep = 1 if len(idx) >= 2 and all(b - a >= 2 for a, b in zip(idx, idx[1:])) else 0
        solo = (not idx or idx[0] > 0 or kind(rs) == 'free' or len(idx) < 3
                or any(len(r) - len(r.lstrip(SP)) >= 2 for r in rs if r.strip(SP)))
        # 흐름으로 잇는 쪽 = 머리 빈 줄 없음 · 목록·소제목(들여쓰기 2칸+) 없음 · 본문 3줄+ · 줄 띄움 방식이 같음. 아니면 그 쪽만 따로
        cont = bool(run) and not [r for r in run[-1] if r.strip(SP)][-1].rstrip(SP).endswith(('。', '！', '？', '」', '』', '…', '・'))
        if solo or (run and run_sep[0] != sep) or not cont:          # 원본이 문장 끝에서 쪽을 넘긴 곳은 그대로 쪽 나눔
            flush()
        run.append(rs); run_sep[0] = sep
        if solo:
            flush()
    flush()
    # 배치
    n = len(newp)
    o_hdr = 0; o_info = 4 * (n + 3); o_rec1 = o_info + 20; o_rec = o_rec1 + 8
    o_tab = o_rec + 20 * n
    tabs = []; o = o_tab
    for k, v in newp:
        if k == 'text':
            tabs.append(o); o += 4 * (len(v) + 1)
        else:
            tabs.append(0)
    strs = {}; sb = bytearray(); o_str = o
    for k, v in newp:
        if k == 'text':
            for r in v:
                if r not in strs:
                    b = enc(r)
                    i = 0
                    while i < len(b):
                        if not smtext.lead(b[i]):
                            raise SystemExit('⛔책 줄에 1바이트 글자 0x%02X: %r' % (b[i], r))
                        i += 2
                    strs[r] = o_str + len(sb); sb += b + b'\0'
    o_blob = o_str + len(sb)
    o_blob += (B0 - o_blob) % 4                                     # 그림 정렬을 원래와 같게(4 나머지)
    delta = o_blob - B0
    out = bytearray(o_blob) + bytearray(d[B0:])
    struct.pack_into('>%dI' % (n + 3), out, 0, o_info, o_rec1, *[o_rec + 20 * j for j in range(n)], 0)
    inf = bytearray(info)
    if u32(info, 8):
        struct.pack_into('>I', inf, 8, u32(info, 8) + delta)
    if u32(info, 16):
        struct.pack_into('>I', inf, 16, u32(info, 16) + delta)
    out[o_info:o_info + 20] = inf; out[o_rec1:o_rec1 + 8] = rec1
    for j, (k, v) in enumerate(newp):
        r = o_rec + 20 * j
        if k == 'text':
            struct.pack_into('>I', out, r, tabs[j])
            struct.pack_into('>%dI' % (len(v) + 1), out, tabs[j], *[strs[x] for x in v], 0)
        elif k == 'raw':
            rec = bytearray(v)
            if u32(rec, 8):
                struct.pack_into('>I', rec, 8, u32(rec, 8) + delta)
            out[r:r + 20] = rec
    out[o_str:o_str + len(sb)] = sb
    if len(out) % 2:
        out += b'\0'
    # 검산: 다시 읽어 쪽 수·그림 바이트
    h2, i2, r2, p2 = parse(bytes(out))
    assert len(p2) == n, (len(p2), n)
    for a, b in zip([p for p in pages if p['img']], [p for p in p2 if p['img']]):
        assert out[b['img']:b['img'] + 64] == d[a['img']:a['img'] + 64]
    stat['책 쪽 %d→%d' % (len(pages), n)] += 0
    return bytes(out)
