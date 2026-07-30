# 실행 계획: 한글 표시 (비트맵 렌더 파이프라인)

날짜: 2026-07-31 / 단계: Phase 2-①

## 목표

X4에서 `???`로 깨지는 한글을 정상 표시. 텍스트 프레임 대신 **브리지가 렌더한 1bpp 비트맵 밴드**를 전송.

## 설계

```
tmux capture-pane (유니코드 그대로)
  → Python 브리지: D2Coding(고정폭, 한글=영문 2배폭)으로 PIL 렌더 → 800×480 1bpp
  → 이전 프레임과 행 단위 diff → 변경 밴드만 POST /band?y=..&h=.. (base64 body, X-Auth)
  → 펌웨어: 48KB 프레임버퍼에 반영 → setPartialWindow + drawBitmap 부분갱신
  → 부분갱신 N회마다 전체갱신(고스팅 방지)
```

## 결정

- **JSON 대신 쿼리파라미터+base64 바디**: Arduino String의 NUL 문제 회피, ArduinoJson 대용량 파싱 회피. 디코드는 mbedtls_base64.
- **박스문자 ASCII 변환 제거**: 실폰트 렌더라 ─│╭ 등 원형 그대로 표시.
- **기존 텍스트 /frame 유지**: 폴백 경로.
- 셀 크기는 폰트 실측(getlength)으로 산출, tmux를 그 크기로 resize.

## 검증 기준

1. 렌더 PNG 자체 검사(한글·박스문자·커서 정렬)
2. 무토큰 /band → 401
3. X4 실물에서 한글 표시 + 부분갱신 동작
4. 기존 미러 성능 체감 유지 (밴드 diff 전송)
