"""TourBox Console 설정 디렉터리 파서.

Console 이 실행 중에 직접 갱신하는 파일만 읽는다 (쓰기 없음 — 읽기 전용):
- tourbox.db      : <TBDB> XML. configBytes = 30개 테이블 × 3350바이트
                    (22바이트 헤더 + 256 슬롯 × 13바이트 레코드),
                    테이블 순번 = 프리셋 ID. presetNames 에 프리셋 이름.
- presets/<id>    : <Preset> XML. ShortDesc 사전 = (수정키비트, SWT키코드)
                    → 사용자 표시 설명 (예: "Undo").
- tableProcess    : 프리셋 ID → 대상 프로세스 이름 (자동 전환 매핑).
- tableid         : 마지막 활성 프리셋 ID (기동 시 초기값으로만 사용).

레코드 payload 12바이트: [type, aux, A(mod,cat,0,0,key), B(mod,cat,0,0,key)]
- aux==0x04       : 내장 기능 (id = payload[2:4] big-endian)
- payload[2]&0x80 : 매크로 참조 / &0x20 : TourMenu 참조 (type==0 단독일 때)
- B 가 채워져 있으면 양방향(회전) 슬롯
"""
from __future__ import annotations

import base64
import gzip
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import codes

CONSOLE_DIR = Path.home() / "Library/Application Support/TourBox Console"

TABLE_SIZE = 3350
TABLE_HEADER = 22
RECORD_SIZE = 13
MAX_TABLES = 30

_RE_CONFIG = re.compile(r"<configBytes>([^<]+)</configBytes>")
_RE_PRESET_NAME = re.compile(r"<entry>\s*<int>(\d+)</int>\s*<string>([^<]*)</string>")
_RE_PROCESS = re.compile(
    r"<int>(-?\d+)</int>\s*<ProcessInfo>\s*<name>([^<]*)</name>\s*"
    r"<selected>([^<]*)</selected>")
_RE_SHORTDESC = re.compile(
    r"<ShortDesc>\s*<m>(\d+)</m>\s*<s>(\d+)</s>\s*<d>(.*?)</d>\s*</ShortDesc>",
    re.S)

# 실시간 변경 감지 대상 (mtime+size 핑거프린트)
_WATCH_GLOBS = ["tourbox.db", "tableProcess", "tableid", "presets/*"]


@dataclass(frozen=True)
class Sub:
    """단방향 하위 액션."""
    mod: int
    cat: int
    key: int

    def label(self, descs: dict[tuple[int, int], str]) -> str:
        """설명 사전 우선, 없으면 키 조합 문자열."""
        swt = codes.swt_code(self.cat, self.key)
        if swt is not None and (self.mod, swt) in descs:
            return descs[(self.mod, swt)]
        name = codes.key_label(self.cat, self.key)
        if name is None:
            if self.key == 0 and self.cat == 0:
                # 수정키 단독 지정 (예: Shift 홀드)
                return codes.mods_label(self.mod).rstrip("+") or "?"
            return f"?{self.cat}/{self.key}"
        return codes.mods_label(self.mod) + name


@dataclass(frozen=True)
class Action:
    """슬롯 하나에 할당된 액션 (표시 목적의 관대한 디코드)."""
    kind: str                 # none | key | dual | builtin | macro | tourmenu | raw
    a: Sub | None = None
    b: Sub | None = None
    ref_id: int = 0
    raw: bytes = b""

    def label(self, descs: dict[tuple[int, int], str]) -> str:
        if self.kind == "none":
            return ""
        if self.kind == "key":
            return self.a.label(descs)
        if self.kind == "dual":
            return f"{self.a.label(descs)} / {self.b.label(descs)}"
        if self.kind == "builtin":
            return f"내장기능#{self.ref_id}"
        if self.kind == "macro":
            return f"매크로#{self.ref_id}"
        if self.kind == "tourmenu":
            return "TourMenu"
        return "(미해석)"


def _decode_sub(b: bytes) -> Sub | None:
    if not any(b):
        return None
    return Sub(mod=b[0], cat=b[1], key=b[4])


