#!/usr/bin/env python3
"""tmux 화면을 한글 폰트로 1bpp 렌더링해 X4 e-ink로 미러하는 브리지.

xteink-terminal의 텍스트 브리지(v1)를 대체한다. 텍스트를 ASCII로 뭉개는 대신
D2Coding(고정폭, 한글=영문 2배폭)으로 800x480 비트맵을 그려 변경 밴드만
POST /band 로 전송한다. 한글·박스문자·특수문자가 원형 그대로 표시된다.
"""

from __future__ import annotations

import argparse
import base64
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request

from PIL import Image, ImageDraw, ImageFont

PANEL_W = 800
PANEL_H = 480
STRIDE = PANEL_W // 8
BAND_GAP_MERGE = 16  # 이 간격(px) 이하로 떨어진 변경 행은 한 밴드로 합침
INVERT_TABLE = bytes(b ^ 0xFF for b in range(256))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x4", required=True, help="X4 base URL, e.g. http://192.168.0.5")
    parser.add_argument("--target", default="x4-terminal:", help="tmux target")
    parser.add_argument("--font", default=None, help="TTF path (default: bundled D2Coding)")
    parser.add_argument("--font-size", type=int, default=16, help="font pixel size (16=100x26, 20=80x21)")
    parser.add_argument("--interval", type=float, default=0.12, help="poll seconds")
    parser.add_argument("--post-timeout", type=float, default=12.0,
                        help="전체갱신(1.7s)+디코드보다 길게 — 중복 연결로 인한 힙 압박 방지")
    parser.add_argument("--token", default="", help="X-Auth shared secret")
    parser.add_argument("--full-every", type=float, default=300.0,
                        help="잔상 방지용 전체갱신 최소 주기(초), 0=비활성")
    return parser.parse_args()


def cell_width(ch: str) -> int:
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def wrap_cells(line: str, cols: int) -> list[str]:
    """셀 폭 기준 줄바꿈 (한글 2셀)."""
    line = line.replace("\r", "").replace("\t", "    ")
    line = "".join(ch for ch in line if ch == " " or not unicodedata.category(ch).startswith("C"))
    if not line:
        return [""]
    out: list[str] = []
    cur, width = "", 0
    for ch in line:
        w = cell_width(ch)
        if width + w > cols:
            out.append(cur)
            cur, width = ch, w
        else:
            cur += ch
            width += w
    out.append(cur)
    return out


class Renderer:
    def __init__(self, font_path: str, font_size: int):
        self.font = ImageFont.truetype(font_path, font_size)
        ascent, descent = self.font.getmetrics()
        self.adv = int(self.font.getlength("A"))
        self.line_h = ascent + descent
        self.cols = PANEL_W // self.adv
        self.rows = PANEL_H // self.line_h
        self.mx = (PANEL_W - self.cols * self.adv) // 2
        self.my = (PANEL_H - self.rows * self.line_h) // 2

    def render(self, lines: list[str], cursor: tuple[int, int]) -> bytes:
        img = Image.new("L", (PANEL_W, PANEL_H), 255)
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(lines[: self.rows]):
            if line:
                draw.text((self.mx, self.my + i * self.line_h), line, font=self.font, fill=0)
        cx, cy = cursor
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            x = self.mx + cx * self.adv
            y = self.my + cy * self.line_h
            draw.rectangle([x, y, x + self.adv - 1, y + self.line_h - 1], outline=0)
        mono = img.convert("1", dither=Image.Dither.NONE)
        raw = mono.tobytes()  # bit=1 → 흰색
        return raw.translate(INVERT_TABLE)  # 펌웨어는 bit=1 → 검정


