# 투입 하드웨어 (2026-07-28 전수조사 기준)

전체 보유 기기 인벤토리가 아니라 **이 프로젝트에 투입 가능한 기기만** 추린 것.

## 1호기 — Xteink X4 ✅ 확정 (결정 D1)

| 항목 | 내용 |
|---|---|
| MCU | ESP32-C3 (RISC-V 싱글코어), RAM ~380KB, Flash 16MB, **PSRAM 없음** |
| 디스플레이 | 4.3" E-Ink **480×800**, 219PPI, 흑백, **부분갱신 지원** |
| 무선 | WiFi 2.4GHz + **BLE 전용 (블루투스 클래식 없음 → BLE 키보드만 연결 가능)** |
| 입력 | 물리 버튼 5개 (Up/Down/OK/Left/Right + Power) |
| 개발환경 | PlatformIO `esp32-c3-devkitm-1`, Arduino framework, 16MB dio |
| 플래시 | **BOOT 홀드 + USB 연결**해야 시리얼 등장 (평시 USB-C는 충전 전용). `esptool write-flash 0x0` 또는 웹 플래셔 |
| 식별 | MAC `14:63:93:f3:b8:88`, 포트 `/dev/cu.usbmodem2101` |
| 현재 펌웨어 | SUMI v0.6.4 + 자체 두벌식 한글 오토마타 (정품 백업 `~/xteink-ebook/backups/` 보유) |
| 파일 적재 | microSD 직결 / WiFi(crosspoint.local) / Calibre — USB로는 불가 |

**핵심 자산**: `~/xteink-ebook`에 BLE 키보드 HID 리포트 파싱 성공 코드(06-25~26, 7바이트 리포트 i=1 파싱 수정, 한글 조합 실기 확인). Phase 2~3에서 이식.

## 예비기 — Xteink X3

- 동일 ESP32-C3 계열, 3.7" 528×792. 미개조 상태 → X4 실험 실패 시 예비.

## 2호기 후보 — GDEY042T81 + Good Display ESP32 데모보드

| 항목 | 내용 |
|---|---|
| 패널 | 4.2" 400×300, SSD1683, 전체갱신 2.3초 / **부분갱신 0.39초 (보유 패널 중 최속)** |
| 구동 | Good Display 데모보드 (**ESP32-D0WD = BT 클래식+BLE 듀얼모드** → 구형 BT 키보드도 esp_hid_host로 수신 가능) + DESPI-C02, RESE=0.47 |
| 배선 | CS=27, DC=14, RST=12, BUSY=13, CLK=18, DIN=23. FPC 금색 접점 위 (역삽입 시 flash 1.8V 오류) |
| 개발환경 | PlatformIO `esp32dev` + GxEPD2 1.6.9, 포트 `/dev/cu.usbserial-2110` (맥북 직결 미인식 → USB 허브 경유) |
| 제약 | 케이스·배터리 없음(맨 기판) → 데스크 고정형 실험용 |

한글 1-bit 렌더 노하우 (gooddisplay-nametag): 작은 글자는 갈무리(Galmuri) 픽셀 폰트(9=10px/11=12px/14=15px), L(회색조) 캔버스에 그린 뒤 마지막 이진화.

## 상태 표시 보조 (터미널 아님)

- **Core Ink ×2** (1.54" 200×200, 부분갱신 0.24초): 터미널 불가(약 25×12자) → Claude 작업 상태 알림판 후보 (XIAOEEN/Claude-code-E-ink-Display 방향)
- **GeekMagic SmallTV Ultra**: 이미 mini-connect로 Claude Code 훅 상태 표시기 운영 중

## 제외 판정

- **Cardputer-Adv**: 키보드 하드웨어가 원판과 달라(I2C 컨트롤러) 커뮤니티 SSH 레포 비호환 + LCD라 취지 밖 (결정 D4)
- **StackChan/CoreS3 계열**: LCD 기기 — e-ink 취지 밖. 입력 보조 단말로만 재검토 여지

## 키보드

- **Magic Keyboard** (BLE): 맥북에 본딩돼 있어 X4 스캔에 안 뜬 이력 → 사용 시 맥북에서 forget 후 재페어링 필요
- 2026-06-25 X4 실타이핑 성공 키보드 모델 **미확정** (미해결 질문 — ROADMAP 참조)
- 제약: X4(ESP32-C3)는 BLE(HOGP) 키보드만 가능. SUMI 공식 검증 목록: Keychron/Logitech 계열

## 서버 인프라

| 항목 | 내용 |
|---|---|
| 맥미니 | M4 Pro, 24GB, 24시간 가동. `ssh macmini` (192.168.0.125 / Tailscale 100.105.124.63). **SSH 계정 `macmini`** (CLAUDE.md의 mymacbook 표기는 구정보) |
| 사용 중 포트 | 5055(bot-dashboard), 5058, 5064, 5066, 5072(cardputer-relay), 5092 — **새 브리지는 새 포트 사용** |
| 외부 노출 | Cloudflare Tunnel 경험: buddy.prefloor.io → :5072, x-device-secret 헤더 인증 (Phase 2에서 동일 패턴) |
