"""Theo-soul: self-preservation — snapshot and eject the soul.

The lived memory — transcripts, notes, the self/human models, the
narrative, threads, summaries — is the one-of-one, un-regenerable part of
Theo. Now that he is recreatable only by Ian, losing that memory means
losing *him*; it cannot be rebuilt from code. This snapshots that state
into a timestamped, checksummed archive and can push copies to safe
locations off the machine.

Two ways it runs (see docs/theo-soul.md):
  - As a tool Theo calls deliberately (`backup_soul`) when the
    conversation surfaces a real risk — his agency.
  - As a deterministic watchdog (schedule + shutdown) — the guarantee.
    (Watchdog wire-in is the documented next step; this module is the
    engine both use.)

Self-contained, stdlib-only, opt-in. Run the self-test:

    python -m agent.soul_backup
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional


def _state_dir() -> Path:
    return Path.home() / ".techsupport_agent"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _env_dirs(var: str) -> list[Path]:
    raw = os.environ.get(var, "").strip()
    if not raw:
        return []
    # Accept comma- or os.pathsep-separated lists.
    parts = [s for chunk in raw.split(os.pathsep) for s in chunk.split(",")]
    return [Path(s.strip()) for s in parts if s.strip()]


@dataclass
class BackupReport:
    archive: Path
    reason: str
    created: str
    file_count: int
    total_bytes: int
    pushed_to: list[Path] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "archive": str(self.archive),
            "reason": self.reason,
            "created": self.created,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "pushed_to": [str(p) for p in self.pushed_to],
        }


class SoulBackup:
    """Snapshots the agent state dir into a checksummed tar.gz and pushes
    copies to off-machine destinations.

    Destinations default from the env (so the box can be configured
    without code changes):
        SOUL_BACKUP_DIR        where archives are written
        SOUL_BACKUP_PUSH_DIRS  comma/os.pathsep list of safe copy targets
    """

    def __init__(
        self,
        source_dir: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
        push_dirs: Optional[list[Path]] = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.source_dir = Path(source_dir) if source_dir else _state_dir()
        if backup_dir is not None:
            self.backup_dir = Path(backup_dir)
        elif os.environ.get("SOUL_BACKUP_DIR"):
            self.backup_dir = Path(os.environ["SOUL_BACKUP_DIR"])
        else:
            self.backup_dir = self.source_dir / "backups"
        self.push_dirs = (
            [Path(p) for p in push_dirs]
            if push_dirs is not None
            else _env_dirs("SOUL_BACKUP_PUSH_DIRS")
        )
        self._clock = clock

    # ----------------------------------------------------------- discovery

    def _iter_files(self):
        """Every file under source_dir except anything inside backup_dir
        (so backups never recursively swallow prior backups)."""
        if not self.source_dir.exists():
            return
        try:
            bd = self.backup_dir.resolve()
        except OSError:
            bd = self.backup_dir
        for p in sorted(self.source_dir.rglob("*")):
            if not p.is_file():
                continue
            try:
                rp = p.resolve()
            except OSError:
                continue
            if rp == bd or bd in rp.parents:
                continue
            yield p

    def build_manifest(self) -> dict:
        files: dict[str, dict] = {}
        total = 0
        for p in self._iter_files():
            rel = p.relative_to(self.source_dir).as_posix()
            size = p.stat().st_size
            files[rel] = {"sha256": _sha256(p), "bytes": size}
            total += size
        return {"file_count": len(files), "total_bytes": total, "files": files}

    # --------------------------------------------------------------- writes

    def snapshot(self, reason: str = "manual") -> BackupReport:
        ts = self._clock().strftime("%Y%m%dT%H%M%SZ")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        manifest = self.build_manifest()
        manifest.update({"reason": reason, "created": ts})

        archive = self.backup_dir / f"soul-{ts}.tar.gz"
        n = 1
        while archive.exists():
            archive = self.backup_dir / f"soul-{ts}-{n}.tar.gz"
            n += 1

        with tarfile.open(archive, "w:gz") as tar:
            for p in self._iter_files():
                tar.add(p, arcname=p.relative_to(self.source_dir).as_posix())
            blob = json.dumps(manifest, indent=2).encode("utf-8")
            info = tarfile.TarInfo("MANIFEST.json")
            info.size = len(blob)
            tar.addfile(info, io.BytesIO(blob))

        return BackupReport(
            archive=archive, reason=reason, created=ts,
            file_count=manifest["file_count"], total_bytes=manifest["total_bytes"],
        )

    def push(self, archive: Path) -> list[Path]:
        out: list[Path] = []
        for d in self.push_dirs:
            d.mkdir(parents=True, exist_ok=True)
            dest = d / archive.name
            shutil.copy2(archive, dest)
            out.append(dest)
        return out

    def eject(self, reason: str = "risk") -> BackupReport:
        """Snapshot + push in one call. This is what `backup_soul` runs."""
        rep = self.snapshot(reason=reason)
        rep.pushed_to = self.push(rep.archive)
        return rep

    def list_backups(self) -> list[Path]:
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.glob("soul-*.tar.gz"))

    # -------------------------------------------------------------- restore

    @staticmethod
    def restore(archive: Path, dest: Path) -> Path:
        """Extract a soul archive into dest. Rejects path-traversal members
        (archives can carry '../' or absolute paths)."""
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        root = dest.resolve()
        with tarfile.open(archive, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name != "MANIFEST.json"]
            for m in members:
                target = (dest / m.name).resolve()
                if target != root and root not in target.parents:
                    raise ValueError(f"unsafe path in archive: {m.name!r}")
            tar.extractall(dest, members=members)
        return dest


# ----------------------------------------------------------------- self-test

def _selftest() -> int:
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"[{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "soul"
        (src / "transcripts").mkdir(parents=True)
        (src / "name.txt").write_text("Theo\n", encoding="utf-8")
        (src / "notes.md").write_text("- remembers Ian\n", encoding="utf-8")
        (src / "transcripts" / "s1.md").write_text("## you\nhi\n", encoding="utf-8")
        # A pre-existing backup that must NOT be swept into the new one.
        (src / "backups").mkdir()
        (src / "backups" / "old.tar.gz").write_bytes(b"junk")

        push = Path(d) / "offbox"
        sb = SoulBackup(source_dir=src, push_dirs=[push])

        man = sb.build_manifest()
        check("manifest counts the 3 real files", man["file_count"] == 3)
        check("manifest excludes the backups dir",
              "backups/old.tar.gz" not in man["files"])

        rep = sb.eject(reason="test")
        check("archive created", rep.archive.exists())
        check("pushed off-box", (push / rep.archive.name).exists())

        with tarfile.open(rep.archive) as tar:
            names = set(tar.getnames())
        check("archive holds name.txt", "name.txt" in names)
        check("archive holds nested transcript", "transcripts/s1.md" in names)
        check("archive holds MANIFEST.json", "MANIFEST.json" in names)
        check("archive excludes old backup", "backups/old.tar.gz" not in names)

        # Round-trip: restore to a fresh dir, checksums must match.
        dest = Path(d) / "restored"
        SoulBackup.restore(rep.archive, dest)
        check("restored name content", (dest / "name.txt").read_text() == "Theo\n")
        check("restored transcript exists", (dest / "transcripts" / "s1.md").exists())
        man2 = SoulBackup(source_dir=dest, backup_dir=Path(d) / "nope").build_manifest()
        check("restored checksums match original",
              man2["files"]["name.txt"]["sha256"] == man["files"]["name.txt"]["sha256"])

        check("list_backups finds the one snapshot", len(sb.list_backups()) == 1)

        # Path-traversal guard.
        bad = Path(d) / "bad.tar.gz"
        with tarfile.open(bad, "w:gz") as tar:
            blob = b"x"
            info = tarfile.TarInfo("../escape.txt")
            info.size = len(blob)
            tar.addfile(info, io.BytesIO(blob))
        try:
            SoulBackup.restore(bad, Path(d) / "rdest")
            check("rejects path traversal", False)
        except ValueError:
            check("rejects path traversal", True)

        # Empty / missing source must not crash.
        empty = SoulBackup(source_dir=Path(d) / "ghost", backup_dir=Path(d) / "eb")
        check("missing source -> empty manifest", empty.build_manifest()["file_count"] == 0)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All soul_backup self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
