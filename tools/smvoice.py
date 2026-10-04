# -*- coding: utf-8 -*-
r"""음성(SAP) 자막 (2026-10-04 밤 시험: V01) — 맵 화면에서 SAP 음성이 나올 때 게임 자체 «지명 자막»(FF 87 의 그리기)으로 화면 아래에 띄움
  번역 = work/text/voice_sub.tsv (음성 · 시작초 · 끝초 · 원문 · 번역(«\n» = 다음 자막) · 비고), 원문 = 사용자 받아쓰기
  시계 = 프레임(60Hz, 스크립트 FF 35 기다리기와 같은 단위 — V02 기다리기 합 101.8초 ≈ 음성 110초 로 확인). 0 = FF 42 처리 함수가 끝난 때.
  자리 = KANJI12.FON 의 JIS 9‥12구(글자 없는 줄, 원문·한글 배정 모두 안 씀) 376칸 × 18 B = 6,768 B
         — 부팅 때 LowRAM 0x002B6004 에 상주 적재(0.BIN 0x060043E0 근처 로더) → 0x002B94E4‥
  갈고리(0.BIN 포인터만 바꿈, 함수 본문 손 안 댐):
    · 명령 표 FF 42 칸(0x0600CF40 필드 · 0x06038E28 다른 모드) → H42: 음성 번호(u16 인자) 읽고 원래 0x06014984 부른 뒤 자막 표 켬
    · 매 프레임 자막 갱신 0x06010070 을 부르는 리터럴(0x060061A4 · 0x06006314) → HUPD: 프레임 세고 시각이면
        0x0600FF70(글, 머무름 0x7FFF, 모드 1 = 화면 아래에서 올라옴 — 게임은 모드 0(위)만 씀) / 끝이면 0x06010048(내려감) → 원래 함수로
  자막 함수는 지명 자막과 한 벌(같은 구조체 0x002F8E58)을 쓰므로 음성 중 FF 87 지명이 나오면 자막이 그것으로 바뀜.
"""
import os, re, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
import sh2asm

FONT_LOAD = 0x002B6004
ROW0, ROWS = 8 * 94, 4 * 94                     # JIS 9‥12구 색인
BASE = FONT_LOAD + ROW0 * 18                    # 0x002B94E4
ROOM = ROWS * 18
L0 = 0x06004000
LIT_UPD = (0x060061A4, 0x06006314); ORIG_UPD = 0x06010070
SLOT_42 = (0x0600CF40, 0x06038E28); ORIG_42 = 0x06014984
SCRIPT_PTR = 0x0609408C
CAPTION = 0x0600FF70; HIDE = 0x06010048
# 엔딩(V20, 스크립트 FF 84 → 0x06015868 → 엔딩 함수 0x0603E230 — 자체 프레임 루프라 필드 갱신 0x06010070 이 안 돎)
LIT_V20 = 0x0603E504; ORIG_V20 = 0x0603E040              # 엔딩 함수 안 0x0603E3D0 의 JSR 대상(V20 재생)
LIT_SYNC = (0x0603DA50, 0x0603DEFC, 0x0603E2AC, 0x0603E4F8); ORIG_SYNC = 0x0606B446   # 엔딩 함수들 리터럴 안 프레임 동기(slSynch)
CAP_STATE = 0x002F8E5A                                      # 자막 구조체 +2(상태)
VOICE_FPS = {'V20': 60}
TEXT_FROM = 4400                                            # 글꼴 색인 ≥ 이 값의 «원문 안 쓰는 한자 칸» = 자막 글 전용(smkr 한글 배정은 이 아래만)                                     # ⏳엔딩 프레임 빠르기 미확인(30 이면 바꿈)
FPS = 60
MAXC = 20                                         # 자막 한 줄 글자 수(전각 12px) — 그리기 버퍼 폭 안
TSV = os.path.join(ROOT, 'work', 'text', 'voice_sub.tsv')
PUNCT_SP = re.compile(r'([,.!?:;)\]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )')    # 부호 뒤 공백 삭제(전프로젝트 규칙)
FW = str.maketrans({' ': '　', '!': '！', '?': '？', ',': '，', '.': '．', '~': '～', '(': '（', ')': '）', ':': '：', '-': '－'})


