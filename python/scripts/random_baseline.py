"""Random-action baseline. Proves the env loop is wired correctly.

Usage:
    python -m scripts.random_baseline --task trading --steps 200
    python -m scripts.random_baseline --task compute --steps 200
"""
from __future__ import annotations

import argparse
import time

from agent_env import DesktopAgentEnv, TradingReward, ComputeReward, NullReward
from agent_env.env import EnvConfig


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", choices=["trading", "compute", "none"], default="none")
    p.add_argument("--steps", type=int, default=100)
    p.add_argument("--url", default="http://127.0.0.1:7023")
    p.add_argument("--step-sleep", type=float, default=1.0,
                   help="Seconds to wait between steps. Higher = less CPU load. "
                        "Default 1.0 (≈ 1 Hz, gentle). Use 0.1 for fast smoke tests.")
    p.add_argument("--obs-size", type=int, default=84,
                   help="Square observation dim sent to the policy. Smaller = less work.")
    args = p.parse_args()

    reward = {
        "trading": TradingReward(),
        "compute": ComputeReward(),
        "none": NullReward(),
    }[args.task]

    cfg = EnvConfig(
        base_url=args.url,
        step_sleep_s=args.step_sleep,
        obs_size=(args.obs_size, args.obs_size),
    )
    env = DesktopAgentEnv(config=cfg, reward=reward)
    obs, _ = env.reset()
    print(f"reset ok. observation shape = {obs.shape}")
    print(f"display = {env.client.info.width}x{env.client.info.height}")
    print(f"step_sleep = {args.step_sleep}s ({1.0/max(args.step_sleep, 0.001):.1f} Hz)")

    total = 0.0
    t0 = time.time()
    for i in range(args.steps):
        action = env.action_space.sample()
        obs, r, term, trunc, info = env.step(action)
        total += r
        if i % 10 == 0:
            print(f"step {i:4d} action={list(action)} r={r:+.4f} total={total:+.2f} info={info.get('reward')}")
        if term or trunc:
            print("episode end")
            break
    elapsed = time.time() - t0
    print(f"done. {args.steps} steps in {elapsed:.1f}s = {args.steps/elapsed:.1f} steps/s, reward sum = {total:.2f}")


if __name__ == "__main__":
    main()
