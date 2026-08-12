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
        self.tableid_path = Path(base) / "tableid"
        self.state = ConsoleState()
        self._fh = None
        self._ino = None
        self._pending = b""
        self._tableid_mtime = self._read_tableid(initial=True)
        self._open(seek_end=True)

    def _read_tableid(self, initial: bool = False) -> int | None:
        """tableid 파일 → preset_id. mtime 을 돌려준다 (없으면 None).

        tableid 는 수동 프리셋 선택·Console 종료 시에만 갱신된다 (자동 전환은
        로그로만 흐름). 따라서 mtime 변경 = 수동 선택으로 보고 disabled 를
        해제한다. 자동 전환 꺼짐 상태에서 유일한 전환 신호다 (2026-08-12).
        """
        try:
            st = self.tableid_path.stat()
            self.state.preset_id = int(self.tableid_path.read_text().strip())
            if not initial:
                self.state.disabled = False
            return st.st_mtime_ns
        except (OSError, ValueError):
            return None

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
        # 수동 프리셋 선택 감지 (tableid mtime)
        try:
            mt = self.tableid_path.stat().st_mtime_ns
            if mt != self._tableid_mtime:
                self._tableid_mtime = self._read_tableid()
        except OSError:
            pass
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
