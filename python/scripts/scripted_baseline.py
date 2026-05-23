"""Scripted baseline — proves actions can actually drive the trading sim.

Targets the PaperTradingDesk window's Buy button by absolute pixel
location. Useful as a sanity check that:
  - mouse moves land where we expect
  - clicks actually fire trades
  - the trading_state.json reward source picks up the change

If your window is at a different position, pass --buy-x/--buy-y/--sell-x
/--sell-y to override.

Usage:
    python -m scripts.scripted_baseline --buy-x 700 --buy-y 240
"""
from __future__ import annotations

import argparse
import time

from agent_env import AgentClient, TradingReward


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:7023")
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--step-sleep", type=float, default=2.0,
                   help="Seconds between actions. Default 2.0s — gentle on CPU.")
    p.add_argument("--buy-x", type=int, default=720,
                   help="X pixel of the Buy button in your trading window")
    p.add_argument("--buy-y", type=int, default=230)
    p.add_argument("--sell-x", type=int, default=830)
    p.add_argument("--sell-y", type=int, default=230)
    args = p.parse_args()

    client = AgentClient(base_url=args.url)
    reward = TradingReward()
    reward.reset()
    info = client.info
    print(f"display = {info.width}x{info.height}")
    print(f"buy = ({args.buy_x}, {args.buy_y})  sell = ({args.sell_x}, {args.sell_y})")
    print(f"step sleep = {args.step_sleep}s\n")

    total = 0.0
    for i in range(args.steps):
        # Alternate buy/sell so the random walk doesn't pin us
        is_buy = (i % 2 == 0)
        x, y = (args.buy_x, args.buy_y) if is_buy else (args.sell_x, args.sell_y)
        label = "BUY " if is_buy else "SELL"

        client.click(x, y, button=0)
        time.sleep(args.step_sleep)

        r = reward.reward()
        total += r
        rinfo = reward.info()
        eq = rinfo.get("equity", "?")
        print(f"step {i:3d} {label} at ({x},{y})  r={r:+.4f}  total={total:+.2f}  equity={eq}")


if __name__ == "__main__":
    main()
