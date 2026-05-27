"""Train theo_net on a set of symbols.

    python -m ml.train --symbols AAPL,MSFT,NVDA --epochs 50 --patience 7

For each (symbol, day) pair we:
  1. Build the 6 features as of that day.
  2. Label = 1 if the symbol's next-5-day return > SPY's next-5-day
     return, else 0.

80/20 train/test split (random). Adam + BCE.
Best checkpoint (lowest test loss) saved to python/ml/checkpoints/theo_net.pt.
Early stopping halts training after `patience` epochs with no test-loss improvement.
"""
from __future__ import annotations

import argparse
import copy
import math
import random
from datetime import date as _date, timedelta
from pathlib import Path


CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "theo_net.pt"

DEFAULT_SYMBOLS = (
    "AAPL,MSFT,NVDA,GOOGL,META,AMZN,TSLA,AMD,AVGO,CRM,"
    "ADBE,NFLX,ORCL,QCOM,CSCO,PYPL,SHOP,UBER,SQ,COIN,"
    "PLTR,SNOW,DDOG,NET,MDB,CRWD,ZS,OKTA,ARM,MRVL"
)


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


def train(
    symbols: list[str],
    epochs: int = 50,
    lr: float = 1e-3,
    seed: int = 0,
    patience: int = 7,
) -> dict:
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

    best_loss = math.inf
    best_state = copy.deepcopy(model.state_dict())
    no_improve = 0
    stopped_at = epochs

    for epoch in range(epochs):
        model.train()
        opt.zero_grad()
        preds = model(X_tr)
        loss = loss_fn(preds, y_tr)
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            if len(X_te) > 0:
                te_preds = model(X_te)
                te_loss = loss_fn(te_preds, y_te).item()
                te_acc = ((te_preds > 0.5).float() == y_te).float().mean().item()
            else:
                te_loss, te_acc = float("nan"), float("nan")

        log_every = max(1, epochs // 10)
        if (epoch + 1) % log_every == 0 or epoch == 0:
            print(
                f"epoch {epoch+1:3d}/{epochs}  "
                f"train_loss={loss.item():.4f}  "
                f"test_loss={te_loss:.4f}  "
                f"test_acc={te_acc:.3f}"
            )

        if te_loss < best_loss:
            best_loss = te_loss
            best_state = copy.deepcopy(model.state_dict())
            no_improve = 0
        else:
            no_improve += 1
            if patience > 0 and no_improve >= patience:
                print(f"early stop at epoch {epoch+1} (no improvement for {patience} epochs)")
                stopped_at = epoch + 1
                break

    model.load_state_dict(best_state)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": best_state,
            "symbols": symbols,
            "epochs_run": stopped_at,
            "best_test_loss": best_loss,
            "n_train": len(train_idx),
            "n_test": len(test_idx),
        },
        CHECKPOINT_PATH,
    )
    print(f"saved best checkpoint (test_loss={best_loss:.4f}) to {CHECKPOINT_PATH}")
    return {
        "checkpoint": str(CHECKPOINT_PATH),
        "epochs_run": stopped_at,
        "best_test_loss": best_loss,
        "n_train": len(train_idx),
        "n_test": len(test_idx),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--symbols",
        default=DEFAULT_SYMBOLS,
        help="Comma-separated ticker list (default: 30 large-cap tech/growth names).",
    )
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--patience",
        type=int,
        default=7,
        help="Early-stop after this many epochs with no test-loss improvement. 0 = disabled.",
    )
    args = p.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    train(symbols, epochs=args.epochs, lr=args.lr, seed=args.seed, patience=args.patience)


if __name__ == "__main__":
    main()
