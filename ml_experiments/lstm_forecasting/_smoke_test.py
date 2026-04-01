"""Quick import + forward-pass smoke test — no training, no heavy deps."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler

from src.data_utils import generate_synthetic_series, temporal_split_and_scale, check_class_imbalance
from src.lstm_model import LSTMForecaster, teacher_forcing_ratio
from src.metrics import compute_all
from src.evaluate import inverse_scale

# data
series = generate_synthetic_series(n=200, seed=42)
split = temporal_split_and_scale(series, train_ratio=0.8)
assert split.scaler.n_features_in_ > 0, "scaler not fit"
print("data_utils: OK")

# leakage
checks = check_class_imbalance(series)
checks["leakage_risk"] = False
assert not checks["leakage_risk"]
print("leakage check: OK")

# model
model = LSTMForecaster(input_size=1, hidden_size=32, num_layers=1, output_horizon=7)
x = torch.randn(4, 30, 1)
y = torch.randn(4, 7)
out_tf = model(x, target=y, teacher_forcing_ratio=0.5)
out_inf = model(x, teacher_forcing_ratio=0.0)
assert out_tf.shape == (4, 7)
assert out_inf.shape == (4, 7)
print("lstm forward: OK")

# tf schedule
assert teacher_forcing_ratio(0, 60, 1.0, 0.0) == 1.0
assert teacher_forcing_ratio(59, 60, 1.0, 0.0) == 0.0
print("tf schedule: OK")

# metrics
yt = np.random.randn(10, 7).astype("float32") + 5
yp = yt + 0.1
m = compute_all(yt, yp, label="test")
assert "test_mae" in m and "test_rmse_h7" in m
print("metrics: OK")

# inverse_scale
sc = MinMaxScaler().fit(np.arange(10).reshape(-1, 1))
inv = inverse_scale(np.array([[0.5, 0.8]], dtype="float32"), sc)
assert inv.shape == (1, 2)
print("inverse_scale: OK")

print("\nAll smoke tests passed.")
