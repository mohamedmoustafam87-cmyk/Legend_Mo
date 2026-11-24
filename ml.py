"""
ml.py
=====
نموذج إحصائي خفيف (Logistic Regression بـ numpy فقط - بدون sklearn) يعمل كـ Meta-Labeling
(López de Prado): بعد ما الـ Setup يطلع إشارة، النموذج يقدّر احتمال نجاح الصفقة
(تحقق ربح صافٍ بعد التكلفة ضمن حواجز الـ Triple Barrier).

النموذج ما بيُستخدم في البوت إلا لو عدّى اختبار out-of-sample في backtest.py.
"""

import json
import os

import numpy as np
import pandas as pd

from config import MODEL_STATS_FILE


# ==========================================================
# Math
# ==========================================================

def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def fit_logistic(X, y, l2=5.0, iters=40):
    n, k = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(k + 1)
    reg = np.eye(k + 1) * l2
    reg[0, 0] = 0.0

    for _ in range(iters):
        p = _sigmoid(Xb @ w)
        grad = Xb.T @ (p - y) + reg @ w
        hess = (Xb.T * (p * (1 - p))) @ Xb + reg + 1e-6 * np.eye(k + 1)
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < 1e-7:
            break

    return w


def auc(y, p):
    y = np.asarray(y)
    p = np.asarray(p)
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = pd.Series(p).rank().to_numpy()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


# ==========================================================
# Model
# ==========================================================

class MetaModel:

    def __init__(self, columns, fill, lo, hi, mean, std, coef, intercept):
        self.columns = list(columns)
        self.fill = np.asarray(fill, float)
        self.lo = np.asarray(lo, float)
        self.hi = np.asarray(hi, float)
        self.mean = np.asarray(mean, float)
        self.std = np.asarray(std, float)
        self.coef = np.asarray(coef, float)
        self.intercept = float(intercept)

    def _prep(self, X):
        A = X[self.columns].to_numpy(float).copy()
        mask = np.isnan(A)
        A[mask] = np.take(self.fill, np.where(mask)[1])
        A = np.clip(A, self.lo, self.hi)
        return (A - self.mean) / self.std

    @classmethod
    def fit(cls, X, y, l2=5.0):
        cols = list(X.columns)
        A = X.to_numpy(float)
        fill = np.nanmedian(A, axis=0)
        fill = np.where(np.isnan(fill), 0.0, fill)
        mask = np.isnan(A)
        A = A.copy()
        A[mask] = np.take(fill, np.where(mask)[1])
        lo = np.percentile(A, 1, axis=0)
        hi = np.percentile(A, 99, axis=0)
        A = np.clip(A, lo, hi)
        mean = A.mean(axis=0)
        std = A.std(axis=0)
        std = np.where(std < 1e-9, 1.0, std)
        w = fit_logistic((A - mean) / std, np.asarray(y, float), l2=l2)
        return cls(cols, fill, lo, hi, mean, std, w[1:], w[0])

    def predict(self, X):
        z = self._prep(X) @ self.coef + self.intercept
        return _sigmoid(z)

    def to_dict(self):
        return {
            "columns": self.columns,
            "fill": self.fill.tolist(),
            "lo": self.lo.tolist(),
            "hi": self.hi.tolist(),
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "coef": self.coef.tolist(),
            "intercept": self.intercept,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            d["columns"], d["fill"], d["lo"], d["hi"],
            d["mean"], d["std"], d["coef"], d["intercept"],
        )


# ==========================================================
# JSON helpers + cached loaders
# ==========================================================

def clean_json(obj):
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if (np.isnan(obj) or np.isinf(obj)) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


_CACHE = {"path": None, "mtime": None, "stats": None, "model": None}


def load_model_stats(path=None):
    """يرجع نتائج الـ backtest المحفوظة أو None لو مفيش."""
    path = path or MODEL_STATS_FILE

    if not os.path.exists(path):
        _CACHE.update(path=path, mtime=None, stats=None, model=None)
        return None

    mtime = os.path.getmtime(path)

    if _CACHE["path"] == path and _CACHE["mtime"] == mtime:
        return _CACHE["stats"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except (OSError, ValueError):
        _CACHE.update(path=path, mtime=mtime, stats=None, model=None)
        return None
    if not isinstance(stats, dict):
        _CACHE.update(path=path, mtime=mtime, stats=None, model=None)
        return None

    model = None
    meta = stats.get("meta") or {}
    if meta.get("validated") and meta.get("model"):
        try:
            model = MetaModel.from_dict(meta["model"])
        except (KeyError, ValueError):
            model = None

    _CACHE.update(path=path, mtime=mtime, stats=stats, model=model)
    return stats


def get_meta_model():
    load_model_stats()
    return _CACHE["model"]
