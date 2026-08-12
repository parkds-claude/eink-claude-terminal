"""tourbox 패키지 자체 검증 (외부 의존 없이 unittest 로 실행).

    cd bridge && python3 -m tourbox.selftest

1부: 순수 단위 테스트 (합성 데이터)
2부: 라이브 검증 — TourBox Console 디렉터리가 있으면 실제 설정을 파싱해
     알려진 불변식(공식 Illustrator 프리셋의 Undo 등)을 확인한다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from . import codes
from .store import (CONSOLE_DIR, Action, ConsoleStore, Preset, Sub,
                    decode_payload)
from .render import KeymapRenderer, PANEL_W, PANEL_H

FONT = str(Path(__file__).resolve().parent.parent / "fonts" / "D2Coding.ttf")


class DecodeTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(decode_payload(bytes(12)).kind, "none")

    def test_empty_with_type_flag(self):
        # 회전 슬롯의 빈 상태: type 바이트만 남음 → none
        self.assertEqual(decode_payload(bytes([8] + [0] * 11)).kind, "none")

    def test_single_key(self):
        act = decode_payload(bytes([0, 0, 0, 0, 0, 0, ord("V"), 0, 0, 0, 0, 0]))
        self.assertEqual(act.kind, "key")
        self.assertEqual(act.label({}), "V")

    def test_modifier_combo(self):
        act = decode_payload(bytes([0, 0, 0x08, 0, 0, 0, ord("Z"), 0, 0, 0, 0, 0]))
        self.assertEqual(act.label({}), "⌘Z")
        self.assertEqual(act.label({(8, 90): "실행 취소"}), "실행 취소")

    def test_modifier_only(self):
        act = decode_payload(bytes([0, 0, 0x02, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
        self.assertEqual(act.label({}), "⇧")

    def test_dual_rotary(self):
        act = decode_payload(bytes([6, 0, 0x08, 0, 0, 0, ord("-"),
                                    0x08, 0, 0, 0, ord("+")]))
        self.assertEqual(act.kind, "dual")
        self.assertEqual(act.label({}), "⌘- / ⌘+")

    def test_extended_key_swt_join(self):
        # 확장키 F7(=코드 16) ↔ ShortDesc SWT 16777232
        act = decode_payload(bytes([0, 0, 0, 1, 0, 0, 16, 0, 0, 0, 0, 0]))
        self.assertEqual(act.label({}), "F7")
        self.assertEqual(act.label({(0, 16777232): "레이어 패널"}), "레이어 패널")

    def test_arrows(self):
        act = decode_payload(bytes([6, 0, 0, 1, 0, 0, 2, 0, 1, 0, 0, 1]))
        self.assertEqual(act.label({}), "↓ / ↑")

    def test_mouse(self):
        act = decode_payload(bytes([0, 0, 0, 2, 0, 0, 4, 0, 0, 0, 0, 0]))
        self.assertEqual(act.label({}), "휠↑")

    def test_builtin(self):
        act = decode_payload(bytes([0, 4, 0x05, 0x7E, 0, 0, 0, 0, 0, 0, 0, 0]))
        self.assertEqual(act.kind, "builtin")
        self.assertEqual(act.ref_id, 0x057E)

    def test_unknown_never_raises(self):
        for pattern in (bytes([0, 9] + [7] * 10), bytes(range(12))):
            act = decode_payload(pattern)
            self.assertIsInstance(act.label({}), str)


class CodesTests(unittest.TestCase):
    def test_slot_names_unique_primary(self):
        self.assertTrue(codes.PRIMARY <= set(codes.SLOTS))

    def test_combo_order_subset(self):
        for slot in codes.COMBO_ORDER:
            self.assertIn(slot, codes.SLOTS)
            self.assertNotIn(slot, codes.PRIMARY)

    def test_mods_order(self):
        self.assertEqual(codes.mods_label(0x0F), "⌃⌥⇧⌘")

    def test_swt_mapping(self):
        self.assertEqual(codes.swt_code(0, 90), 90)
        self.assertEqual(codes.swt_code(1, 16), 0x1000010)
        self.assertIsNone(codes.swt_code(2, 1))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.r = KeymapRenderer(FONT)
        self.preset = Preset(pid=0, name="TestPreset")
        self.preset.bindings[0x02] = Action("key", a=Sub(0, 0, ord("V")))
        self.preset.bindings[0x04] = Action(
            "dual", a=Sub(8, 0, ord("-")), b=Sub(8, 0, ord("+")))
        self.preset.bindings[0x21] = Action("key", a=Sub(8, 0, ord("Z")))

    def test_main_size(self):
        img = self.r.render_main(self.preset, "TestApp", "1/2")
        self.assertEqual(img.size, (PANEL_W, PANEL_H))

    def test_combo_size(self):
        img = self.r.render_combos(self.preset, "TestApp", "2/2")
        self.assertEqual(img.size, (PANEL_W, PANEL_H))

    def test_placeholder(self):
        img = self.r.render_placeholder(None)
        self.assertEqual(img.size, (PANEL_W, PANEL_H))

    def test_long_label_fits(self):
        self.preset.descs[(0, ord("V"))] = "아주 긴 설명 텍스트가 잘리는지 확인하는 라벨" * 3
        img = self.r.render_main(self.preset, "TestApp")
        self.assertEqual(img.size, (PANEL_W, PANEL_H))

    def test_1bpp_convertible(self):
        img = self.r.render_main(self.preset, None)
        raw = img.convert("1", dither=None).tobytes()
        self.assertEqual(len(raw), PANEL_W * PANEL_H // 8)


class WatchTests(unittest.TestCase):
    def test_tail_lifecycle(self):
        import tempfile
        from .watch import ConsoleWatch
        tmp = Path(tempfile.mkdtemp())
        (tmp / "tableid").write_text("2")
        log = tmp / "tourbox.log"
        log.write_text("boot\n")
        w = ConsoleWatch(tmp)
        self.assertEqual(w.poll().preset_id, 2)          # 초기값 = tableid
        with log.open("a") as f:
            f.write("x - Now Process name is:Adobe Illustrator\n")
            f.write("x - Change process name=Adobe Illustrator\n")
            f.write("x - switchPreset =========> currentPresetId=1, tabId=1\n")
        s = w.poll()
        self.assertEqual((s.preset_id, s.process, s.disabled),
                         (1, "Adobe Illustrator", False))
        # 미매칭 앱 전환 — Console 실제 순서: disable 뒤에 switchPreset 이
        # 또 찍힌다. disabled 가 유지되어야 한다 (2026-08-12 버그 수정 검증).
        with log.open("a") as f:
            f.write("x - Now Process name is:Google Chrome\n")
            f.write("x - Change process name=__Others__\n")
            f.write("x - Not found match preset,disable Tourbox\n")
            f.write("x - switchPreset =========> currentPresetId=1, tabId=1\n")
        s = w.poll()
        self.assertEqual((s.process, s.disabled), ("Google Chrome", True))
        # 매칭 앱으로 복귀 → 해제
        with log.open("a") as f:                          # 부분 줄 내성 포함
            f.write("x - Change process name=Adobe Photoshop\n")
            f.write("x - switchPreset =========> currentPre")
        self.assertTrue(w.poll().disabled is False)
        self.assertEqual(w.state.preset_id, 1)            # 부분 줄은 아직 미적용
        with log.open("a") as f:
            f.write("setId=0, tabId=0\n")
        s = w.poll()
        self.assertEqual((s.preset_id, s.disabled), (0, False))
        log.write_text(                                   # truncate 내성
            "x - switchPreset =========> currentPresetId=2, tabId=2\n")
        self.assertEqual(w.poll().preset_id, 2)


@unittest.skipUnless(CONSOLE_DIR.exists(), "TourBox Console 미설치")
class LiveConsoleTests(unittest.TestCase):
    """실제 설치본 검증 — 사용자 프리셋의 알려진 값이 올바로 해석되는가."""

    @classmethod
    def setUpClass(cls):
        cls.snap = ConsoleStore().load()

    def test_presets_parsed(self):
        self.assertGreaterEqual(len(self.snap.presets), 1)
        for p in self.snap.presets.values():
            self.assertTrue(p.name)
            self.assertGreater(len(p.bindings), 0)

    def test_process_map(self):
        for name, pid in self.snap.process_map.items():
            self.assertIn(pid, self.snap.presets)

    def test_illustrator_invariants(self):
        """공식 Illustrator 프리셋이 있으면 알려진 바인딩 확인."""
        ai = next((p for p in self.snap.presets.values()
                   if p.name == "Illustrator"), None)
        if ai is None:
            self.skipTest("Illustrator 프리셋 없음")
        self.assertEqual(ai.label(0x00), "Space")          # TALL = 손바닥 이동
        self.assertIn("Zoom", ai.label(0x04))              # KNOB = 확대/축소
        self.assertEqual(ai.label(0x21), "Undo")           # SIDE 더블 = 실행취소

    def test_all_presets_render(self):
        r = KeymapRenderer(FONT)
        for p in self.snap.presets.values():
            for img in (r.render_main(p, "앱"), r.render_combos(p, "앱")):
                self.assertEqual(img.size, (PANEL_W, PANEL_H))

    def test_labels_never_raise(self):
        for p in self.snap.presets.values():
            for slot in p.bindings:
                self.assertIsInstance(p.label(slot), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
