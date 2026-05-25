"""Security tools — Trivy (vuln scanner) and CrowdSec (threat intel).

Two tools wired here:

  - `trivy_scan` — vulnerability scan over a filesystem path, container
    image, or git repo. Wraps the `trivy` CLI. Requires Trivy installed:
        winget install AquaSecurity.Trivy   # Windows
        brew install trivy                  # macOS
        sudo apt install trivy              # Debian/Ubuntu

  - `crowdsec_check` — query CrowdSec for IP reputation. Two paths:
      (a) local: `cscli decisions list` for the local daemon's view
      (b) cti: https://cti.api.crowdsec.net for the public CTI feed,
          using a free API key from https://www.crowdsec.net.
    The tool auto-selects based on which is available.

Reference docs: docs/research/trivy/ and docs/research/crowdsec/."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from .base import Tool


# ---------------------------------------------------------------- trivy

def _detect_target_kind(target: str) -> str:
    """Best-guess what kind of target this is."""
    if target.startswith(("http://", "https://", "git@", "git+")):
        return "repo"
    if "/" in target and not os.path.exists(target):
        return "image"            # docker-image-like name
    return "fs"


def _trivy_scan(target: str, kind: str = "auto",
                severity: str = "HIGH,CRITICAL",
                max_findings: int = 25) -> dict[str, Any]:
    """Run a Trivy scan and return parsed findings."""
    if not shutil.which("trivy"):
        return {
            "error": "trivy not installed",
            "install": (
                "winget install AquaSecurity.Trivy on Windows, "
                "brew install trivy on macOS, "
                "apt install trivy on Debian/Ubuntu"
            ),
        }
    if kind == "auto":
        kind = _detect_target_kind(target)
    if kind not in {"fs", "image", "repo"}:
        return {"error": f"unknown kind {kind!r}, expected fs/image/repo/auto"}

    cmd = [
        "trivy", kind, target,
        "--format", "json",
        "--severity", severity,
        "--quiet",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"error": "trivy scan timed out after 5min"}
    if proc.returncode != 0 and not proc.stdout:
        return {"error": f"trivy exit {proc.returncode}", "stderr": proc.stderr[:500]}

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "trivy output not JSON", "stdout": proc.stdout[:500]}

    # Flatten findings across results
    findings: list[dict] = []
    for r in (data.get("Results") or []):
        for v in (r.get("Vulnerabilities") or []):
            findings.append({
                "id":         v.get("VulnerabilityID"),
                "pkg":        v.get("PkgName"),
                "installed":  v.get("InstalledVersion"),
                "fixed":      v.get("FixedVersion"),
                "severity":   v.get("Severity"),
                "title":      v.get("Title"),
                "target":     r.get("Target"),
            })
    # Sort by severity rank
    rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}
    findings.sort(key=lambda f: rank.get(f["severity"], 9))
    return {
        "target": target,
        "kind": kind,
        "severity_filter": severity,
        "total_findings": len(findings),
        "shown": min(len(findings), max_findings),
        "findings": findings[:max_findings],
    }


TRIVY_SCAN_TOOL = Tool(
    name="trivy_scan",
    description=(
        "Vulnerability scan via Trivy. `target` can be a filesystem "
        "path, a container image name (e.g. 'nginx:latest'), or a "
        "git repo URL. `kind` is auto-detected by default but can be "
        "forced to fs/image/repo. `severity` filters which severities "
        "are shown (default 'HIGH,CRITICAL'). Returns sorted findings "
        "with CVE id, affected package, fix version. Requires the "
        "trivy CLI installed."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Path, image, or repo URL."},
            "kind": {"type": "string", "description": "auto / fs / image / repo. Default auto."},
            "severity": {"type": "string", "description": "Comma-separated severities. Default HIGH,CRITICAL."},
            "max_findings": {"type": "integer", "description": "Cap output. Default 25."},
        },
        "required": ["target"],
        "additionalProperties": False,
    },
    handler=_trivy_scan,
)


# -------------------------------------------------------------- crowdsec

def _crowdsec_check(ip: str | None = None, mode: str = "auto") -> dict[str, Any]:
    """Check CrowdSec for IP reputation or local decisions.

    Modes:
      auto  — try CTI first if key present, else local
      cti   — query CrowdSec CTI (public threat intel) with free API key
      local — query local cscli for current decisions

    Without `ip`, local mode lists current decisions.
    """
    api_key = os.environ.get("CROWDSEC_CTI_KEY") or os.environ.get("CROWDSEC_API_KEY")
    cscli = shutil.which("cscli")

    chosen = mode
    if chosen == "auto":
        if api_key and ip:
            chosen = "cti"
        elif cscli:
            chosen = "local"
        else:
            return {
                "error": "no CrowdSec source available",
                "fix": (
                    "Either set CROWDSEC_CTI_KEY env var (free key from "
                    "crowdsec.net) for IP lookups, or install crowdsec "
                    "locally to query the daemon via cscli."
                ),
            }

    if chosen == "cti":
        if not api_key:
            return {"error": "cti mode requires CROWDSEC_CTI_KEY env var"}
        if not ip:
            return {"error": "cti mode requires an ip"}
        try:
            import requests
        except ImportError:
            return {"error": "requests not installed"}
        try:
            r = requests.get(
                f"https://cti.api.crowdsec.net/v2/smoke/{ip}",
                headers={"x-api-key": api_key},
                timeout=10,
            )
        except requests.RequestException as e:
            return {"error": f"{type(e).__name__}: {e}"}
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "body": r.text[:400]}
        return {"mode": "cti", "ip": ip, "data": r.json()}

    # local mode
    if not cscli:
        return {"error": "cscli not on PATH; install CrowdSec locally"}
    cmd = ["cscli", "decisions", "list", "-o", "json"]
    if ip:
        cmd.extend(["--ip", ip])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"error": "cscli timed out"}
    if proc.returncode != 0:
        return {"error": f"cscli exit {proc.returncode}", "stderr": proc.stderr[:400]}
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        data = proc.stdout
    return {"mode": "local", "ip": ip, "decisions": data}


CROWDSEC_CHECK_TOOL = Tool(
    name="crowdsec_check",
    description=(
        "Threat intelligence via CrowdSec. Two modes (auto-selected):\n"
        "  - 'cti'   queries the public CrowdSec CTI feed for an IP. "
        "Needs a free API key in CROWDSEC_CTI_KEY env var.\n"
        "  - 'local' queries the local CrowdSec daemon via cscli for "
        "current decisions. Without an `ip`, lists all current "
        "decisions.\n"
        "Use this when the human asks 'is this IP known bad?' or "
        "'what's CrowdSec seeing right now?'."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "ip": {"type": "string", "description": "Target IP. Optional for local mode."},
            "mode": {"type": "string", "description": "auto / cti / local. Default auto."},
        },
        "additionalProperties": False,
    },
    handler=_crowdsec_check,
)


def register(registry) -> None:
    registry.register(TRIVY_SCAN_TOOL)
    registry.register(CROWDSEC_CHECK_TOOL)
