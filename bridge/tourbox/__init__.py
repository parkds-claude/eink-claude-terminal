"""TourBox Elite 키맵을 X4 e-ink에 표시하기 위한 파서·렌더러 패키지.

- codes: 버튼 슬롯/키코드/수정키 상수 (리버스엔지니어링 결과)
- store: TourBox Console 설정 디렉터리 파서 (실시간 변경 감지용 핑거프린트 포함)
- render: 800x480 1bpp 키맵 이미지 렌더러

포맷 근거:
- https://github.com/YongHee-Kim/tourbox-preset (MIT) — configBytes 13바이트
  레코드 구조·버튼 코드 캘리브레이션 결과를 참조했다.
- presetConf/N 의 category items 배열(Console UI 슬롯 배열)로 콤보 슬롯을
  추가 도출했다. 상세: docs/tourbox-format.md
"""
