"""TourBox Elite configBytes 상수표 (macOS 기준).

버튼 슬롯 코드는 두 근거로 확정했다:
1. YongHee-Kim/tourbox-preset (MIT) 캘리브레이션 — 단일 버튼·회전·누름 17종
2. TourBox Console `presetConf/N` category items 배열 — Console UI의 슬롯
   나열 순서가 코드 값과 1:1 로 일치함을 이용해 콤보·더블클릭 슬롯 도출
   (예: Rotating 섹션 items=[4,55] fold=[5,6,7,8] → 노브 콤보 4종)

확장 키코드는 SWT 키 상수의 하위 24비트다 — presets/N 의 ShortDesc
설명 사전이 쓰는 큰 정수(예: 16777232=F7)는 `0x1000000 | 확장코드`.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# 버튼 슬롯: code -> (표시명, 그룹)
# 그룹: primary(본체 표기), combo(콤보 페이지), 확신도 주석 참고
# ---------------------------------------------------------------------------
SLOTS: dict[int, str] = {
    # 단일 (캘리브레이션 확정)
    0x00: "TALL",
    0x01: "SIDE",
    0x02: "TOP",
    0x03: "SHORT",
    0x04: "KNOB",            # 회전 (양방향)
    0x37: "KNOB 누름",
    0x09: "SCROLL",          # 회전 (양방향)
    0x0A: "SCROLL 누름",
    0x0F: "DIAL",            # 회전 (양방향)
    0x38: "DIAL 누름",
    0x10: "▲", 0x11: "▼", 0x12: "◀", 0x13: "▶",   # 십자키
    0x22: "C1", 0x23: "C2", 0x2A: "TOUR",
    # 콤보 — Rotating 섹션 fold=[5,6,7,8] / [11..14] (Prime Four 나열 순서
    # Side, Top, Tall, Short 를 따른다고 본 도출값)
    0x05: "SIDE+KNOB", 0x06: "TOP+KNOB", 0x07: "TALL+KNOB", 0x08: "SHORT+KNOB",
    0x0B: "SIDE+SCROLL", 0x0C: "TOP+SCROLL", 0x0D: "TALL+SCROLL", 0x0E: "SHORT+SCROLL",
    # 콤보 — Kit 섹션 fold=[43,44,45,46,20,21,22,23,36,37,57,58]
    0x2B: "▲ 더블", 0x2C: "▼ 더블", 0x2D: "◀ 더블", 0x2E: "▶ 더블",
    0x14: "TOP+▲", 0x15: "TOP+▼", 0x16: "TOP+◀", 0x17: "TOP+▶",
    0x24: "C1 더블", 0x25: "C2 더블",
    0x39: "C1 콤보", 0x3A: "C2 콤보",     # 도출 미확정 — 값 존재 시 표시만
    # 콤보 — Prime Four fold=[33,31,24,28,32,27,30,25,29,26]
    # (UI 행 순서: 더블 4종 → 페어 6종으로 본 도출값)
    0x21: "SIDE 더블", 0x1F: "TOP 더블", 0x18: "TALL 더블", 0x1C: "SHORT 더블",
    0x20: "SIDE+TOP", 0x1B: "SIDE+TALL", 0x1E: "SIDE+SHORT",
    0x19: "TOP+TALL", 0x1D: "TOP+SHORT", 0x1A: "TALL+SHORT",
}

# 본체 스키매틱에 그리는 슬롯 (나머지는 콤보 페이지)
PRIMARY = {0x00, 0x01, 0x02, 0x03, 0x04, 0x37, 0x09, 0x0A, 0x0F, 0x38,
           0x10, 0x11, 0x12, 0x13, 0x22, 0x23, 0x2A}

ROTARY = {0x04, 0x09, 0x0F}          # 양방향 회전 슬롯

# 콤보 페이지 정렬 순서 (Console UI 순서)
COMBO_ORDER = [
    0x21, 0x1F, 0x18, 0x1C,                  # 더블클릭 4종
    0x20, 0x1B, 0x1E, 0x19, 0x1D, 0x1A,      # 페어 6종
    0x2B, 0x2C, 0x2D, 0x2E,                  # 십자키 더블
    0x14, 0x15, 0x16, 0x17,                  # TOP+십자키
    0x24, 0x25, 0x39, 0x3A,                  # C1/C2
    0x05, 0x06, 0x07, 0x08,                  # +KNOB
    0x0B, 0x0C, 0x0D, 0x0E,                  # +SCROLL
]

# ---------------------------------------------------------------------------
# 수정키 (payload/ShortDesc 공통 비트) — macOS 심볼, 표준 나열 순서 ⌃⌥⇧⌘
# (D2Coding 글리프 지원 확인: 2026-08-12)
# ---------------------------------------------------------------------------
MOD_BITS = [(0x01, "⌃"), (0x04, "⌥"), (0x02, "⇧"), (0x08, "⌘")]

# ---------------------------------------------------------------------------
# 키코드: category 0 = 일반(ASCII 유사), 1 = 확장(SWT 하위 24비트), 2 = 마우스
# ---------------------------------------------------------------------------
NORMAL_KEYS = {
    0x20: "Space", 0x09: "Tab", 0x0D: "Enter", 0x1B: "Esc",
    0x08: "⌫", 0x7F: "Del",
}

EXT_KEYS = {
    1: "↑", 2: "↓", 3: "←", 4: "→",
    5: "PgUp", 6: "PgDn", 7: "Home", 8: "End", 9: "Ins",
    42: "Num*", 43: "Num+", 44: "Num-", 45: "Num-", 46: "Num.", 47: "Num/",
}
EXT_KEYS.update({i: f"F{i - 9}" for i in range(10, 30)})       # F1..F20
EXT_KEYS.update({i: f"Num{i - 48}" for i in range(48, 58)})    # 키패드 0..9

MOUSE_ACTS = {
    1: "클릭", 2: "우클릭", 3: "휠클릭", 4: "휠↑", 5: "휠↓", 6: "더블클릭",
}

SWT_EXT_BIT = 0x1000000   # ShortDesc 의 확장키 = SWT_EXT_BIT | 확장코드


def mods_label(bits: int) -> str:
    return "".join(name for bit, name in MOD_BITS if bits & bit)


def key_label(cat: int, code: int) -> str | None:
    """(category, keycode) → 표시 문자열. 모르는 값은 None."""
    if cat == 0:
        if code in NORMAL_KEYS:
            return NORMAL_KEYS[code]
        if 33 <= code < 127:
            return chr(code)
        return None
    if cat == 1:
        return EXT_KEYS.get(code)
    if cat == 2:
        return MOUSE_ACTS.get(code)
    return None


def swt_code(cat: int, code: int) -> int | None:
    """payload (cat, code) → ShortDesc 설명 사전의 키값. 마우스는 없음."""
    if cat == 0:
        return code
    if cat == 1:
        return SWT_EXT_BIT | code
    return None
