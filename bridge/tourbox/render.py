"""TourBox Elite 키맵 → 800x480 e-ink 이미지 렌더러.

스펙 다이어그램 스타일: 중앙에 기기 상면 스키매틱(제품 사진 비례),
좌·우 콜아웃 열에 버튼명+할당 텍스트, 가는 리더선으로 연결.
십자키는 하단 스트립에 4방향 표기. 2페이지는 콤보/더블클릭 목록.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from . import codes
from .store import Preset

PANEL_W, PANEL_H = 800, 480

# 기기 스키매틱 영역
DEV_X0, DEV_Y0, DEV_X1, DEV_Y1 = 250, 72, 560, 400
DEV_W, DEV_H = DEV_X1 - DEV_X0, DEV_Y1 - DEV_Y0

# 컨트롤 위치 (기기 사각형 내 비율 — TourBox Elite 제품 사진 실측 비례)
POS = {
    "scroll": (0.22, 0.15),
    "top":    (0.47, 0.08),
    "c1":     (0.66, 0.13),
    "c2":     (0.78, 0.13),
    "knob":   (0.48, 0.42),
    "tour":   (0.55, 0.64),
    "side":   (0.00, 0.42),
    "dial":   (0.18, 0.74),
    "dpad":   (0.54, 0.84),
    "tall":   (0.80, 0.64),
    "short":  (0.93, 0.58),
}

S = codes.SLOTS  # 가독용 별칭


def _pt(key: str) -> tuple[int, int]:
    fx, fy = POS[key]
    return DEV_X0 + int(fx * DEV_W), DEV_Y0 + int(fy * DEV_H)


class KeymapRenderer:
    def __init__(self, font_path: str):
        # e-ink 가독성: 값 텍스트는 크게 + stroke 1px 로 볼드 (2026-08-12 피드백)
        self.f_head = ImageFont.truetype(font_path, 27)
        self.f_name = ImageFont.truetype(font_path, 15)
        self.f_val = ImageFont.truetype(font_path, 22)
        self.f_val_s = ImageFont.truetype(font_path, 18)
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
        draw.rounded_rectangle([DEV_X0, DEV_Y0, DEV_X1, DEV_Y1],
                               radius=38, outline=0, width=2)
        # scroll: 세로 휠
        x, y = _pt("scroll")
        draw.rounded_rectangle([x - 16, y - 30, x + 16, y + 30],
                               radius=14, outline=0, width=2)
        for dy in (-12, -4, 4, 12):
            draw.line([x - 9, y + dy, x + 9, y + dy], fill=0, width=1)
        # top: 가로 필
        x, y = _pt("top")
        draw.rounded_rectangle([x - 45, y - 14, x + 45, y + 14],
                               radius=13, outline=0, width=2)
        # c1/c2
        for key, lab in (("c1", "C1"), ("c2", "C2")):
            x, y = _pt(key)
            draw.ellipse([x - 13, y - 13, x + 13, y + 13], outline=0, width=2)
            draw.text((x - draw.textlength(lab, font=self.f_small) / 2, y - 7),
                      lab, font=self.f_small, fill=0)
        # knob: 큰 원 + 눈금
        x, y = _pt("knob")
        draw.ellipse([x - 46, y - 46, x + 46, y + 46], outline=0, width=3)
        draw.ellipse([x - 30, y - 30, x + 30, y + 30], outline=0, width=1)
        # tour
        x, y = _pt("tour")
        draw.ellipse([x - 11, y - 11, x + 11, y + 11], outline=0, width=2)
        # side: 왼쪽 엣지 세로 필 (기기 밖으로 반쯤 걸침)
        x, y = _pt("side")
        draw.rounded_rectangle([x - 8, y - 42, x + 8, y + 42],
                               radius=8, outline=0, width=2)
        # dial: 큰 원판
        x, y = _pt("dial")
        draw.ellipse([x - 52, y - 52, x + 52, y + 52], outline=0, width=3)
        draw.ellipse([x - 14, y - 14, x + 14, y + 14], outline=0, width=1)
        # dpad: 십자
        x, y = _pt("dpad")
        a = 15  # 팔 반폭
        r = 40  # 팔 길이
        draw.polygon([
            (x - a, y - r), (x + a, y - r), (x + a, y - a), (x + r, y - a),
            (x + r, y + a), (x + a, y + a), (x + a, y + r), (x - a, y + r),
            (x - a, y + a), (x - r, y + a), (x - r, y - a), (x - a, y - a),
        ], outline=0, width=2)
        # tall / short
        x, y = _pt("tall")
        draw.rounded_rectangle([x - 20, y - 34, x + 20, y + 34],
                               radius=17, outline=0, width=2)
        x, y = _pt("short")
        draw.rounded_rectangle([x - 15, y - 27, x + 15, y + 27],
                               radius=13, outline=0, width=2)

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

        LX0, LX1 = 10, 240   # 좌측 콜아웃 열
        RX0, RX1 = 572, 790  # 우측 콜아웃 열

        # 좌측: TOP, SCROLL, SIDE, DIAL
        tx, ty = _pt("top")
        self._callout(d, LX0, LX1, 48, "TOP",
                      [preset.label(0x02)], (tx - 45, ty), True)
        sx, sy = _pt("scroll")
        self._callout(d, LX0, LX1, 118, "SCROLL",
                      rot(0x09, 0x0A), (sx - 17, sy), True)
        x, y = _pt("side")
        self._callout(d, LX0, LX1, 208, "SIDE",
                      [preset.label(0x01)], (x - 9, y), True)
        x, y = _pt("dial")
        self._callout(d, LX0, LX1, 296, "DIAL",
                      rot(0x0F, 0x38), (x - 53, y), True)

        # 우측: C1, C2, KNOB, SHORT, TALL, TOUR
        x, y = _pt("c1")
        self._callout(d, RX0, RX1, 48, "C1",
                      [preset.label(0x22)], (x + 6, y - 12), False)
        x, y = _pt("c2")
        self._callout(d, RX0, RX1, 98, "C2",
                      [preset.label(0x23)], (x + 12, y + 5), False)
        x, y = _pt("knob")
        self._callout(d, RX0, RX1, 152, "KNOB",
                      rot(0x04, 0x37), (x + 47, y), False)
        x, y = _pt("short")
        self._callout(d, RX0, RX1, 232, "SHORT",
                      [preset.label(0x03)], (x + 16, y), False)
        x, y = _pt("tall")
        self._callout(d, RX0, RX1, 288, "TALL",
                      [preset.label(0x00)], (x + 12, y + 20), False)
        x, y = _pt("tour")
        self._callout(d, RX0, RX1, 344, "TOUR",
                      [preset.label(0x2A)], (x + 11, y), False)

        # 하단 스트립: 십자키 (2x2 그리드 — 긴 설명 대비)
        d.line([0, 418, PANEL_W, 418], fill=0, width=1)
        dx, dy = _pt("dpad")
        d.line([dx, dy + 42, dx, 418], fill=0, width=1)
        d.text((12, 424), "십자키", font=self.f_name, fill=0)
        cell = (PANEL_W - 70) // 2
        for i, slot in enumerate((0x10, 0x11, 0x12, 0x13)):
            label = preset.label(slot) or "–"
            col, row = i % 2, i // 2
            x0 = 70 + col * cell
            y0 = 420 + row * 30
            d.text((x0, y0 + 3), S[slot], font=self.f_val, fill=0)
            font, txt = self._fit(d, label, cell - 44)
            self._bold(d, (x0 + 30, y0 + 3), txt, font)
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
