"""Train theo_net on a set of symbols.

    python -m ml.train --symbols AAPL,MSFT,NVDA --epochs 20

For each (symbol, day) pair we:
  1. Build the 6 features as of that day.
  2. Label = 1 if the symbol's next-5-day return > SPY's next-5-day
     return, else 0.

80/20 train/test split (random). Adam + BCE. Checkpoint saved to
python/ml/checkpoints/theo_net.pt.
"""
from __future__ import annotations

import argparse
import random
from datetime import date as _date, timedelta
from pathlib import Path


CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "theo_net.pt"


def _build_dataset(symbols: list[str], lookback_days: int = 365):
    import torch
    import yfinance as yf
    from .features import build_features, features_to_vector

    today = _date.today()
    spy_hist = yf.Ticker("SPY").history(
        start=(today - timedelta(days=lookback_days + 30)).isoformat(),
        end=today.isoformat(),
        auto_adjust=True,
    )
    spy_closes_by_date = {d.date(): float(c) for d, c in zip(spy_hist.index, spy_hist["Close"])}

    X: list[list[float]] = []
    y: list[float] = []

    for symbol in symbols:
        try:
            hist = yf.Ticker(symbol).history(
                start=(today - timedelta(days=lookback_days + 30)).isoformat(),
                end=today.isoformat(),
                auto_adjust=True,
            )
        except Exception as e:
            print(f"[skip] {symbol}: {e}")
            continue
        if hist is None or len(hist) < 40:
            print(f"[skip] {symbol}: insufficient history")
            continue
        dates = [d.date() for d in hist.index]
        closes = hist["Close"].tolist()
        for i in range(25, len(closes) - 6):
            asof = dates[i]
            try:
                feats = build_features(symbol, asof_date=asof)
            except Exception:
                continue
            # Label: next-5d return vs SPY next-5d return
            ret = (closes[i + 5] / closes[i]) - 1.0
            spy_then = spy_closes_by_date.get(asof)
            spy_future = spy_closes_by_date.get(dates[i + 5])
            if spy_then is None or spy_future is None or spy_then <= 0:
                continue
            spy_ret = (spy_future / spy_then) - 1.0
            label = 1.0 if ret > spy_ret else 0.0
            X.append(features_to_vector(feats))
            y.append(label)

    if not X:
        raise RuntimeError("no training samples produced")
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def train(symbols: list[str], epochs: int = 20, lr: float = 1e-3, seed: int = 0) -> dict:
    import torch
    from .theo_net import TheoNet

    random.seed(seed)
    torch.manual_seed(seed)

    X, y = _build_dataset(symbols)
    n = len(X)
    idx = list(range(n))
    random.shuffle(idx)
    split = int(n * 0.8)
    train_idx, test_idx = idx[:split], idx[split:]
    X_tr, y_tr = X[train_idx], y[train_idx]
    X_te, y_te = X[test_idx], y[test_idx]

    model = TheoNet()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.BCELoss()

    for epoch in range(epochs):
        model.train()
        opt.zero_grad()
        preds = model(X_tr)
        loss = loss_fn(preds, y_tr)
        loss.backward()
        opt.step()

        if (epoch + 1) % max(1, epochs // 10) == 0 or epoch == 0:
            model.eval()
            with torch.no_grad():
                te_preds = model(X_te) if len(X_te) > 0 else preds
                if len(X_te) > 0:
                    te_loss = loss_fn(te_preds, y_te).item()
                    te_acc = ((te_preds > 0.5).float() == y_te).float().mean().item()
                else:
                    te_loss, te_acc = float("nan"), float("nan")
            print(f"epoch {epoch+1:3d}/{epochs}  train_loss={loss.item():.4f}  "
                  f"test_loss={te_loss:.4f}  test_acc={te_acc:.3f}")

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "symbols":    symbols,
        "epochs":     epochs,
        "n_train":    len(train_idx),
        "n_test":     len(test_idx),
    }, CHECKPOINT_PATH)
    print(f"saved checkpoint to {CHECKPOINT_PATH}")
    return {
        "checkpoint": str(CHECKPOINT_PATH),
        "n_train":    len(train_idx),
        "n_test":     len(test_idx),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default="AAPL,MSFT,NVDA,GOOGL,AMZN",
                   help="Comma-separated ticker list.")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    train(symbols, epochs=args.epochs, lr=args.lr, seed=args.seed)


if __name__ == "__main__":
    main()
