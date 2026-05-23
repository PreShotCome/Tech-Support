"""XGBoost direction classifier.

Predicts P(forward log return > 0) over a fixed horizon. The strategy
side turns that probability into a position via a threshold + optional
linear scaling.

Why XGBoost not deep learning:
  - Tabular features with mostly local interactions — exactly where
    gradient-boosted trees match or beat neural nets.
  - Trains in seconds on CPU.
  - Predictions are microseconds — no GPU dependency for live.
  - Interpretable via feature importance; easier to debug.

If XGBoost plateaus and we have a strong reason to believe there's
sequence structure being missed, *then* an LSTM or small transformer
is worth trying.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss


@dataclass
class XgbConfig:
    n_estimators: int = 400
    max_depth: int = 5
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: float = 1.0
    reg_lambda: float = 1.0
    reg_alpha: float = 0.0
    early_stopping_rounds: Optional[int] = 30
    random_state: int = 42


@dataclass
class XgbDirectionModel:
    horizon: int                   # bars ahead the model predicts
    feature_names: list[str] = field(default_factory=list)
    config: XgbConfig = field(default_factory=XgbConfig)
    booster: object = None         # xgboost.Booster after fit

    # ------------------------------------------------------------------ train
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> dict:
        import xgboost as xgb

        self.feature_names = list(X_train.columns)
        dtrain = xgb.DMatrix(X_train.values, label=y_train.values,
                             feature_names=self.feature_names)
        evals = [(dtrain, "train")]
        dval = None
        if X_val is not None and y_val is not None and len(X_val) > 0:
            dval = xgb.DMatrix(X_val.values, label=y_val.values,
                               feature_names=self.feature_names)
            evals.append((dval, "val"))

        params = {
            "objective": "binary:logistic",
            "eval_metric": ["logloss", "auc"],
            "max_depth": self.config.max_depth,
            "learning_rate": self.config.learning_rate,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "min_child_weight": self.config.min_child_weight,
            "reg_lambda": self.config.reg_lambda,
            "reg_alpha": self.config.reg_alpha,
            "seed": self.config.random_state,
            "verbosity": 0,
        }

        es = self.config.early_stopping_rounds if dval is not None else None
        self.booster = xgb.train(
            params,
            dtrain,
            num_boost_round=self.config.n_estimators,
            evals=evals,
            early_stopping_rounds=es,
            verbose_eval=False,
        )

        # Hold-out metrics if we have a val set
        report = {"n_train": len(X_train)}
        if dval is not None:
            p_val = self.predict_proba(X_val)
            report.update({
                "n_val": len(X_val),
                "val_logloss": float(log_loss(y_val.values, p_val.clip(1e-6, 1 - 1e-6))),
                "val_auc": float(roc_auc_score(y_val.values, p_val))
                            if len(np.unique(y_val.values)) > 1 else float("nan"),
                "best_iteration": int(getattr(self.booster, "best_iteration", -1)),
            })
        return report

    # ----------------------------------------------------------------- infer
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        import xgboost as xgb
        if self.booster is None:
            raise RuntimeError("Model not trained")
        d = xgb.DMatrix(X.values, feature_names=self.feature_names)
        return self.booster.predict(d)

    # ----------------------------------------------------------------- io
    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.booster is None:
            raise RuntimeError("Model not trained")
        # XGBoost native JSON for the booster, sidecar JSON for our metadata.
        self.booster.save_model(str(path.with_suffix(".xgb.json")))
        path.with_suffix(".meta.json").write_text(json.dumps({
            "horizon": self.horizon,
            "feature_names": self.feature_names,
            "config": self.config.__dict__,
        }, indent=2))

    @classmethod
    def load(cls, path: Path) -> "XgbDirectionModel":
        import xgboost as xgb
        path = Path(path)
        meta = json.loads(path.with_suffix(".meta.json").read_text())
        booster = xgb.Booster()
        booster.load_model(str(path.with_suffix(".xgb.json")))
        return cls(
            horizon=meta["horizon"],
            feature_names=meta["feature_names"],
            config=XgbConfig(**meta["config"]),
            booster=booster,
        )