def rows():
    out = {}
    import glob
    for ln in (l for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'text', 'voice_sub*.tsv'))) for l in open(f, encoding='utf-8')):
        if ln.startswith('#') or not ln.strip():
            continue
        c = ln.rstrip('\n').split('\t')
        out.setdefault(c[0], []).append((float(c[1]), float(c[2]), [PUNCT_SP.sub(r'\1', p.strip()) for p in c[4].split('\\n')]))
    return out


def split_long(p):
    """MAXC 자 넘는 조각은 어절에서 나눔"""
    if len(p) <= MAXC:
        return [p]
    ws = p.split(' ')                                 # 두 조각 길이가 가장 비슷한 어절 경계에서(«한다.»만 남는 것 방지)
    cut = min(range(1, len(ws)), key=lambda i: max(len(' '.join(ws[:i])), len(' '.join(ws[i:]))))
    return split_long(' '.join(ws[:cut])) + split_long(' '.join(ws[cut:]))


def events(rs, fps=FPS):
    """→ [(시작 프레임, 끝 프레임, 글)] — 받아쓰기 구간 안에서 조각을 글자 수 비례로 나눔, 다음 대사 전까지"""
    ev = []
    for k, (s, e, parts) in enumerate(rs):
        nxt = rs[k + 1][0] if k + 1 < len(rs) else e + 1.0
        e = min(max(e, s + 1.2 * len(parts)), nxt)
        ps = [q for p in parts for q in split_long(p)]
        tot = sum(max(len(q), 4) for q in ps); a = s
        for q in ps:
            d = (e - s) * max(len(q), 4) / tot
            ev.append((round(a * fps), round((a + d) * fps), q)); a += d
    return ev


def texts():
    """빌더 글자 배정용 — 화면에 나갈 글 전부(전각 변환 뒤)"""
    return [t.translate(FW) for rs in rows().values() for *_, t in events(rs)]


