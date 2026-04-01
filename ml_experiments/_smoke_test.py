"""Quick smoke test for the feature pipeline — not part of the test suite."""
import sys
sys.path.insert(0, 'ml_experiments/src')

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from feature_pipeline import build_feature_pipeline

rng = np.random.default_rng(0)
n = 400

df = pd.DataFrame({
    'age':    rng.integers(18, 80, n).astype(float),
    'income': rng.lognormal(10, 1, n),
    'region': rng.choice(['north', 'south', 'east', 'west'], n),
    'city':   rng.choice([f'city_{i}' for i in range(30)], n),
})
df.loc[rng.random(n) < 0.10, 'age'] = float('nan')
df.loc[rng.random(n) < 0.08, 'region'] = None
y = rng.integers(0, 2, n)

X_train, X_test, y_train, y_test = train_test_split(
    df, y, test_size=0.2, stratify=y, random_state=42
)

ct = build_feature_pipeline(
    numeric_cols=['age', 'income'],
    ohe_cols=['region'],
    target_enc_cols=['city'],
    numeric_strategy='median',
)

ct.fit(X_train, y_train)           # fit on train only
out_train = ct.transform(X_train)
out_test  = ct.transform(X_test)   # no re-fit — leakage-safe

print(f"Transformers: {[t[0] for t in ct.transformers]}")
print(f"Train transformed: {out_train.shape}")
print(f"Test  transformed: {out_test.shape}")
assert not np.isnan(out_train).any(), "NaN in train output"
assert not np.isnan(out_test).any(),  "NaN in test output"
print("All assertions passed.")