def run_tmux(args: list[str]) -> str:
    result = subprocess.run(["tmux", *args], check=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout


def capture(target: str, cols: int, rows: int) -> list[str]:
    # window-size manual + resize-window: 큰 화면의 클라이언트가 attach해도
    # 세션 크기는 X4 셀 수로 고정 (클라이언트 쪽에는 여백으로 표시됨)
    subprocess.run(["tmux", "set-option", "-t", target, "window-size", "manual"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["tmux", "resize-window", "-t", target, "-x", str(cols), "-y", str(rows)],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    output = run_tmux(["capture-pane", "-p", "-t", target, "-S", f"-{rows}", "-E", "-"])
    wrapped: list[str] = []
    for line in output.splitlines():
        wrapped.extend(wrap_cells(line, cols))
    if len(wrapped) < rows:
        wrapped = [""] * (rows - len(wrapped)) + wrapped
    return wrapped[-rows:]


def cursor_pos(target: str) -> tuple[int, int]:
    try:
        out = run_tmux(["display-message", "-p", "-t", target, "#{cursor_x} #{cursor_y}"])
        x, y = out.strip().split()
        return int(x), int(y)
    except Exception:
        return 0, 0


def post_band(base: str, y: int, h: int, data: bytes, token: str,
              timeout: float, full: bool) -> bool:
    url = f"{base.rstrip('/')}/band?y={y}&h={h}" + ("&full=1" if full else "")
    headers = {"Content-Type": "text/plain"}
    if token:
        headers["X-Auth"] = token
    req = urllib.request.Request(url, data=base64.b64encode(data), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def x4_in_bitmap_mode(base: str, timeout: float) -> bool | None:
    """X4가 비트맵 모드인지 확인. 통신 실패 시 None."""
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/status", timeout=timeout) as resp:
            import json
            return json.load(resp).get("mode") == "bitmap"
    except (OSError, urllib.error.URLError, ValueError, TimeoutError):
        return None


def dirty_bands(prev: bytes | None, cur: bytes) -> list[tuple[int, int]]:
    if prev is None:
        return [(0, PANEL_H)]
    changed = [prev[i * STRIDE:(i + 1) * STRIDE] != cur[i * STRIDE:(i + 1) * STRIDE]
               for i in range(PANEL_H)]
    bands: list[tuple[int, int]] = []
    start = None
    last = None
    for row, ch in enumerate(changed):
        if not ch:
            continue
        if start is None:
            start, last = row, row
        elif row - last <= BAND_GAP_MERGE:
            last = row
        else:
            bands.append((start, last - start + 1))
            start, last = row, row
    if start is not None:
        bands.append((start, last - start + 1))
    return bands


def main() -> int:
    args = parse_args()
    font_path = args.font or (__file__.rsplit("/", 1)[0] + "/fonts/D2Coding.ttf")
    r = Renderer(font_path, args.font_size)
    print(f"x4 bitmap bridge: {r.cols}x{r.rows} cells "
          f"(cell {r.adv}x{r.line_h}px, font {args.font_size}px)", file=sys.stderr)

    prev: bytes | None = None
    last_ok = True
    last_full = time.monotonic()
    last_probe = time.monotonic()
    last_key = None
    while True:
        # X4 재부팅 감지: 15초마다 상태 확인, 비트맵 모드가 아니면 전체 재전송
        if prev is not None and time.monotonic() - last_probe > 15:
            last_probe = time.monotonic()
            if x4_in_bitmap_mode(args.x4, args.post_timeout) is False:
                print("x4 bitmap bridge: X4 rebooted, resending full frame", file=sys.stderr)
                prev = None
        try:
            lines = capture(args.target, r.cols, r.rows)
            cpos = cursor_pos(args.target)
            key = (tuple(lines), cpos)
            if prev is not None and key == last_key:
                time.sleep(args.interval)
                continue
            last_key = key
            cur = r.render(lines, cpos)
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            print(f"x4 bitmap bridge: {error}", file=sys.stderr)
            time.sleep(1.0)
            continue

        ok = True
        want_full = prev is None or (
            args.full_every > 0 and time.monotonic() - last_full > args.full_every)
        bands = dirty_bands(None if want_full else prev, cur)
        MAX_H = 120  # ESP32 힙 보호: 밴드당 최대 120행(base64 20KB) — 크래시 예방
        for y, h in bands:
            full = want_full
            for cy in range(y, y + h, MAX_H):
                ch = min(MAX_H, y + h - cy)
                if not post_band(args.x4, cy, ch, cur[cy * STRIDE:(cy + ch) * STRIDE],
                                 args.token, args.post_timeout, full and cy == y):
                    ok = False
                    break
            if not ok:
                break
        if bands:
            if ok:
                prev = cur
                if want_full:
                    last_full = time.monotonic()
            else:
                prev = None  # X4 복귀 시 전체 프레임 재전송
                time.sleep(2.0)  # 백오프: 갱신 중인 X4를 연타하지 않는다
            if ok != last_ok:
                print(f"x4 bitmap bridge: {'connected' if ok else 'X4 unavailable'}",
                      file=sys.stderr)
                last_ok = ok

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
