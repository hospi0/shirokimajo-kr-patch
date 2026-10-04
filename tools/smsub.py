# -*- coding: utf-8 -*-
r"""동영상 대사 자막 굽기 (2026-10-04) — 걸리버 보이 tools/moviesub_all.py · opening_enc.py 를 이 게임에 맞게 옮김
  번역 = work/text/movie_sub.tsv (영상 · 시작초 · 끝초 · 원문 · 번역(«\n» = 다음 자막, 한 행 시간을 글자 수 비례로 나눔) · 비고)
         원문 = 사용자 받아쓰기 my files/할일/무비.txt (효과음만인 줄은 뺌)
  영상 = CPK/Mnn.CPK — Sega FILM 1.09 · cinepak 320×224 15fps · 프레임마다 띠 2개(112줄) · 8비트 PCM 22050Hz
    ★STAB 은 모든 프레임을 키로 표시하지만 실제 프레임은 거의 전부 앞 프레임 참조 → 진짜 키 = 첫 띠 번호 0x1000(프레임 머리 0 바이트 0)
      그래서 재굽기 구간(GOP)은 이 진짜 키 기준으로 자르고, STAB 정보 칸은 원본 그대로 둔다.
  그리기 = 나눔고딕 Bold 14px 흰색 + 검은 1px 테두리, 화면 아래 가운데, 넘치면 어절 두 줄 · 부호 뒤 공백 삭제(전프로젝트 규칙)
  굽기 = 자막 든 GOP 만 ffmpeg cinepak(띠 2개, 첫 프레임 키) → 새턴식 변환(filmcpk.to_saturn) · 구간 바이트 ≤ 원본(+앞 구간 남은 몫)이 되게 q
         못 맞추면 가장 작은 판으로 빚지고 뒤 구간에서 갚음 — 끝내 원본보다 크면 그대로(smkr/isotree 가 파일을 끝으로 옮김)
  → work/kr/Mnn.CPK + 미리보기 work/movie/sub/Mnn_kr.mp4
  python tools/smsub.py [M01 M04 …]   (없으면 표의 영상 전부)
"""
import glob, os, re, shutil, struct, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import filmcpk

FFBIN = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin'
FF = os.path.join(FFBIN, 'ffmpeg.exe')
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX, W, H, FPS, STRIPS = 14, 320, 224, 15, 2
TSV = os.path.join(ROOT, 'work', 'text', 'movie_sub.tsv')
PUNCT_SP = re.compile(r'([,.!?:;)\]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )')
TMP = os.path.join(ROOT, 'work', 'movie', 'sub', '_gop')


def src_cpk(name):
    p = glob.glob(os.path.join(ROOT, 'work', 'disc', 'd*', 'CPK', name + '.CPK'))
    assert len(p) == 1, (name, p)
    return p[0]


def duration(p):
    r = subprocess.run([os.path.join(FFBIN, 'ffprobe.exe'), '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', p], capture_output=True, text=True)
    return float(r.stdout.strip())


