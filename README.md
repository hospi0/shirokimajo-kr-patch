# 하얀 마녀 ~또 하나의 영웅전설~ (새턴 JP 2장) 한글화

## 내려받기
- 최신 **v0.8** — [릴리즈](https://github.com/hospi0/shirokimajo-kr-patch/releases/latest)에서 `ShirokiMajo_KR_v0.8.zip`
- 대상: `Shiroki Majo - Mou Hitotsu no Eiyuu Densetsu (Japan)` 2장
  - 1장 트랙 1 (트랙 2개) — 원본md5 `BB23E52C0215CB2A7A6F0FC302CBCD8A` → 패치md5 `C17787F79B38CEDA7A9B581E3A5D6098`
  - 2장 트랙 1 (트랙 3개) — 원본md5 `FF022073D236272D8A8ADC84361E4843` → 패치md5 `FD43AF9BDE62882FF20E4874CD010946`
  - 2장 트랙 2 (트랙 3개) — 원본md5 `B21D07469958F8F34D51F5BA29465B86` → 패치md5 `B27589583D2162FB907F0579DD512703`

## 작업 저장소

- 인계·빌드 절차: **`docs/00_이어하기.md`** 부터.
- 번역 TSV: `work/trans/sm_ko.tsv`(대사) · `sm_param_ko.tsv`(몬스터·아이템·마법) · `sm_bin0_ko.tsv`(시스템 문구) · `sm_maphead_ko.tsv`(지명) 등, 음성 자막 `work/text/voice_sub*.tsv`
- 빌드 `python tools/smkr.py --write` → 배포 묶음 `python tools/make_dist.py`
- ROM·빌드 결과물은 들어 있지 않다.
