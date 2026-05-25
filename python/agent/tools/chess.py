"""Stockfish chess engine — analyze positions via UCI.

Stockfish (https://stockfishchess.org) is the top open-source chess
engine in the world. Theo can analyze any position, suggest the best
move, evaluate who's winning, and explain principal variations.

Setup:
  - Install: `winget install Stockfish.Stockfish` (Windows),
    `brew install stockfish` (macOS), `apt install stockfish` (Linux).
  - The binary should be on PATH as `stockfish`.

Reference docs: docs/research/Stockfish/

Inputs are positions in FEN (Forsyth–Edwards Notation), which is the
chess standard. From the starting position you can use the constant
'startpos'. To analyze after a sequence of moves, pass the FEN that
results from playing them."""
from __future__ import annotations

import shutil
import subprocess
import re
from typing import Any

from .base import Tool


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _chess_analyze(fen: str = STARTPOS_FEN, depth: int = 15,
                   movetime_ms: int = 0) -> dict[str, Any]:
    """Analyze a chess position. Returns best move, evaluation, and
    the principal variation."""
    if not shutil.which("stockfish"):
        return {
            "error": "stockfish not installed",
            "install": (
                "Windows: winget install Stockfish.Stockfish | "
                "macOS: brew install stockfish | "
                "Linux: apt install stockfish"
            ),
        }

    fen = (fen or "").strip() or STARTPOS_FEN

    # Build UCI command sequence to send via stdin
    commands = ["uci", f"position fen {fen}"]
    if movetime_ms > 0:
        commands.append(f"go movetime {int(movetime_ms)}")
    else:
        commands.append(f"go depth {int(depth)}")
    commands.append("quit")
    stdin_data = "\n".join(commands) + "\n"

    try:
        proc = subprocess.run(
            ["stockfish"], input=stdin_data,
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"error": "stockfish timed out after 2min"}

    if proc.returncode != 0:
        return {
            "error": f"stockfish exit {proc.returncode}",
            "stderr": proc.stderr[:300],
        }

    out = proc.stdout or ""

    # Parse the last `info` line with score (it's the deepest analysis)
    info_lines = [l for l in out.splitlines() if l.startswith("info ") and "score" in l]
    best_move_match = re.search(r"bestmove\s+(\S+)", out)

    eval_cp = None
    eval_mate = None
    depth_reached = None
    nodes = None
    pv: list[str] = []

    if info_lines:
        last = info_lines[-1]
        m_depth = re.search(r"depth\s+(\d+)", last)
        m_nodes = re.search(r"nodes\s+(\d+)", last)
        m_cp = re.search(r"score\s+cp\s+(-?\d+)", last)
        m_mate = re.search(r"score\s+mate\s+(-?\d+)", last)
        m_pv = re.search(r"\s+pv\s+(.+)$", last)
        if m_depth: depth_reached = int(m_depth.group(1))
        if m_nodes: nodes = int(m_nodes.group(1))
        if m_cp:    eval_cp = int(m_cp.group(1))
        if m_mate:  eval_mate = int(m_mate.group(1))
        if m_pv:    pv = m_pv.group(1).split()

    return {
        "fen":           fen,
        "best_move":     best_move_match.group(1) if best_move_match else None,
        "eval_centipawns": eval_cp,        # None if mate found instead
        "eval_mate_in":  eval_mate,        # plies to mate; sign = who's mating
        "depth":         depth_reached,
        "nodes":         nodes,
        "principal_variation": pv[:8],     # first 8 moves of best line
    }


CHESS_ANALYZE_TOOL = Tool(
    name="chess_analyze",
    description=(
        "Analyze a chess position with Stockfish. Pass a FEN string "
        "in `fen` (the chess-standard position notation). Set `depth` "
        "for how many plies to search (default 15; higher = stronger "
        "and slower) OR `movetime_ms` for fixed thinking time. "
        "Returns: best move in UCI notation (e.g. 'e2e4'), evaluation "
        "in centipawns (positive = white winning) OR mate-in-N plies, "
        "search depth reached, nodes searched, and principal "
        "variation (best line). Use when the human asks for chess "
        "analysis, best move, position evaluation, or wants to study "
        "a game."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "fen": {
                "type": "string",
                "description": (
                    "Position in FEN. Default is the starting position. "
                    "Example after 1.e4: 'rnbqkbnr/pppppppp/8/8/4P3/8/"
                    "PPPP1PPP/RNBQKBNR b KQkq e3 0 1'."
                ),
            },
            "depth": {"type": "integer", "description": "Search depth in plies. Default 15."},
            "movetime_ms": {"type": "integer", "description": "Fixed thinking time in ms. Overrides depth if > 0."},
        },
        "additionalProperties": False,
    },
    handler=_chess_analyze,
)


def register(registry) -> None:
    registry.register(CHESS_ANALYZE_TOOL)
