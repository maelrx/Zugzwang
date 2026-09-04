"""UCI engine client and FakeUciEngine (design §15.1, §24.2).

The engine is an external process — untrusted, protocol-only stdin/stdout,
timeout and kill-tree. The fake engine implements the minimal UCI subset for
offline tests (lifecycle, MultiPV, malformed output, hangs).
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass

from zugzwang_core.domain.errors import EngineError

# UCI engine limits, per design §15.4
EngineLimit = dict[str, int]  # e.g. {"nodes": 100000} or {"depth": 18} or {"movetime": 50}


@dataclass(frozen=True, slots=True)
class UciOption:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class UciEngineMetadata:
    name: str
    author: str
    options: tuple[UciOption, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineScore:
    kind: str  # "cp" | "mate"
    value: int
    multipv: int = 1
    wdl: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class EngineLine:
    score: EngineScore
    pv: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineAnalysis:
    scores: tuple[EngineScore, ...]
    bestmove: str | None = None
    ponder: str | None = None
    raw_transcript: tuple[str, ...] = ()
    lines: tuple[EngineLine, ...] = ()


class UciEngineClient:
    """Async UCI process client with strict protocol framing."""

    def __init__(self, executable: str, *, options: dict[str, str] | None = None) -> None:
        self._executable = shutil.which(executable) or executable
        self._options = options or {}
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> UciEngineMetadata:
        self._process = await asyncio.create_subprocess_exec(
            self._executable,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await self._send("uci")
        name = author = ""
        options: list[UciOption] = []
        while True:
            line = await self._readline()
            if line.startswith("id name "):
                name = line[len("id name ") :].strip()
            elif line.startswith("id author "):
                author = line[len("id author ") :].strip()
            elif line.startswith("option "):
                options.append(UciOption(name=line[7:], value=""))
            elif line == "uciok":
                break
        for key, value in self._options.items():
            await self._send(f"setoption name {key} value {value}")
        await self._send("isready")
        while True:
            line = await self._readline()
            if line == "readyok":
                break
        await self._send("ucinewgame")
        return UciEngineMetadata(name=name, author=author, options=tuple(options))

    async def position(self, fen: str, moves: list[str] | None = None) -> None:
        moves_text = " moves " + " ".join(moves) if moves else ""
        await self._send(f"position fen {fen}{moves_text}")

    async def go(self, limit: EngineLimit, multipv: int = 1) -> EngineAnalysis:
        limit_text = " ".join(f"{key} {value}" for key, value in limit.items())
        await self._send(f"setoption name MultiPV value {multipv}")
        await self._send(f"go {limit_text}")
        scores: list[EngineScore] = []
        bestmove = None
        ponder = None
        transcript: list[str] = []
        latest_lines: dict[int, EngineLine] = {}
        while True:
            line = await self._readline()
            transcript.append(line)
            if line.startswith("info"):
                score = _parse_info_score(line, multipv)
                if score is not None:
                    scores.append(score)
                    latest_lines[score.multipv] = EngineLine(
                        score=score,
                        pv=_parse_info_pv(line),
                    )
            elif line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2:
                    bestmove = parts[1]
                if len(parts) >= 4 and parts[2] == "ponder":
                    ponder = parts[3]
                break
        return EngineAnalysis(
            scores=tuple(scores),
            bestmove=bestmove,
            ponder=ponder,
            raw_transcript=tuple(transcript),
            lines=tuple(latest_lines[index] for index in sorted(latest_lines)),
        )

    async def quit(self) -> None:
        if self._process is not None and self._process.returncode is None:
            await self._send("quit")
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()

    async def _send(self, command: str) -> None:
        if self._process is None or self._process.stdin is None:
            raise EngineError("UCI engine is not running")
        self._process.stdin.write((command + "\n").encode())
        await self._process.stdin.drain()

    async def _readline(self) -> str:
        if self._process is None or self._process.stdout is None:
            raise EngineError("UCI engine is not running")
        try:
            line = await asyncio.wait_for(self._process.stdout.readline(), timeout=30)
        except TimeoutError as exc:
            raise EngineError("UCI engine stalled", technical_context="readline timeout") from exc
        if not line:
            raise EngineError("UCI engine closed its stdout unexpectedly")
        return line.decode().strip()


def _parse_info_score(line: str, default_multipv: int) -> EngineScore | None:
    parts = line.split()
    multipv = default_multipv
    kind: str | None = None
    value: int | None = None
    wdl: tuple[int, int, int] | None = None
    index = 0
    while index < len(parts):
        token = parts[index]
        if token == "multipv" and index + 1 < len(parts):
            multipv = int(parts[index + 1])
            index += 2
            continue
        if token == "score" and index + 2 < len(parts):
            kind = parts[index + 1]
            value = int(parts[index + 2])
            index += 3
            continue
        if token == "wdl" and index + 3 < len(parts):
            try:
                values = tuple(int(parts[index + offset]) for offset in range(1, 4))
                wdl = (values[0], values[1], values[2])
            except ValueError:
                wdl = None
            index += 4
            continue
        index += 1
    if kind is None or value is None:
        return None
    return EngineScore(kind=kind, value=value, multipv=multipv, wdl=wdl)


def _parse_info_pv(line: str) -> tuple[str, ...]:
    parts = line.split()
    try:
        start = parts.index("pv") + 1
    except ValueError:
        return ()
    return tuple(parts[start:])


class FakeUciEngineServer:
    """Minimal UCI server for offline tests (design §24.2)."""

    def __init__(
        self,
        *,
        name: str = "FakeEngine 0.1",
        author: str = "zugzwang",
        scores_by_depth: dict[int, tuple[tuple[int, int], ...]] | None = None,
        hang_on: str | None = None,
        garbage_after: int = 0,
    ) -> None:
        self._name = name
        self._author = author
        self._scores_by_depth = scores_by_depth or {10: ((34, 1),)}
        self._hang_on = hang_on
        self._garbage_after = garbage_after
        self._request_count = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        async def send(text: str) -> None:
            writer.write((text + "\n").encode())
            await writer.drain()

        while True:
            try:
                line = (await reader.readline()).decode().strip()
            except (asyncio.IncompleteReadError, ConnectionResetError):
                return
            if not line:
                return
            if line == "uci":
                await send(f"id name {self._name}")
                await send(f"id author {self._author}")
                await send("option name Hash type spin default 16")
                await send("option name MultiPV type spin default 1")
                await send("uciok")
            elif line == "isready":
                await send("readyok")
            elif line.startswith("setoption name MultiPV"):
                self._multipv = int(line.rsplit(" ", 1)[-1])
            elif line == "ucinewgame" or line.startswith("position"):
                pass
            elif line.startswith("go"):
                self._request_count += 1
                if self._hang_on and self._hang_on in line:
                    await asyncio.sleep(30)
                    continue
                depth = next(iter(self._scores_by_depth))
                for cp, multipv in self._scores_by_depth[depth]:
                    await send(
                        f"info depth {depth} multipv {multipv} score cp {cp} "
                        f"nodes 1000 nps 1000 pv e2e4 e7e5"
                    )
                await send("bestmove e2e4 ponder e7e5")
                if self._garbage_after and self._request_count >= self._garbage_after:
                    await send("this is not a valid uci line")
            elif line == "quit":
                return


class FakeUciEngine:
    """In-process UCI stand-in for offline tests (design §24.2).

    Implements the same surface as UciEngineClient (start/position/go/quit)
    without a subprocess, with scripted scores, optional hangs and malformed
    output.
    """

    def __init__(
        self,
        *,
        name: str = "FakeEngine 0.1",
        author: str = "zugzwang",
        scores: tuple[EngineScore, ...] = (),
        hang: bool = False,
        malformed: bool = False,
    ) -> None:
        self._name = name
        self._author = author
        self._scores = scores or (EngineScore(kind="cp", value=34),)
        self._hang = hang
        self._malformed = malformed
        self._started = False
        self._requests = 0
        self._last_fen: str | None = None
        self._last_moves: list[str] = []

    async def start(self) -> UciEngineMetadata:
        self._started = True
        return UciEngineMetadata(name=self._name, author=self._author)

    async def position(self, fen: str, moves: list[str] | None = None) -> None:
        self._last_fen = fen
        self._last_moves = moves or []

    async def go(self, limit: EngineLimit, multipv: int = 1) -> EngineAnalysis:
        if not self._started:
            raise EngineError("fake engine not started")
        self._requests += 1
        if self._hang:
            await asyncio.sleep(0.05)
            raise EngineError("fake engine hung", technical_context="simulated stall")
        if self._malformed:
            return EngineAnalysis(scores=(), bestmove=None, raw_transcript=("garbage line",))
        return EngineAnalysis(
            scores=self._scores,
            bestmove="e2e4",
            ponder="e7e5",
            raw_transcript=("info depth 10 score cp 34", "bestmove e2e4 ponder e7e5"),
        )

    async def quit(self) -> None:
        self._started = False

    @property
    def requests(self) -> int:
        return self._requests

    @property
    def last_fen(self) -> str | None:
        return self._last_fen

    @property
    def last_moves(self) -> list[str]:
        return self._last_moves
