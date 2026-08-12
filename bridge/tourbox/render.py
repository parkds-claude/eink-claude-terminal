"""TourBox Elite 키맵 → 800x480 e-ink 이미지 렌더러.

스펙 다이어그램 스타일: 중앙에 기기 상면 스키매틱(제품 사진 비례),
좌·우 콜아웃 열에 버튼명+할당 텍스트, 가는 리더선으로 연결.
십자키는 하단 스트립에 4방향 표기. 2페이지는 콤보/더블클릭 목록.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

from . import codes
from .store import Preset

PANEL_W, PANEL_H = 800, 480

# 기기 스키매틱 영역 — 실물 비례(가로>세로)에 맞춘 와이드 배치 (2026-08-12)
DEV_X0, DEV_Y0, DEV_X1, DEV_Y1 = 210, 78, 590, 446
DEV_W, DEV_H = DEV_X1 - DEV_X0, DEV_Y1 - DEV_Y0

# 컨트롤 위치 (기기 영역 내 비율 — TourBox 공식 일러스트 비례)
POS = {
    "scroll": (0.20, 0.28),
    "top":    (0.48, 0.17),
    "c1":     (0.66, 0.31),
    "c2":     (0.77, 0.31),
    "knob":   (0.50, 0.45),
    "tour":   (0.37, 0.58),
    "side":   (0.03, 0.28),
    "dial":   (0.22, 0.74),
    "dpad":   (0.55, 0.75),
    "tall":   (0.77, 0.70),
    "short":  (0.90, 0.75),
}

# 유기적 외곽선 앵커 (기기 영역 비율 — 은은한 물결의 둥근 사각 실루엣)
_OUTLINE = [
    (0.10, 0.10), (0.30, 0.06), (0.52, 0.08), (0.75, 0.05), (0.93, 0.09),
    (0.98, 0.30), (0.96, 0.55), (0.98, 0.82), (0.92, 0.95), (0.70, 0.93),
    (0.45, 0.96), (0.20, 0.94), (0.05, 0.88), (0.04, 0.60), (0.03, 0.30),
]


def _catmull_rom(pts: list[tuple[float, float]], steps: int = 12):
    """닫힌 Catmull-Rom 스플라인 보간점 목록."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (pts[(i + k - 1) % n] for k in range(4))
        for t in (j / steps for j in range(steps)):
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
            ))
    return out

S = codes.SLOTS  # 가독용 별칭


def _pt(key: str) -> tuple[int, int]:
    fx, fy = POS[key]
    return DEV_X0 + int(fx * DEV_W), DEV_Y0 + int(fy * DEV_H)


