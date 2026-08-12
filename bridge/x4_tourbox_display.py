#!/usr/bin/env python3
"""TourBox Elite 키 세팅을 X4 e-ink 에 표시하는 브리지.

x4_bitmap_bridge(터미널 미러)를 대체하는 표시 모드다. TourBox Console 의
설정 디렉터리를 읽어(쓰기 없음) 현재 전면 앱의 프리셋 키맵을 스키매틱
다이어그램으로 그린다.

실시간 반영:
- 앱/프리셋 전환: tourbox.log tail (Console 이 전환 즉시 기록)
- 키 세팅 편집:   tourbox.db·presets/* mtime 핑거프린트 (Console 이 즉시 저장)

X4 물리버튼: 위/아래 = 메인 ↔ 콤보 페이지, 확인 = 전체 리프레시.
전송 계층(post_band, dirty_bands 등)은 x4_bitmap_bridge 를 그대로 재사용.
"""
from __future__ import annotations

import argparse
import sys
import time

from PIL import Image

import x4_bitmap_bridge as xb
from x4_bitmap_bridge import (
    PANEL_H, PANEL_W, STRIDE, INVERT_TABLE,
    dirty_bands, fetch_buttons, post_band, resolve_base, x4_status,
)
from tourbox.render import KeymapRenderer
from tourbox.store import ConsoleStore, Snapshot
from tourbox.watch import ConsoleWatch

BATT_BAR_H = 4
BATT_STEP = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x4", required=True, help="X4 base URL, e.g. http://x4-terminal.local")
    parser.add_argument("--font", default=None, help="TTF path (default: bundled D2Coding)")
    parser.add_argument("--interval", type=float, default=0.5, help="poll seconds")
    parser.add_argument("--post-timeout", type=float, default=12.0)
    parser.add_argument("--token", default="", help="X-Auth shared secret")
    parser.add_argument("--full-every", type=float, default=300.0,
                        help="잔상 방지용 전체갱신 최소 주기(초), 0=비활성")
    return parser.parse_args()


def to_1bpp(img: Image.Image, battery: int | None) -> bytes:
    """PIL 'L' 이미지 → 펌웨어 포맷(비트=1 → 검정). 상단 배터리 바 포함."""
    if battery is not None:
        from PIL import ImageDraw
        w = max(4, PANEL_W * battery // 100)
        ImageDraw.Draw(img).rectangle([0, 0, w - 1, BATT_BAR_H - 1], fill=0)
    mono = img.convert("1", dither=Image.Dither.NONE)
    return mono.tobytes().translate(INVERT_TABLE)


def send_frame(base: str, cur: bytes, prev: bytes | None, token: str,
               timeout: float, full: bool) -> bool:
    bands = dirty_bands(None if full else prev, cur)
    for y, h in bands:
        # raw 스트리밍은 전체 프레임도 한 번에, base64 폴백은 ESP32 힙 보호로
        # 120행씩 분할 (미러 브리지와 동일한 규칙; _use_raw 는 전송 중 판정됨)
        max_h = 480 if xb._use_raw else 120
        for cy in range(y, y + h, max_h):
            ch = min(max_h, y + h - cy)
            if not post_band(base, cy, ch, cur[cy * STRIDE:(cy + ch) * STRIDE],
                             token, timeout, full and cy == y == bands[0][0]):
                return False
    return True


def main() -> int:
    args = parse_args()
    font_path = args.font or (__file__.rsplit("/", 1)[0] + "/fonts/D2Coding.ttf")
    renderer = KeymapRenderer(font_path)
    store = ConsoleStore()
    watch = ConsoleWatch()

    snap: Snapshot | None = None
    fp: tuple | None = None
    base = resolve_base(args.x4)
    prev: bytes | None = None
    last_key = None
    last_ok = True
    last_full = time.monotonic()
    last_probe = float("-inf")
    last_fp_check = 0.0
    battery: int | None = None
    page = 0                      # 0=메인, 1=콤보
    btn_base: tuple[int, ...] | None = None
    last_reload_err: str | None = None
    shown_pid: int | None = None  # 프리셋이 바뀌면 메인 페이지로 복귀
    print("x4 tourbox display: start", file=sys.stderr)

    while True:
        now = time.monotonic()

        # 15초마다 X4 상태: 재부팅 감지 + 배터리
        if now - last_probe > 15:
            last_probe = now
            status = x4_status(base, args.post_timeout)
            if status is not None:
                b = status.get("battery")
                if isinstance(b, int):
                    battery = round(b / BATT_STEP) * BATT_STEP
                if prev is not None and status.get("mode") != "bitmap":
                    print("x4 tourbox display: X4 rebooted, full resend", file=sys.stderr)
                    prev = None

        # 1초마다 설정 변경 감지 (편집 실시간 반영)
        if snap is None or now - last_fp_check > 1.0:
            last_fp_check = now
            new_fp = store.fingerprint()
            if new_fp != fp:
                try:
                    snap = store.load()
                    fp = new_fp
                    last_reload_err = None
                    print("x4 tourbox display: config reloaded "
                          f"({len(snap.presets)} presets)", file=sys.stderr)
                except Exception as error:  # Console 이 쓰는 중이면 다음 턴에 재시도
                    msg = str(error)
                    if msg != last_reload_err:  # 같은 오류 반복 출력 방지
                        last_reload_err = msg
                        print(f"x4 tourbox display: reload failed, retrying: {msg}",
                              file=sys.stderr)
                    time.sleep(1.0)
                    continue

        # X4 물리버튼: 위/아래=페이지, 확인=전체 리프레시
        btn = fetch_buttons(base, args.token, 0.5)
        if btn is not None:
            if btn_base is None:
                btn_base = btn
            du, dd, dl, dr, db, dc = (btn[i] - btn_base[i] for i in range(6))
            if any((du, dd, dl, dr, db, dc)):
                btn_base = btn
                if du or dd:
                    page = 1 - page
                if dc or db:
                    prev = None       # 강제 전체 재전송(잔상 제거)

        # 현재 상태 → 프리셋 선택
        state = watch.poll()
        preset = None
        if snap is not None:
            if state.disabled:
                preset = snap.preset_for_process("__Others__")
            elif state.preset_id is not None:
                preset = snap.presets.get(state.preset_id)
            if preset is None and not state.disabled:
                preset = snap.preset_for_process(state.process)

        # 프리셋(또는 없음 상태)이 바뀌면 콤보 페이지에서 메인으로 복귀
        cur_pid = preset.pid if preset else None
        if cur_pid != shown_pid:
            shown_pid = cur_pid
            page = 0

        key = (fp, state.preset_id, state.process, state.disabled, page, battery)
        if key == last_key and prev is not None:
            time.sleep(args.interval)
            continue

        if preset is None:
            img = renderer.render_placeholder(state.process)
        elif page == 1:
            img = renderer.render_combos(preset, state.process, "2/2")
        else:
            img = renderer.render_main(preset, state.process, "1/2")
        cur = to_1bpp(img, battery)

        want_full = prev is None or (
            args.full_every > 0 and now - last_full > args.full_every)
        ok = send_frame(base, cur, prev, args.token, args.post_timeout, want_full)
        if ok:
            prev = cur
            last_key = key
            if want_full:
                last_full = time.monotonic()
        else:
            prev = None
            time.sleep(2.0)               # X4 미응답 백오프
            base = resolve_base(args.x4)  # DHCP 로 IP 변경 대비 재해석
        if ok != last_ok:
            print(f"x4 tourbox display: {'connected' if ok else 'X4 unavailable'}",
                  file=sys.stderr)
            last_ok = ok

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