def rows():
    out = {}
    for ln in open(TSV, encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        c = ln.rstrip('\n').split('\t')
        if not c[4].strip():
            continue
        parts = [PUNCT_SP.sub(r'\1', p.strip()) for p in c[4].split('\\n')]
        out.setdefault(c[0], []).append((float(c[1]), float(c[2]), parts))
    return out


def events(rs, dur):
    """받아쓰기 구간 [시작, 끝] — 읽을 시간(글자×0.18초 + 조각×1.0초, 조각당 최소 1.3초)보다 짧으면 다음 행 앞까지 늘리고,
       지나치게 길면(구간에 무음·음악이 섞임) 읽을 시간 + 1초로 줄인다 (걸리버와 같음)"""
    ev = []
    for k, (s, e, parts) in enumerate(rs):
        nxt = rs[k + 1][0] if k + 1 < len(rs) else dur
        chars = sum(len(p) for p in parts)
        need = max(chars * 0.18 + 1.0 * len(parts), 1.3 * len(parts))
        end = min(e, s + need + 1.0)
        if end - s < need:
            end = s + need
        end = min(end, nxt - 0.07, dur - 0.05)
        a = s
        for p in parts:
            d = (end - s) * max(len(p), 4) / sum(max(len(q), 4) for q in parts)
            ev.append((a, a + d, p)); a += d
    return ev


def wrap(text, F):
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    if d.textlength(text, font=F) <= W - 16:
        return [text]
    words = text.split(' ')
    best = min((max(d.textlength(' '.join(words[:i]), font=F), d.textlength(' '.join(words[i:]), font=F)),
                [' '.join(words[:i]), ' '.join(words[i:])]) for i in range(1, len(words)))
    assert best[0] <= W - 16, ('두 줄로도 넘침', text)
    return best[1]


def plate(text, F):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lines = wrap(text, F)
    y = H - 14 - (len(lines) - 1) * 17
    for ln in lines:
        d.text((W / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0)); y += 17
    a = im.getchannel('A').point(lambda v: 255 if v >= 128 else 0)       # 반투명 없이(시네팩 번짐 줄임)
    im.putalpha(a)
    return im


def frames(name):
    fr = os.path.join(ROOT, 'work', 'movie', 'frames', name.lower())
    if not glob.glob(os.path.join(fr, 'f*.png')):
        os.makedirs(fr, exist_ok=True)
        subprocess.run([FF, '-v', 'error', '-y', '-i', src_cpk(name), '-fps_mode', 'passthrough',
                        os.path.join(fr, 'f%04d.png')], check=True)
    return fr


def encode_gop(paths, q):
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    for i, p in enumerate(paths):
        shutil.copyfile(p, os.path.join(TMP, 'g%04d.png' % (i + 1)))
    avi = os.path.join(TMP, 'o.avi')
    subprocess.run([FF, '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(TMP, 'g%04d.png'),
                    '-c:v', 'cinepak', '-min_strips', str(STRIPS), '-max_strips', str(STRIPS), '-max_extra_cb_iterations', '4',
                    '-g', '9999', '-q:v', str(q), avi], check=True)
    pk = filmcpk.avi_packets(open(avi, 'rb').read())
    assert len(pk) == len(paths), (len(pk), len(paths))
    return [filmcpk.to_saturn(p, i == 0) for i, p in enumerate(pk)]


def reencode(src, fr, changed, kr, out, log):
    film = filmcpk.read(open(src, 'rb').read())
    vid = [i for i, e in enumerate(film['stab']) if e[2] != 0xFFFFFFFF]
    key = [k for k, i in enumerate(vid) if film['chunks'][i][0] == 0]          # ★진짜 키(프레임 머리 플래그 0 = 첫 띠 0x1000)
    assert key and key[0] == 0
    gops = list(zip(key, key[1:] + [len(vid)]))
    chunks = list(film['chunks']); infos = [e[2] for e in film['stab']]
    carry = 0; n_re = 0
    for a, b in gops:
        if not any(a <= f < b for f in changed):
            continue
        paths = [os.path.join(kr if f in changed else fr, 'f%04d.png' % (f + 1)) for f in range(a, b)]
        budget = sum(len(film['chunks'][vid[f]]) for f in range(a, b))
        for q in (1, 2, 3, 4, 6, 8, 12, 16, 24, 31):
            new = encode_gop(paths, q)
            if sum(map(len, new)) <= budget + carry:
                break
        else:
            log('  ⚠구간 %d‥%d 빚 %d B' % (a + 1, b, sum(map(len, new)) - budget - carry))
        carry += budget - sum(map(len, new))
        for f, c in zip(range(a, b), new):
            chunks[vid[f]] = c                                                  # 정보 칸(STAB)은 원본 그대로
        n_re += 1
        log('  구간 %4d‥%4d (%3d프레임) q %2d  %7d / %7d B' % (a + 1, b, b - a, q, sum(map(len, new)), budget))
    assert all(len(c) % 4 == 0 for c in chunks), '4 바이트 정렬 아님'
    data = filmcpk.write(film, chunks, infos)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(data)
    return n_re, len(gops), len(data)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    allr = rows()
    names = [a for a in sys.argv[1:] if a.startswith('M')] or sorted(allr)
    log = lambda *a: print(*a, flush=True)
    F = ImageFont.truetype(FONT, PX)
    for name in names:
        src = src_cpk(name)
        dur = duration(src)
        ev = events(allr[name], dur)
        log('== %s 자막 %d개 (%.1f초)' % (name, len(ev), dur))
        fr = frames(name)
        nf = len(glob.glob(os.path.join(fr, 'f*.png')))
        kr = os.path.join(fr, 'kr')
        if os.path.isdir(kr):
            shutil.rmtree(kr)
        os.makedirs(kr)
        changed = set()
        for a, b, text in ev:
            log('   %6.2f‥%6.2f  %s' % (a, b, text))
            pl = plate(text, F)
            for f in range(nf):
                if a <= f / FPS < b:
                    im = Image.open(os.path.join(fr, 'f%04d.png' % (f + 1))).convert('RGBA')
                    im.alpha_composite(pl)
                    im.convert('RGB').save(os.path.join(kr, 'f%04d.png' % (f + 1))); changed.add(f)
        out = os.path.join(ROOT, 'work', 'kr', name + '.CPK')
        n_re, n_g, size = reencode(src, fr, changed, kr, out, log)
        o = os.path.getsize(src)
        log('%s 덮은 프레임 %d · 다시 구운 구간 %d/%d · %d B (원본 %d, %+d)' % (name, len(changed), n_re, n_g, size, o, size - o))
        os.makedirs(os.path.join(ROOT, 'work', 'movie', 'sub'), exist_ok=True)
        subprocess.run([FF, '-v', 'error', '-y', '-i', out, '-vf', 'scale=%d:%d:flags=neighbor' % (W * 2, H * 2),
                        '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
                        os.path.join(ROOT, 'work', 'movie', 'sub', name + '_kr.mp4')], check=True)


if __name__ == '__main__':
    main()