def decode_payload(payload: bytes) -> Action:
    """12바이트 payload → Action. 실패해도 예외 없이 raw 로 강등."""
    if not any(payload):
        return Action("none")
    if payload[1] == 0x04:
        return Action("builtin", ref_id=int.from_bytes(payload[2:4], "big"))
    if payload[0] == 0 and payload[1] == 0 and payload[2] in (0x80, 0x20):
        others = [i for i, v in enumerate(payload) if v and i not in (2, 4)]
        if not others:
            kind = "macro" if payload[2] == 0x80 else "tourmenu"
            return Action(kind, ref_id=payload[4])
    a = _decode_sub(payload[2:7])
    b = _decode_sub(payload[7:12])
    if a and b:
        return Action("dual", a=a, b=b)
    if a:
        return Action("key", a=a)
    if b:
        return Action("key", a=b)
    # 하위 액션이 모두 비어 있으면 type/speed 플래그만 남은 빈 슬롯
    if payload[1] == 0:
        return Action("none")
    return Action("raw", raw=bytes(payload))


@dataclass
class Preset:
    pid: int
    name: str
    bindings: dict[int, Action] = field(default_factory=dict)      # 슬롯코드 → 액션
    descs: dict[tuple[int, int], str] = field(default_factory=dict)

    def label(self, slot: int) -> str:
        act = self.bindings.get(slot)
        return act.label(self.descs) if act else ""


@dataclass
class Snapshot:
    presets: dict[int, Preset] = field(default_factory=dict)
    process_map: dict[str, int] = field(default_factory=dict)      # 프로세스명 → 프리셋
    last_tableid: int | None = None

    def preset_for_process(self, process: str | None) -> Preset | None:
        if process is None:
            return None
        pid = self.process_map.get(process)
        if pid is None:
            pid = self.process_map.get("__Others__")
        return self.presets.get(pid) if pid is not None else None


class ConsoleStore:
    """읽기 전용 파서 + 변경 핑거프린트."""

    def __init__(self, base: Path = CONSOLE_DIR):
        self.base = Path(base)

    # -- 변경 감지 ---------------------------------------------------------
    def fingerprint(self) -> tuple:
        out = []
        for pattern in _WATCH_GLOBS:
            for p in sorted(self.base.glob(pattern)):
                try:
                    st = p.stat()
                    out.append((str(p), st.st_mtime_ns, st.st_size))
                except OSError:
                    continue
        return tuple(out)

    # -- 파싱 ---------------------------------------------------------------
    def load(self) -> Snapshot:
        snap = Snapshot()
        db_text = (self.base / "tourbox.db").read_text(encoding="utf-8",
                                                       errors="replace")
        m = _RE_CONFIG.search(db_text)
        if not m:
            raise ValueError("tourbox.db 에 configBytes 없음")
        blob = base64.b64decode(m.group(1))

        names: dict[int, str] = {}
        for pid_s, name in _RE_PRESET_NAME.findall(db_text):
            pid = int(pid_s)
            if pid < MAX_TABLES:
                names[pid] = name

        for pid, name in names.items():
            start = pid * TABLE_SIZE
            table = blob[start + TABLE_HEADER:start + TABLE_SIZE]
            if len(table) < 256 * RECORD_SIZE:
                continue
            preset = Preset(pid=pid, name=name, descs=self._load_descs(pid))
            for r in range(256):
                rec = table[r * RECORD_SIZE:(r + 1) * RECORD_SIZE]
                act = decode_payload(rec[1:])
                if act.kind != "none":
                    preset.bindings[rec[0]] = act
            snap.presets[pid] = preset

        proc_path = self.base / "tableProcess"
        if proc_path.exists():
            for pid_s, pname, selected in _RE_PROCESS.findall(
                    proc_path.read_text(encoding="utf-8", errors="replace")):
                pid = int(pid_s)
                if pid >= 0 and selected.strip() == "true":
                    snap.process_map[pname] = pid

        tid_path = self.base / "tableid"
        if tid_path.exists():
            try:
                snap.last_tableid = int(tid_path.read_text().strip())
            except ValueError:
                pass
        return snap

    def _load_descs(self, pid: int) -> dict[tuple[int, int], str]:
        path = self.base / "presets" / str(pid)
        if not path.exists():
            return {}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {}
        out = {}
        for m_s, s_s, desc in _RE_SHORTDESC.findall(text):
            out[(int(m_s), int(s_s))] = desc.strip()
        return out


def load_tb_file(path: Path) -> bytes:
    """(테스트용) .tb / import 파일 → configBytes blob."""
    data = Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    m = _RE_CONFIG.search(data.decode("utf-8", errors="replace"))
    if not m:
        raise ValueError("configBytes 없음")
    return base64.b64decode(m.group(1))