class KeymapRenderer:
    def __init__(self, font_path: str):
        # e-ink 가독성: 값 텍스트는 크게 + stroke 1px 로 볼드 (2026-08-12 피드백)
        self.f_head = ImageFont.truetype(font_path, 28)
        self.f_name = ImageFont.truetype(font_path, 16)
        self.f_val = ImageFont.truetype(font_path, 24)
        self.f_val_s = ImageFont.truetype(font_path, 19)
        self.f_small = ImageFont.truetype(font_path, 14)

    # ------------------------------------------------------------------ util
    @staticmethod
    def _bold(draw, xy, text, font):
        draw.text(xy, text, font=font, fill=0, stroke_width=1, stroke_fill=0)

    def _fit(self, draw: ImageDraw.ImageDraw, text: str, max_w: int):
        """폭에 맞는 (폰트, 텍스트) — 큰 폰트 → 작은 폰트 → 말줄임.
        stroke 1px 여유로 2px 마진을 둔다."""
        max_w -= 2
        for font in (self.f_val, self.f_val_s):
            if draw.textlength(text, font=font) <= max_w:
                return font, text
        font = self.f_val_s
        while text and draw.textlength(text + "…", font=font) > max_w:
            text = text[:-1]
        return font, (text + "…" if text else "")

    def _callout(self, draw, x0: int, x1: int, y: int, name: str,
                 lines: list[str], target: tuple[int, int], align_right: bool):
        """콜아웃 한 개: 버튼명 + 값 텍스트(1~2줄) + 리더선."""
        lines = [ln for ln in lines if ln] or ["–"]
        max_w = x1 - x0
        draw.text((x1 - draw.textlength(name, font=self.f_name) if align_right
                   else x0, y), name, font=self.f_name, fill=0)
        ty = y + 18
        for ln in lines[:2]:
            font, txt = self._fit(draw, ln, max_w)
            tw = draw.textlength(txt, font=font)
            self._bold(draw, (x1 - tw if align_right else x0, ty), txt, font)
            ty += font.size + 4
        # 리더선: 콜아웃 모서리 → 컨트롤
        ly = y + 20
        lx = x1 + 3 if align_right else x0 - 3
        draw.line([lx, ly, target[0], target[1]], fill=0, width=1)
        draw.ellipse([target[0] - 2, target[1] - 2,
                      target[0] + 2, target[1] + 2], fill=0)

    # ------------------------------------------------------------- schematic
    def _draw_device(self, draw):
        # 유기적 외곽 실루엣 (공식 일러스트의 물결 라인)
        pts = [(DEV_X0 + fx * DEV_W, DEV_Y0 + fy * DEV_H)
               for fx, fy in _catmull_rom(_OUTLINE)]
        draw.line(pts + [pts[0]], fill=0, width=2, joint="curve")

        # side: 왼쪽 엣지 밖으로 돌출한 탭
        x, y = _pt("side")
        draw.rounded_rectangle([x - 5, y - 30, x + 6, y + 30],
                               radius=4, outline=0, width=2)

        # scroll: 달걀형 하우징 + 내부 휠 + 리지 3개
        x, y = _pt("scroll")
        draw.ellipse([x - 34, y - 62, x + 34, y + 62], outline=0, width=2)
        draw.rounded_rectangle([x - 18, y - 44, x + 18, y + 44],
                               radius=17, outline=0, width=2)
        for dy in (-18, 0, 18):
            draw.rounded_rectangle([x - 9, y + dy - 3, x + 9, y + dy + 3],
                                   radius=3, outline=0, width=1)

        # top: 가로 필 (이중 라인)
        x, y = _pt("top")
        draw.rounded_rectangle([x - 58, y - 18, x + 58, y + 18],
                               radius=17, outline=0, width=2)
        draw.rounded_rectangle([x - 51, y - 11, x + 51, y + 11],
                               radius=11, outline=0, width=1)

        # 로고
        lx, ly = DEV_X0 + int(0.70 * DEV_W), DEV_Y0 + int(0.11 * DEV_H)
        draw.text((lx, ly), "tour", font=self.f_small, fill=0)
        draw.text((lx + 5, ly + 13), "box", font=self.f_small, fill=0)

        # c1/c2: 원
        for key, lab in (("c1", "C1"), ("c2", "C2")):
            x, y = _pt(key)
            draw.ellipse([x - 15, y - 15, x + 15, y + 15], outline=0, width=2)
            draw.text((x - draw.textlength(lab, font=self.f_small) / 2, y - 8),
                      lab, font=self.f_small, fill=0)

        # knob: 스캘럽 엣지 + 골마다 방사선
        x, y = _pt("knob")
        R = 50
        knob_pts = []
        for i in range(144):
            th = i * 2 * math.pi / 144
            r = R * (1 + 0.055 * math.cos(12 * th))
            knob_pts.append((x + r * math.cos(th), y + r * math.sin(th)))
        draw.line(knob_pts + [knob_pts[0]], fill=0, width=2, joint="curve")
        for i in range(12):
            th = (2 * i + 1) * math.pi / 12
            draw.line([x + 0.30 * R * math.cos(th), y + 0.30 * R * math.sin(th),
                       x + 0.82 * R * math.cos(th), y + 0.82 * R * math.sin(th)],
                      fill=0, width=1)

        # tour: 노브 좌하단의 작은 콩 모양
        x, y = _pt("tour")
        draw.ellipse([x - 15, y - 12, x + 15, y + 12], outline=0, width=2)

        # dial: 방사 스포크 원판
        x, y = _pt("dial")
        R = 58
        draw.ellipse([x - R, y - R, x + R, y + R], outline=0, width=2)
        for i in range(18):
            th = i * math.pi / 9
            draw.line([x + 10 * math.cos(th), y + 10 * math.sin(th),
                       x + (R - 5) * math.cos(th), y + (R - 5) * math.sin(th)],
                      fill=0, width=1)
        draw.ellipse([x - 9, y - 9, x + 9, y + 9], outline=0, width=1, fill=255)

        # dpad: 분리형 키 4개 + 중앙 다이아몬드
        x, y = _pt("dpad")
        o, kl, ks = 32, 17, 13   # 키 중심 오프셋, 키 반변(긴/짧은)
        for dx, dy, vert in ((0, -o, True), (0, o, True),
                             (-o, 0, False), (o, 0, False)):
            hw, hh = (ks, kl) if vert else (kl, ks)
            draw.rounded_rectangle([x + dx - hw, y + dy - hh,
                                    x + dx + hw, y + dy + hh],
                                   radius=6, outline=0, width=2)
        draw.polygon([(x, y - 7), (x + 7, y), (x, y + 7), (x - 7, y)],
                     outline=0, width=1)

        # tall: 세로 필 + 리지 3줄 / short: 돔
        x, y = _pt("tall")
        draw.rounded_rectangle([x - 21, y - 42, x + 21, y + 42],
                               radius=20, outline=0, width=2)
        for dy in (-13, 0, 13):
            draw.line([x - 9, y + dy, x + 9, y + dy], fill=0, width=1)
        x, y = _pt("short")
        try:
            draw.rounded_rectangle([x - 16, y - 32, x + 16, y + 32], radius=15,
                                   corners=(True, True, False, False),
                                   outline=0, width=2)
            draw.line([x - 16, y + 32, x + 16, y + 32], fill=0, width=2)
        except TypeError:  # Pillow < 9.1
            draw.rounded_rectangle([x - 16, y - 32, x + 16, y + 32],
                                   radius=15, outline=0, width=2)

    # ------------------------------------------------------------ main page
    def render_main(self, preset: Preset, process: str | None,
                    page_hint: str = "") -> Image.Image:
        img = Image.new("L", (PANEL_W, PANEL_H), 255)
        d = ImageDraw.Draw(img)

        # 헤더
        self._bold(d, (12, 6), preset.name, self.f_head)
        right = (process or "").strip()
        if page_hint:
            right = f"{right}   {page_hint}" if right else page_hint
        if right:
            d.text((PANEL_W - 12 - d.textlength(right, font=self.f_small), 16),
                   right, font=self.f_small, fill=0)
        d.line([0, 40, PANEL_W, 40], fill=0, width=1)

        self._draw_device(d)

        def rot(turn_slot: int, press_slot: int) -> list[str]:
            lines = []
            t = preset.label(turn_slot)
            if t:
                lines.append(t)
            p = preset.label(press_slot)
            if p:
                lines.append(f"누름 {p}")
            return lines

        LX0, LX1 = 8, 202    # 좌측 콜아웃 열
        RX0, RX1 = 598, 792  # 우측 콜아웃 열

        # 좌측: TOP, SIDE, SCROLL, TOUR, DIAL (물리 위치 순)
        tx, ty = _pt("top")
        self._callout(d, LX0, LX1, 60, "TOP",
                      [preset.label(0x02)], (tx - 52, ty), True)
        x, y = _pt("side")
        self._callout(d, LX0, LX1, 122, "SIDE",
                      [preset.label(0x01)], (x - 6, y), True)
        sx, sy = _pt("scroll")
        self._callout(d, LX0, LX1, 186, "SCROLL",
                      rot(0x09, 0x0A), (sx - 34, sy), True)
        x, y = _pt("tour")
        self._callout(d, LX0, LX1, 292, "TOUR",
                      [preset.label(0x2A)], (x - 13, y - 8), True)
        x, y = _pt("dial")
        self._callout(d, LX0, LX1, 358, "DIAL",
                      rot(0x0F, 0x38), (x - 59, y), True)

        # 우측: C1, C2, KNOB, TALL, SHORT (물리 위치 순)
        x, y = _pt("c1")
        self._callout(d, RX0, RX1, 60, "C1",
                      [preset.label(0x22)], (x + 3, y - 14), False)
        x, y = _pt("c2")
        self._callout(d, RX0, RX1, 120, "C2",
                      [preset.label(0x23)], (x + 12, y - 9), False)
        x, y = _pt("knob")
        self._callout(d, RX0, RX1, 190, "KNOB",
                      rot(0x04, 0x37), (x + 52, y), False)
        x, y = _pt("tall")
        self._callout(d, RX0, RX1, 296, "TALL",
                      [preset.label(0x00)], (x + 22, y), False)
        x, y = _pt("short")
        self._callout(d, RX0, RX1, 360, "SHORT",
                      [preset.label(0x03)], (x + 18, y), False)
        return img

    # ----------------------------------------------------------- combo page
    def render_combos(self, preset: Preset, process: str | None,
                      page_hint: str = "") -> Image.Image:
        img = Image.new("L", (PANEL_W, PANEL_H), 255)
        d = ImageDraw.Draw(img)
        self._bold(d, (12, 6), f"{preset.name} — 콤보·더블클릭", self.f_head)
        if page_hint:
            d.text((PANEL_W - 12 - d.textlength(page_hint, font=self.f_small), 16),
                   page_hint, font=self.f_small, fill=0)
        d.line([0, 40, PANEL_W, 40], fill=0, width=1)

        rows = []
        for slot in codes.COMBO_ORDER:
            label = preset.label(slot)
            if label:
                rows.append((S.get(slot, f"0x{slot:02X}"), label))
        if not rows:
            d.text((280, 220), "콤보 할당 없음", font=self.f_head, fill=0)
            return img

        col_w = PANEL_W // 2
        name_w = 132
        row_h = 32
        per_col = (PANEL_H - 56) // row_h
        for i, (name, label) in enumerate(rows[:per_col * 2]):
            col, row = divmod(i, per_col)
            x0 = 12 + col * col_w
            y0 = 50 + row * row_h
            d.text((x0, y0 + 6), name, font=self.f_name, fill=0)
            font, txt = self._fit(d, label, col_w - name_w - 26)
            self._bold(d, (x0 + name_w, y0 + 2), txt, font)
        if len(rows) > per_col * 2:
            d.text((PANEL_W - 130, PANEL_H - 22),
                   f"+{len(rows) - per_col * 2}건 더", font=self.f_small, fill=0)
        return img

    # ----------------------------------------------------------- placeholder
    def render_placeholder(self, process: str | None) -> Image.Image:
        img = Image.new("L", (PANEL_W, PANEL_H), 255)
        d = ImageDraw.Draw(img)
        title = process or "알 수 없는 앱"
        self._bold(d, ((PANEL_W - d.textlength(title, font=self.f_head)) / 2, 185),
                   title, self.f_head)
        msg = "TourBox 프리셋 없음"
        d.text(((PANEL_W - d.textlength(msg, font=self.f_val)) / 2, 240),
               msg, font=self.f_val, fill=0)
        return img
