"""TourBox Console 런타임 상태 추적 (tourbox.log tail).

Console 은 앱 전환·프리셋 전환 때마다 tourbox.log 에 기록한다:
  "switchPreset =========> currentPresetId=2, tabId=2"   → 활성 프리셋
  "Now Process name is:Adobe Illustrator"                → 전면 앱
  "Not found match preset,disable Tourbox"               → 매칭 프리셋 없음

로그가 지워지거나(재설치) 파일이 새로 생겨도 견디도록 inode/크기 변화를
감지해 재오픈한다. 부분 줄은 내부 버퍼에 모았다가 개행이 오면 처리한다.
초기 프리셋은 tableid 파일에서 가져온다.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .store import CONSOLE_DIR

_RE_SWITCH = re.compile(r"switchPreset =+> currentPresetId=(\d+)")
_RE_PROCESS = re.compile(r"Now Process name is:(.*)")
_RE_CHANGE = re.compile(r"Change process name=(.*)")
_RE_DISABLE = re.compile(r"Not found match preset,disable Tourbox")


@dataclass
class ConsoleState:
    preset_id: int | None = None
    process: str | None = None        # 전면 앱 표시 이름
    match_process: str | None = None  # 매칭에 쓰인 이름 (__Others__ 가능)
    disabled: bool = False            # 전면 앱에 매칭 프리셋 없음


class ConsoleWatch:
    def __init__(self, base: Path = CONSOLE_DIR):
        self.log_path = Path(base) / "tourbox.log"
        self.state = ConsoleState()
        self._fh = None
        self._ino = None
        self._pending = b""
        try:
            self.state.preset_id = int((Path(base) / "tableid").read_text().strip())
        except (OSError, ValueError):
            pass
        self._open(seek_end=True)

    def _open(self, seek_end: bool) -> None:
        self._pending = b""
        try:
            fh = open(self.log_path, "rb")
        except OSError:
            self._fh = None
            return
        self._fh = fh
        self._ino = os.fstat(fh.fileno()).st_ino
        if seek_end:
            fh.seek(0, os.SEEK_END)

    def _handle(self, line: str) -> None:
        # 주의: 미매칭 앱 전환 시 Console 은 "disable Tourbox" 뒤에
        # "switchPreset currentPresetId=N"(UI 탭 상태)을 또 남긴다.
        # 따라서 switchPreset 은 disabled 를 해제하지 않는다 — 해제는
        # "Change process name=실제앱" (매칭 성공) 시점에만 한다.
        m = _RE_SWITCH.search(line)
        if m:
            self.state.preset_id = int(m.group(1))
            return
        m = _RE_PROCESS.search(line)
        if m:
            self.state.process = m.group(1).strip()
            return
        m = _RE_CHANGE.search(line)
        if m:
            # 매칭 결과가 확정되는 지점 — disabled 는 여기서 리셋하고,
            # 매칭 실패면 바로 다음 "disable Tourbox" 줄이 다시 True 로 만든다.
            # (__Others__ 에 프리셋을 매핑해 두면 disable 줄이 안 나오므로
            #  일반 프리셋이 그대로 표시된다.)
            self.state.match_process = m.group(1).strip()
            self.state.disabled = False
            return
        if _RE_DISABLE.search(line):
            self.state.disabled = True

    def poll(self) -> ConsoleState:
        """새 로그 바이트를 소화하고 최신 상태를 돌려준다."""
        if self._fh is None:
            self._open(seek_end=False)
            if self._fh is None:
                return self.state
        try:
            st = os.stat(self.log_path)
            if st.st_ino != self._ino or st.st_size < self._fh.tell():
                self._fh.close()
                self._open(seek_end=False)      # 새/축소된 파일은 처음부터
                if self._fh is None:
                    return self.state
            chunk = self._fh.read()
        except OSError:
            return self.state

        if not chunk:
            return self.state
        buf = self._pending + chunk
        lines = buf.split(b"\n")
        self._pending = lines.pop()             # 개행 없는 마지막 조각은 보류
        for raw in lines:
            self._handle(raw.decode("utf-8", errors="replace"))
        return self.state
