# TourBox Console 설정 포맷 리버스엔지니어링 노트 (2026-08-12)

X4 키맵 표시(`bridge/tourbox/`)가 읽는 TourBox Console(맥, 5.11.3) 설정
구조 정리. 모든 접근은 **읽기 전용**이다.

## 데이터 위치

`~/Library/Application Support/TourBox Console/`

| 파일 | 내용 | 갱신 시점 |
|---|---|---|
| `tourbox.db` | TBDB XML. `configBytes` = 전 프리셋 바인딩 테이블, `presetNames` = 프리셋 이름 | 편집 즉시 |
| `presets/<id>` | Preset XML. `ShortDesc` 사전 = (수정키비트, SWT키코드) → 표시 설명 | 편집 즉시 |
| `tableProcess` | 프리셋 ID → 대상 프로세스 이름 (자동 전환 매핑) | 매핑 변경 시 |
| `tableid` | 마지막 활성 프리셋 ID | 전환 시 |
| `tourbox.log` | 런타임 로그 — 앱 전환·프리셋 전환이 실시간 기록됨 | 상시 |
| `import/<id>` | 프리셋 가져오기 원본(.tb = gzip TableTransfer XML) | 가져올 때만 (편집 미반영) |

## configBytes 구조

```
base64 디코드 → 30 테이블 × 3350 바이트 (테이블 순번 = 프리셋 ID)
테이블 = 22 바이트 헤더 + 256 슬롯 × 13 바이트 레코드
레코드 = [슬롯코드 1B][payload 12B]
payload = [type][aux][A: mod,cat,0,0,key][B: mod,cat,0,0,key]
```

- `aux == 0x04` → 내장 기능, id = payload[2:4] (BE)
- `type==0 && payload[2] & 0x80/0x20` → 매크로 / TourMenu 참조 (id = payload[4])
- A·B 모두 있으면 양방향(회전) 슬롯. type 바이트는 5.11.3 에서 0x06 도
  관찰됨(캘리브레이션 문서의 0x08|speed 와 다름) — 표시 목적으로는 무시.
- 수정키 비트: 0x01=⌃ 0x02=⇧ 0x04=⌥ 0x08=⌘ (macOS 기준)
- category: 0=일반키(ASCII 유사), 1=확장키, 2=마우스
- **확장키 = SWT 키 상수 하위 24비트**. `ShortDesc` 의 `<s>` 는
  일반키=키코드 그대로, 확장키=`0x1000000 | 코드` (예: F7=16777232).
  화살표 1..4, PgUp/PgDn 5/6, Home/End 7/8, F1..F20=10..29, 키패드 42..57.

## 버튼 슬롯 코드

단일 17종은 [YongHee-Kim/tourbox-preset](https://github.com/YongHee-Kim/tourbox-preset)
(MIT) 캘리브레이션 결과를 그대로 사용:
tall=0x00 side=0x01 top=0x02 short=0x03 knob=0x04 scroll=0x09
scrollـpress=0x0A dial=0x0F dpad=0x10..0x13 c1=0x22 c2=0x23 tour=0x2A
knob_press=0x37 dial_press=0x38.

콤보·더블클릭 슬롯은 `presetConf/<id>` 의 category items 배열(Console UI
슬롯 나열)이 코드 값과 1:1 인 점을 이용해 도출:

| 코드 | 슬롯 | 근거 |
|---|---|---|
| 0x05~0x08 | SIDE/TOP/TALL/SHORT + KNOB | Rotating fold=[5,6,7,8] |
| 0x0B~0x0E | SIDE/TOP/TALL/SHORT + SCROLL | Rotating fold=[11..14] |
| 0x14~0x17 | TOP + 십자키 ▲▼◀▶ | Kit fold + AI 프리셋 의미 검증(Rectangle/Ellipse/Line) |
| 0x18,0x1C,0x1F,0x21 | TALL/SHORT/TOP/SIDE 더블클릭 | Prime Four fold 순서 + AI 검증(SIDE 더블=Undo, TALL 더블=Delete) |
| 0x19~0x1E,0x20 | 4버튼 페어 콤보 6종 | Prime Four fold 순서 + AI 검증(SIDE+TALL=Cut 등) |
| 0x2B~0x2E | 십자키 더블클릭 | Kit fold + PPT 검증(단일과 동일값 중복 할당) |
| 0x24,0x25 | C1/C2 더블클릭 | Kit fold 순서 |
| 0x39,0x3A | C1/C2 콤보(미확정) | Kit fold 잔여 슬롯 — 값 존재 시 표시만 |

## 실시간 반영 경로

- **키 편집**: Console 이 `tourbox.db`·`presets/<id>` 를 즉시 저장 →
  `ConsoleStore.fingerprint()` (mtime+size) 1초 폴링으로 감지.
- **앱 전환**: `tourbox.log` 의
  `switchPreset =========> currentPresetId=N` /
  `Now Process name is:앱이름` /
  `Not found match preset,disable Tourbox` 를 tail (`ConsoleWatch`).
- 매칭 프리셋이 없는 앱은 `__Others__` 매핑이 있으면 그 프리셋, 없으면
  "프리셋 없음" 화면.

## 미해결 / 주의

- 내장 기능 id → 이름 테이블은 Console 리소스(LibTM.dec, 암호화)에 있어
  미해석 — 화면에는 `내장기능#id` 로 표기.
- `import/<id>` 는 가져오기 시점 스냅샷이라 편집이 반영되지 않는다.
  **바인딩은 반드시 tourbox.db 에서 읽을 것.**
- 매크로는 이름 해석 없이 `매크로#id` 로 표기 (macros/ 폴더 비어 있음).
