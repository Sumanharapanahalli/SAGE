"""Quick smoke test — validates all modules work end-to-end on synthetic data."""
import sys
sys.path.insert(0, "src")

import numpy as np
from linear_regression import LinearRegressionGD, StandardScaler, LRScheduler
from utils import evaluate_regression, train_test_split_numpy, check_leakage

np.random.seed(0)
X = np.random.randn(200, 5)
true_w = np.array([3.0, -1.5, 0.5, 2.0, -0.8])
y = X @ true_w + 5.0 + np.random.randn(200) * 0.5

X_tr, X_te, y_tr, y_te = train_test_split_numpy(X, y, test_size=0.2, random_state=42)

scaler = StandardScaler()
X_tr_s = scaler.fit_transform(X_tr)
X_te_s = scaler.transform(X_te)

assert not check_leakage(False)["leakage_risk"], "Leakage check failed"

for sched in ["constant", "step", "exponential", "cosine"]:
    m = LinearRegressionGD(
        learning_rate=0.1, n_iterations=2000,
        lr_schedule=sched, verbose=False
    )
    m.fit(X_tr_s, y_tr)
    preds = m.predict(X_te_s)
    met = evaluate_regression(y_te, preds)
    print(f"[{sched:12s}] RMSE={met['rmse']:.4f} R2={met['r2']:.4f} "
          f"iters={m.n_iter_actual_} converged={m.converged_at_ is not None}")

print("\nAll smoke tests PASSED")
