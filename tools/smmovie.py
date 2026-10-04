# -*- coding: utf-8 -*-
r"""동영상·음성 추출(2026-10-04) → work/movie/d1·d2/
  CPK = Sega FILM(시네팩 320×224 15fps + 8비트 PCM 22050Hz 스테레오) → mp4(H.264 crf 18 + AAC), 원래 크기 그대로
  SAP = AIFF 식 머리 [프레임 수 u32][채널 u32=2][비트 u32=16][80비트 실수 44100Hz] + 0x800 부터 16비트 BE 스테레오 PCM(채널 4096표본 덩어리 교대) → wav
        (동영상 길이와 안 맞음 — 따로 재생되는 음성 클립)
python tools/smmovie.py"""
import glob, os, struct, subprocess, sys, wave
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'


SR = 22050   # ★머리엔 44100 이지만 그대로 틀면 목소리가 중간값 735Hz(2배 빠름) — 22050 이 맞음(2026-10-04 밤 사용자 «이상함»)


def sap_to_wav(src, dst):
    d = open(src, 'rb').read()
    n, ch, bits = struct.unpack_from('>III', d, 0)
    assert (ch, bits) == (2, 16) and d[12:16] == b'\x40\x0d\xac\x44', src
    if os.path.basename(src).upper().startswith('V20'):
        # ★V20(엔딩, 디스크 2 트랙 2, 전용 재생 함수 0x0603E040)은 형식이 다름: 섹터 6개 중 2개만 데이터, 나머지 4개는 빈 채움 섹터
        #   (서브헤더·EDC 까지 0 — 2배속 스트리밍 속도 맞춤) → 0 섹터 빼고 이으면 16비트 BE «모노» 44100Hz(머리는 2채널이라 적혀 있음 — 홀짝 표본 차이가 같아 모노로 판정, 사용자 «높게 깨짐» 2026-10-04 밤 · 초당 88,200 B = 다른 SAP 와 같음)
        S = 0x800
        data = b''.join(d[k * S:(k + 1) * S] for k in range(1, len(d) // S) if d[k * S:(k + 1) * S].strip(b'\x00'))
        s = np.frombuffer(data[:len(data) // 2 * 2], dtype='>i2')
        with wave.open(dst, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(s.astype('<i2').tobytes())
        return len(s) / 44100
    # ★채널은 표본 단위가 아니라 4096표본(0x2000 B) 덩어리로 번갈아 듦(L 덩어리, R 덩어리, …) — 표본 단위로 읽으면 소리가 찢어짐(2026-10-04 밤 사용자)
    B = 4096
    a = np.frombuffer(d[0x800:], dtype='>i2')
    k = len(a) // (ch * B)
    s = a[:k * ch * B].reshape(k, ch, B).transpose(0, 2, 1).reshape(-1, ch)[:n]
    with wave.open(dst, 'wb') as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(SR); w.writeframes(s.astype('<i2').tobytes())
    return n / SR


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for disc in ('d1', 'd2'):
        out = os.path.join(ROOT, 'work', 'movie', disc); os.makedirs(out, exist_ok=True)
        for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'disc', disc, 'CPK', '*.CPK'))):
            dst = os.path.join(out, os.path.basename(f)[:-4] + '.mp4')
            subprocess.run([FF, '-v', 'error', '-y', '-i', f, '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-b:a', '160k', dst], check=True)
            print(disc, os.path.basename(dst), os.path.getsize(dst))
        for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'disc', disc, 'SAP', '*.SAP'))):
            dst = os.path.join(out, os.path.basename(f)[:-4] + '.wav')
            print(disc, os.path.basename(dst), '%.1f초' % sap_to_wav(f, dst))


if __name__ == '__main__':
    main()