def build(encode, text_slots=None):
    """encode(글) → 게임 바이트(00 없이). → (글꼴 칸 bytes(ROOM 안), 0.BIN 패치 [(주소, u32)]), 요약"""
    R = rows()
    a = sh2asm.Asm(BASE + 16)                     # 앞 16 B = 상태 [표 항목][프레임][번호][보이는 중]
    a.defl('state', BASE); a.defl('sptr', SCRIPT_PTR); a.defl('o42', ORIG_42); a.defl('oupd', ORIG_UPD)
    a.defl('cap', CAPTION); a.defl('hide', HIDE); a.defw('hold', 0x7FFF); a.defw('m15', 0x7FFF)
    # ── H42 ──
    a.label('h42')
    a.stspr_predec('r15'); a.movl_push('r8')
    a.movl_pc('sptr', 'r1'); a.movl_load('r1', 'r1'); a.movw_load('r1', 'r8'); a.extuw('r8', 'r8')
    a.movl_pc('o42', 'r1'); a.jsr('r1'); a.nop()
    a.movl_pc('state', 'r4'); a.movl_pc('table', 'r2')
    a.label('lp')
    a.movw_load('r2', 'r3'); a.extuw('r3', 'r3'); a.tst('r3', 'r3'); a.bt('nf')
    a.cmpeq('r8', 'r3'); a.bt('found')
    a.addi(8, 'r2'); a.bra('lp'); a.nop()
    a.label('found')
    a.movl_store('r2', 'r4'); a.movi(0, 'r3')
    a.w(0x1431); a.w(0x1432); a.w(0x1433)        # mov.l r3,@(4|8|12,r4)
    a.bra('out'); a.nop()
    a.label('nf')
    a.movi(0, 'r3'); a.movl_store('r3', 'r4')
    a.label('out')
    a.movl_postinc('r15', 'r8'); a.ldspr_postinc('r15'); a.rts(); a.nop()
    # ── H20(엔딩 V20 시작): 원래 재생 → 표에서 20 찾아 켜고 자막 구조체 상태 0 ──
    a.defl('o20', ORIG_V20); a.defl('capst', CAP_STATE); a.defl('osync', ORIG_SYNC)
    a.label('h20')
    a.stspr_predec('r15')
    a.movl_pc('o20', 'r1'); a.jsr('r1'); a.nop()
    a.movl_pc('capst', 'r1'); a.movi(0, 'r3'); a.movw_store('r3', 'r1')
    a.movl_pc('state', 'r4'); a.movl_pc('table', 'r2'); a.movi(20, 'r5')
    a.label('lp20')
    a.movw_load('r2', 'r3'); a.extuw('r3', 'r3'); a.tst('r3', 'r3'); a.bt('nf20')
    a.cmpeq('r5', 'r3'); a.bt('f20')
    a.addi(8, 'r2'); a.bra('lp20'); a.nop()
    a.label('f20')
    a.movl_store('r2', 'r4'); a.movi(0, 'r3')
    a.w(0x1431); a.w(0x1432); a.w(0x1433)
    a.bra('o20x'); a.nop()
    a.label('nf20')
    a.movi(0, 'r3'); a.movl_store('r3', 'r4')
    a.label('o20x')
    a.ldspr_postinc('r15'); a.rts(); a.nop()
    # ── HSYNC(엔딩 매 프레임): 자막 처리 → 자막 갱신 0x06010070(애니·스프라이트) → 원래 프레임 동기로 ──
    a.label('hsync')
    a.stspr_predec('r15')
    a.movl_pc('stepa', 'r1'); a.jsr('r1'); a.nop()
    a.movl_pc('oupd', 'r1'); a.jsr('r1'); a.nop()
    a.movl_pc('osync', 'r1'); a.ldspr_postinc('r15'); a.jmp('r1'); a.nop()
    # ── HUPD(필드 매 프레임): 자막 처리 → 원래 갱신으로 ──
    a.label('hupd')
    a.stspr_predec('r15')
    a.movl_pc('stepa', 'r1'); a.jsr('r1'); a.nop()
    a.movl_pc('oupd', 'r1'); a.ldspr_postinc('r15'); a.jmp('r1'); a.nop()
    # ── STEP(공통): 프레임 세고 자막 띄움/내림 ──
    a.label('step')
    a.stspr_predec('r15')
    a.movl_pc('state', 'r4'); a.movl_load('r4', 'r5'); a.tst('r5', 'r5'); a.bt('done')
    a.w(0x5641); a.addi(1, 'r6'); a.w(0x1461)    # r6 = ++프레임
    a.w(0x5742)                                   # r7 = 번호
    a.w(0x8551); a.extuw('r0', 'r0')              # r0 = 개수
    a.cmphs('r0', 'r7'); a.bt('stop')
    a.w(0x5151)                                   # r1 = 사건 표
    a.mov('r7', 'r2'); a.shll2('r2'); a.shll('r2'); a.add('r2', 'r1')
    a.w(0x5343); a.tst('r3', 'r3'); a.bf('shown')
    a.movw_load('r1', 'r2'); a.extuw('r2', 'r2'); a.cmphs('r2', 'r6'); a.bf('done')
    a.movi(1, 'r3'); a.w(0x1433)                  # 보이는 중 = 1
    a.w(0x5411)                                   # r4 = 글 주소 @(4,r1)
    a.movw_pc('hold', 'r5'); a.movi(1, 'r6')
    a.movl_pc('cap', 'r1'); a.jsr('r1'); a.nop()
    a.bra('done'); a.nop()
    a.label('shown')
    a.w(0x8511); a.extuw('r0', 'r0')              # r0 = 끝(위 비트 = 내리지 않음)
    a.mov('r0', 'r2'); a.movw_pc('m15', 'r3'); a.andr('r3', 'r2')
    a.cmphs('r2', 'r6'); a.bf('done')
    a.movi(0, 'r3'); a.w(0x1433)                  # 보이는 중 = 0
    a.addi(1, 'r7'); a.w(0x1472)                  # 번호 + 1
    a.shlr8('r0'); a.andi(0x80); a.tst('r0', 'r0'); a.bf('done')
    a.movl_pc('hide', 'r1'); a.jsr('r1'); a.nop()
    a.bra('done'); a.nop()
    a.label('stop')
    a.movi(0, 'r3'); a.movl_store('r3', 'r4')
    a.label('done')
    a.ldspr_postinc('r15'); a.rts(); a.nop()
    # 표·STEP 주소는 코드 길이를 알아야 하므로 두 번 조립
    a.defl('table', 0); a.defl('stepa', 0)
    code, _ = a.assemble()
    tbl = BASE + 16 + len(code); tbl += (-tbl) % 4
    a.lit_l['table'] = tbl; a.lit_l['stepa'] = a.labels['step']
    code, _ = a.assemble()
    h42, hupd, h20, hsync = a.labels['h42'], a.labels['hupd'], a.labels['h20'], a.labels['hsync']
    names = sorted(R)
    ev = {v: events(R[v], VOICE_FPS.get(v, FPS)) for v in names}
    p = tbl + 8 * (len(names) + 1)                 # 음성 표 뒤 = 앞 자리 남은 곳
    nev = sum(len(x) for x in ev.values())
    # 자리: 앞 자리 남은 곳 → 모자라면 글꼴의 «자막 전용 빈 한자 칸»(TEXT_FROM 이상, 원문·한글 배정 안 씀) 연속 구간들
    tail_end = BASE + ROOM
    runs = [[p, tail_end]]
    s_ = sorted(i for i in (text_slots or []) if i >= TEXT_FROM)
    i = 0
    while i < len(s_):
        j = i
        while j + 1 < len(s_) and s_[j + 1] == s_[j] + 1:
            j += 1
        if j - i + 1 >= 4:
            runs.append([FONT_LOAD + s_[i] * 18, FONT_LOAD + (s_[j] + 1) * 18])
        i = j + 1
    W = {}                                          # RAM 주소 → bytes
    def put(b, align=2):
        for r in runs:
            a0 = r[0] + (-r[0]) % align
            if a0 + len(b) <= r[1]:
                r[0] = a0 + len(b); W[a0] = b
                return a0
        raise SystemExit('⛔음성 자막 자리 넘침(글꼴 칸까지)')
    evp = {}
    for v in names:                                 # 사건 표(8 B × 개수, 4 정렬) 먼저 — 글 주소는 나중에 채움
        evp[v] = put(bytes(8 * len(ev[v])), 4)
    for v in names:
        es = ev[v]; eb = bytearray()
        for k, (s, e, t) in enumerate(es):
            ta = put(encode(t.translate(FW)) + b'\x00')
            keep = k + 1 < len(es) and es[k + 1][0] <= e + 6       # 다음 자막이 바로 이어지면 내리지 않고 바꿔 끼움
            eb += struct.pack('>HHI', s, e | (0x8000 if keep else 0), ta)
        W[evp[v]] = bytes(eb)
    assert max(s for v in names for s, e, t in ev[v]) < 0x8000
    tb = bytearray()
    for v in names:
        tb += struct.pack('>HHI', int(v[1:]), len(ev[v]), evp[v])
    tb += bytes(8)
    blob = bytearray(bytes(16) + code + bytes(tbl - BASE - 16 - len(code)) + tb)
    fwrites = {}
    for a0, b in W.items():
        if BASE <= a0 < tail_end:
            o = a0 - BASE
            blob += bytes(max(0, o + len(b) - len(blob)))
            blob[o:o + len(b)] = b
        else:
            fwrites[a0] = b
    assert len(blob) <= ROOM, ('음성 자막 자리 넘침', len(blob), ROOM)
    blob = bytes(blob)
    patches = [(x, hupd) for x in LIT_UPD] + [(x, h42) for x in SLOT_42]
    if 'V20' in R:                                                  # 엔딩 갈고리는 V20 자막이 있을 때만
        patches += [(LIT_V20, h20)] + [(x, hsync) for x in LIT_SYNC]
    fw = [((a - FONT_LOAD), b) for a, b in sorted(fwrites.items())]       # 글꼴 파일 오프셋, bytes
    return blob, patches, fw, '음성 자막 %s · 사건 %d · 앞 자리 %d / %d B · 글꼴 칸 %d B' % (
        ','.join(names), nev, len(blob), ROOM, sum(len(b) for _, b in fw))


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    for v, rs in rows().items():
        for s, e, t in events(rs, VOICE_FPS.get(v, FPS)):
            print(v, '%5d‥%5d (%.2f‥%.2f) %s' % (s, e, s / FPS, e / FPS, t.translate(FW)))
    blob, pt, fw, info = build(lambda t: t.encode('utf-16-be'), list(range(4400, 7808)))
    print(info, [(hex(a), hex(b)) for a, b in pt])
