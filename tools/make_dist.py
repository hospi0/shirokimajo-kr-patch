# -*- coding: utf-8 -*-
r"""白き魔女 배포 묶음 — dist/ShirokiMajo_KR_<VER>/ : 바뀐 트랙마다 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat(CP949)
  바뀌는 트랙: 1장 트랙 1 · 2장 트랙 1·2(2장 트랙 2 = 데이터 트랙, 트랙 1이 길어져 섹터 머리 주소가 바뀜)
  검증: 원본 트랙 → xdelta 적용 → md5 = 빌드 결과(work/out) md5 (세 파일 모두).
  python tools/make_dist.py   (먼저 python tools/smkr.py --write)
"""
import hashlib, os, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

VER = 'v0.8'
XDELTA = r'C:\claude\utils\xdelta.exe'
ROMS = r'C:\claude\roms\ss'
OUT = os.path.join(ROOT, 'work', 'out')
NAME = 'ShirokiMajo_KR_' + VER
TITLE = '하얀 마녀 ~또 하나의 영웅전설~ (Shiroki Majo, 세가 새턴 일본판) 한글 패치 ' + VER
DISCS = [(1, 2, (1,)), (2, 3, (1, 2))]           # (장, 트랙 수, 패치할 트랙)


def rom(n):
    return 'Shiroki Majo - Mou Hitotsu no Eiyuu Densetsu (Japan) (Disc %d)' % n


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 {t}번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 파일을 이 폴더에 복사
{bins}
     (두 장 중 한 장만 있어도 그 장만 패치합니다. 2장은 트랙 1·2 둘 다 넣어 주세요)
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 이름으로 바꿔 넣고, 나머지 트랙과 cue 는 그대로 쓰세요

  직접 적용:
    xdelta.exe -d -s "원본 트랙" "패치 파일" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - 본편 대사 전부, 화자 이름표, 마을·지역 이름, 장 제목
  - 메뉴·상태창·시스템 문구, 전투 결과 문구
  - 몬스터·아이템·마법 이름과 설명
  - 책(도서) 본문과 표지 제목
  - 거리 표지판, 월드맵 지명판 그림 34장
  - 동영상 자막, 음성 장면 자막 21개


[ 알려진 점 ]

  - 아직 끝까지 실기로 통독하지 못했습니다. 이상한 곳이 있으면 알려 주세요.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
set DONE=0
{blocks}
if "%DONE%"=="0" (
  echo   [오류] 원본 트랙 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
echo   완료
pause
"""

BLOCK = r"""if exist "%~dp0{bin}" (
  "%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
  if errorlevel 1 (
    echo   [오류] {n}장 트랙 {t} 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
    pause & exit /b 1
  )
  echo   {n}장 트랙 {t}: "{kbin}"
  set DONE=1
)
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    heads, blocks, bins = [], [], []
    for n, tracks, pts in DISCS:
        for t in pts:
            b = '%s (Track %d).bin' % (rom(n), t)
            src = os.path.join(ROMS, rom(n), b); out = os.path.join(OUT, 'd%d' % n, b)
            patch = '%s_Disc%d_Track%d.xdelta' % (NAME, n, t); pp = os.path.join(d, patch)
            subprocess.run([XDELTA, '-e', '-9', '-f', '-s', src, out, pp], check=True)
            chk = os.path.join(d, '_check.bin')
            subprocess.run([XDELTA, '-d', '-f', '-s', src, pp, chk], check=True)
            o, want, got = md5(src), md5(out), md5(chk)
            os.remove(chk)
            assert got == want, ('패치 적용 결과가 빌드와 다름', n, t, got, want)
            heads.append(HEAD.format(tracks=tracks, rom=rom(n), t=t, o=o, d=want))
            kbin = '%s (Track %d) [KR].bin' % (rom(n), t)
            blocks.append(BLOCK.format(bin=b, patch=patch, kbin=kbin, n=n, t=t))
            bins.append('       "%s"' % b)
            print('%d장 트랙 %d 원본md5 %s → 패치md5 %s · %s %d B' % (n, t, o, want, patch, os.path.getsize(pp)))
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = TITLE + '\n' + '=' * 60 + '\n\n' + '\n\n'.join(heads) + BODY.format(bins='\n'.join(bins))
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(BAT.format(blocks=''.join(blocks)).replace('\n', '\r\n').encode('cp949'))
    z = os.path.join(ROOT, 'dist', NAME + '.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(d)):
            zf.write(os.path.join(d, f), NAME + '/' + f)
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-56s %12d' % (f, os.path.getsize(os.path.join(d, f))))
    print('  zip %s %d B · md5 %s' % (os.path.basename(z), os.path.getsize(z), md5(z)))


if __name__ == '__main__':
    main()
