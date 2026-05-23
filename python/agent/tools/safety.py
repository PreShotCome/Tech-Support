"""Operational safety tools — the procedures from docs/skills/ as
callable Python tools the agent (and paper_runner) can invoke.

Built from skills 02 (pre-trade-validation), 03 (order-lifecycle),
04 (position-reconciliation), and 06 (session-state-review). Skills
01 and 05 are saved as reference docs only — see docs/skills/.

Each tool returns a structured dict ready to feed back into the LLM or
log to a decision file. None of them mutate state — they observe and
report. paper_runner.py is responsible for acting on what they find.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import Tool


# ---------------------------------------------------------------- helpers


def _trading_client():
    from alpaca.trading.client import TradingClient
    key = os.environ.get("ALPACA_KEY_ID", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        raise RuntimeError("ALPACA_KEY_ID / ALPACA_SECRET_KEY not set.")
    return TradingClient(key, secret, paper=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- session-state-review


def _session_preflight() -> dict[str, Any]:
    """Skill 06: verify state before the bot trades.

    Returns a dict with one boolean per check plus an overall status.
    `cleared` means the session can trade; `halted` means the bot can
    run and observe but must place no orders; `not_cleared` means a
    hard halt — escalate to human."""
    from alpaca.trading.client import TradingClient
    from trading.risk import DEFAULT as RISK

    checks: dict[str, Any] = {}
    failed: list[str] = []

    # 1. broker connectivity + auth
    try:
        client = _trading_client()
        account = client.get_account()
        checks["broker_connectivity"] = True
    except Exception as e:
        checks["broker_connectivity"] = False
        failed.append(f"broker_connectivity: {e}")
        return {
            "timestamp": _now(),
            "status": "not_cleared",
            "checks": checks,
            "failed_checks": failed,
            "action_taken": "escalate",
        }

    # 2. account status
    status = str(getattr(account, "status", "")).lower()
    checks["account_status_ok"] = status in ("active", "accountstatus.active")
    if not checks["account_status_ok"]:
        failed.append(f"account_status_ok (status={status!r})")

    # 3. account is paper (refuse to run against live by accident)
    api_url = str(getattr(client, "_base_url", "") or "").lower()
    checks["account_is_paper"] = (
        "paper" in api_url
        or "paper-api" in api_url
        or "alpaca.markets" in api_url and "paper" in api_url
    )
    if not checks["account_is_paper"]:
        failed.append(f"account_is_paper (base_url={api_url!r})")

    # 4. framework loaded + sane
    fw_ok = all([
        0 < RISK.position_cap <= 1.0,
        0 < RISK.exposure_cap <= 2.0,
        RISK.position_count_cap > 0,
        0 < RISK.daily_drawdown_kill < 1.0,
        0 < RISK.total_drawdown_kill < 1.0,
    ])
    checks["framework_loaded"] = fw_ok
    if not fw_ok:
        failed.append("framework_loaded (sanity)")

    # 5. kill-switch clear (intra-day and overall)
    equity = float(account.equity)
    last_equity = float(account.last_equity)
    intraday_dd = (last_equity - equity) / last_equity if last_equity > 0 else 0.0
    # Total drawdown approximation: would need a stored high-water mark
    # for full accuracy; we approximate as (equity - peak) / peak with
    # peak = max(last_equity, equity).
    peak = max(last_equity, equity)
    total_dd = (peak - equity) / peak if peak > 0 else 0.0
    checks["kill_switch_clear"] = (
        intraday_dd < RISK.daily_drawdown_kill
        and total_dd < RISK.total_drawdown_kill
    )
    if not checks["kill_switch_clear"]:
        failed.append(
            f"kill_switch_clear (intraday_dd={intraday_dd:.3f}, "
            f"total_dd={total_dd:.3f})"
        )

    # 6. market state known
    try:
        clock = client.get_clock()
        checks["market_state_known"] = True
        market_open = bool(clock.is_open)
    except Exception as e:
        checks["market_state_known"] = False
        market_open = None
        failed.append(f"market_state_known: {e}")

    # 7. clock sanity (system clock vs broker clock within 60s)
    try:
        broker_ts = clock.timestamp
        broker_dt = broker_ts if isinstance(broker_ts, datetime) else datetime.fromisoformat(str(broker_ts).replace("Z", "+00:00"))
        skew = abs((datetime.now(timezone.utc) - broker_dt).total_seconds())
        checks["clock_sane"] = skew < 60.0
    except Exception:
        checks["clock_sane"] = True
        skew = None

    # Decide status
    hard_halt = any([
        not checks.get("broker_connectivity"),
        not checks.get("account_status_ok"),
        not checks.get("account_is_paper"),
        not checks.get("framework_loaded"),
    ])
    if hard_halt:
        status_out = "not_cleared"
    elif not checks.get("kill_switch_clear", True):
        status_out = "halted"
    else:
        status_out = "cleared"

    return {
        "timestamp": _now(),
        "status": status_out,
        "checks": checks,
        "failed_checks": failed,
        "equity": equity,
        "last_equity": last_equity,
        "market_open": market_open,
        "clock_skew_seconds": skew,
    }


# ---------------------------------------------------------------- position-reconciliation


def _reconcile_positions(expected: dict[str, float] | None = None) -> dict[str, Any]:
    """Skill 04: diff broker positions against expected.

    `expected` is {symbol: target_weight} the caller believes the
    portfolio should hold. If None, just returns broker truth + a
    no-discrepancy report (still useful for snapshotting state)."""
    client = _trading_client()
    account = client.get_account()
    equity = float(account.equity)
    positions = client.get_all_positions()

    broker_state = {}
    for p in positions:
        broker_state[p.symbol] = {
            "qty": float(p.qty),
            "market_value": float(p.market_value),
            "avg_entry_price": float(p.avg_entry_price),
            "weight": float(p.market_value) / equity if equity > 0 else 0.0,
        }

    discrepancies: list[dict[str, Any]] = []
    if expected:
        # Symbols broker has but we didn't expect.
        for sym, st in broker_state.items():
            if sym not in expected:
                discrepancies.append({
                    "type": "missing_internal",
                    "symbol": sym,
                    "broker_value": st["market_value"],
                    "expected_weight": 0.0,
                })
        # Symbols we expected but broker doesn't have.
        for sym, w in expected.items():
            if sym not in broker_state and w > 0:
                discrepancies.append({
                    "type": "missing_broker",
                    "symbol": sym,
                    "expected_weight": w,
                    "broker_value": 0.0,
                })
        # Weight drift on shared symbols.
        for sym, st in broker_state.items():
            if sym in expected:
                drift_pct = abs(st["weight"] - expected[sym])
                if drift_pct > 0.02:  # 2 percentage-point tolerance
                    discrepancies.append({
                        "type": "weight_mismatch",
                        "symbol": sym,
                        "expected_weight": expected[sym],
                        "broker_weight": st["weight"],
                        "drift": drift_pct,
                    })

    if not discrepancies:
        out_status = "clean"
    elif all(d["type"] == "weight_mismatch" and d.get("drift", 0) < 0.05 for d in discrepancies):
        out_status = "benign"
    else:
        out_status = "drift"

    return {
        "timestamp": _now(),
        "status": out_status,
        "equity": equity,
        "broker_positions": broker_state,
        "discrepancies": discrepancies,
        "action_taken": {
            "clean": "none",
            "benign": "adopt_broker_state",
            "drift": "halt_new",
        }[out_status],
    }


# ---------------------------------------------------------------- pre-trade-validation


def _validate_trade(
    symbol: str,
    side: str,
    qty: float,
    last_price: float,
    notional_value: float | None = None,
) -> dict[str, Any]:
    """Skill 02: mechanical pre-trade gate.

    Returns {checks, passed, failed_checks, decision}. `decision` is
    'submit' only when every check is True."""
    from trading.risk import DEFAULT as RISK
    client = _trading_client()
    account = client.get_account()
    equity = float(account.equity)
    buying_power = float(account.buying_power)

    if notional_value is None:
        notional_value = abs(qty) * last_price

    # After-fill exposure: current gross + new position
    positions = client.get_all_positions()
    current_gross = sum(abs(float(p.market_value)) for p in positions)
    after_gross = current_gross + (notional_value if side.lower() == "buy" else -notional_value)
    after_count = len(positions) + (1 if side.lower() == "buy" and not any(p.symbol == symbol for p in positions) else 0)

    checks: dict[str, bool] = {}

    checks["account_status_ok"] = str(account.status).lower().endswith("active")
    checks["buying_power_sufficient"] = buying_power >= notional_value or side.lower() == "sell"
    checks["size_within_cap"] = (notional_value / equity if equity > 0 else 1.0) <= RISK.position_cap + 1e-6
    checks["exposure_within_cap"] = (after_gross / equity if equity > 0 else 1.0) <= RISK.exposure_cap + 1e-6
    checks["position_count_within_cap"] = after_count <= RISK.position_count_cap
    checks["symbol_not_blocklisted"] = symbol.upper() not in {s.upper() for s in RISK.blocklist}
    checks["order_params_valid"] = (qty > 0) and (last_price > 0) and (side.lower() in ("buy", "sell"))

    # Kill-switch
    last_equity = float(account.last_equity)
    intraday_dd = (last_equity - equity) / last_equity if last_equity > 0 else 0.0
    checks["kill_switch_clear"] = intraday_dd < RISK.daily_drawdown_kill

    passed = all(checks.values())
    failed = [k for k, v in checks.items() if not v]

    return {
        "timestamp": _now(),
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "notional_value": notional_value,
        "checks": checks,
        "passed": passed,
        "failed_checks": failed,
        "decision": "submit" if passed else "block",
        "context": {
            "equity": equity,
            "buying_power": buying_power,
            "current_gross_exposure": current_gross,
            "after_fill_gross_exposure": after_gross,
            "after_fill_position_count": after_count,
            "intraday_drawdown": intraday_dd,
        },
    }


# ---------------------------------------------------------------- order-lifecycle


def _track_order(
    order_id: str,
    timeout_seconds: float = 90.0,
    poll_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    """Skill 03: poll an order to a confirmed terminal state.

    Returns the lifecycle record with the broker's verbatim status. If
    timeout elapses without a terminal state, returns status='unknown'
    so the caller can run the unknown-state procedure (freeze symbol,
    reconcile, escalate)."""
    TERMINAL = {"filled", "canceled", "rejected", "expired", "done_for_day"}

    client = _trading_client()
    deadline = time.time() + timeout_seconds
    history: list[dict[str, Any]] = []
    last_state = None

    while time.time() < deadline:
        try:
            o = client.get_order_by_id(order_id)
        except Exception as e:
            history.append({"ts": _now(), "event": "poll_error", "detail": str(e)})
            time.sleep(poll_interval_seconds)
            continue

        state = str(o.status.value if hasattr(o.status, "value") else o.status).lower()
        if state != last_state:
            history.append({"ts": _now(), "state": state})
            last_state = state

        if state in TERMINAL:
            return {
                "order_id": order_id,
                "symbol": o.symbol,
                "intended_qty": float(o.qty) if o.qty else None,
                "filled_qty": float(o.filled_qty) if o.filled_qty else 0.0,
                "avg_fill_price": (float(o.filled_avg_price) if o.filled_avg_price else None),
                "final_state": state,
                "reject_reason": getattr(o, "extended_hours", None) and "" or "",
                "state_history": history,
                "escalated": False,
            }
        time.sleep(poll_interval_seconds)

    # Timed out without terminal state
    return {
        "order_id": order_id,
        "final_state": "unknown",
        "state_history": history,
        "last_observed_state": last_state,
        "escalated": True,
        "unknown_resolution": (
            "Order did not reach a terminal state within "
            f"{timeout_seconds}s. Freeze trading on this symbol and "
            "reconcile against the broker as source of truth."
        ),
    }


# ---------------------------------------------------------------- decision log


def _decision_log(record: dict, log_path: str | None = None) -> str:
    """Append a structured record to the decision log."""
    p = Path(log_path) if log_path else Path("decisions.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {"logged_at": _now(), **record}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return f"logged to {p}"


# ---------------------------------------------------------------- tool defs


SESSION_PREFLIGHT_TOOL = Tool(
    name="session_preflight",
    description=(
        "Run the session-start preflight checks (broker connectivity, "
        "account status, paper-vs-live, framework loaded, kill-switch "
        "state, market state, clock sanity). Returns 'cleared', "
        "'halted', or 'not_cleared'. No trade should be placed unless "
        "status == 'cleared'."
    ),
    parameters_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_session_preflight,
)

RECONCILE_TOOL = Tool(
    name="reconcile_positions",
    description=(
        "Diff broker-reported positions against the expected portfolio. "
        "Returns broker truth + any drift discrepancies. If expected is "
        "omitted, returns a snapshot of broker state without diffing."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "expected": {
                "type": "object",
                "description": "{symbol: target_weight} the caller believes the portfolio should hold.",
            },
        },
        "additionalProperties": False,
    },
    handler=_reconcile_positions,
)

VALIDATE_TRADE_TOOL = Tool(
    name="validate_trade",
    description=(
        "Mechanical pre-trade gate against the risk framework: position "
        "size cap, exposure cap, position-count cap, buying power, "
        "blocklist, kill-switch. Returns a decision ('submit' or "
        "'block') plus the failed checks. Never override a block."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "side": {"type": "string", "description": "'buy' or 'sell'"},
            "qty": {"type": "number"},
            "last_price": {"type": "number"},
            "notional_value": {"type": "number", "description": "Optional. If omitted, computed as qty * last_price."},
        },
        "required": ["symbol", "side", "qty", "last_price"],
        "additionalProperties": False,
    },
    handler=_validate_trade,
)

TRACK_ORDER_TOOL = Tool(
    name="track_order",
    description=(
        "Poll an order to a confirmed terminal state (filled, canceled, "
        "rejected, expired). Returns the lifecycle record. If the order "
        "does not reach a terminal state within timeout_seconds, returns "
        "status='unknown' so the caller can freeze the symbol and "
        "reconcile against the broker."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "timeout_seconds": {"type": "number", "description": "Default 90."},
            "poll_interval_seconds": {"type": "number", "description": "Default 2."},
        },
        "required": ["order_id"],
        "additionalProperties": False,
    },
    handler=_track_order,
)

LOG_DECISION_TOOL = Tool(
    name="log_decision",
    description=(
        "Append a structured decision record to decisions.jsonl. Use "
        "this to log validation outcomes, reconciliation results, and "
        "blocked-trade events. The log is the audit trail."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "record": {"type": "object", "description": "Arbitrary JSON record."},
            "log_path": {"type": "string", "description": "Default 'decisions.jsonl'."},
        },
        "required": ["record"],
        "additionalProperties": False,
    },
    handler=_decision_log,
)


def register(registry) -> None:
    for t in (
        SESSION_PREFLIGHT_TOOL,
        RECONCILE_TOOL,
        VALIDATE_TRADE_TOOL,
        TRACK_ORDER_TOOL,
        LOG_DECISION_TOOL,
    ):
        registry.register(t)
