"""
arima_baseline.py — ARIMA baseline for multi-step forecasting.

Uses pmdarima.auto_arima to select order (p,d,q) via AIC, then
re-fits statsmodels ARIMA for full control over the forecast API.

Walk-forward evaluation: for each test window the model is re-fit
on all preceding data to avoid look-ahead — this is the correct
evaluation protocol for ARIMA on a temporal test set.
"""

from __future__ import annotations

import logging
import warnings
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def _try_import_pmdarima():
    try:
        import pmdarima as pm
        return pm
    except ImportError:
        return None


def _try_import_statsmodels():
    try:
        from statsmodels.tsa.arima.model import ARIMA
        return ARIMA
    except ImportError:
        return None


class ARIMABaseline:
    """Walk-forward ARIMA baseline.

    Args:
        max_p, max_d, max_q: Upper bounds for order search.
        information_criterion: "aic" or "bic" for auto_arima.
    """

    def __init__(
        self,
        max_p: int = 5,
        max_d: int = 2,
        max_q: int = 5,
        information_criterion: str = "aic",
    ) -> None:
        self.max_p = max_p
        self.max_d = max_d
        self.max_q = max_q
        self.information_criterion = information_criterion
        self.order_: Tuple[int, int, int] | None = None

    # ------------------------------------------------------------------ #
    # Order selection                                                      #
    # ------------------------------------------------------------------ #

    def select_order(self, train_series: np.ndarray) -> Tuple[int, int, int]:
        """Run auto_arima on training data to pick (p, d, q)."""
        pm = _try_import_pmdarima()
        if pm is None:
            logger.warning("pmdarima not installed — defaulting to ARIMA(2,1,2)")
            self.order_ = (2, 1, 2)
            return self.order_

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = pm.auto_arima(
                train_series,
                max_p=self.max_p,
                max_d=self.max_d,
                max_q=self.max_q,
                information_criterion=self.information_criterion,
                stepwise=True,
                suppress_warnings=True,
                error_action="ignore",
            )
        self.order_ = model.order
        logger.info("auto_arima selected order: %s", self.order_)
        return self.order_

    # ------------------------------------------------------------------ #
    # Walk-forward forecast                                               #
    # ------------------------------------------------------------------ #

    def walk_forward_forecast(
        self,
        full_series: np.ndarray,
        train_size: int,
        lookback: int,
        horizon: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Walk-forward evaluation on the test portion.

        For each test window starting at index i, re-fits ARIMA on
        full_series[:i] and predicts the next `horizon` steps.

        Returns:
            preds:  (n_windows, horizon) float32 array
            actuals: (n_windows, horizon) float32 array
        """
        ARIMA = _try_import_statsmodels()
        if ARIMA is None:
            raise ImportError("statsmodels is required for ARIMA baseline")

        if self.order_ is None:
            self.select_order(full_series[:train_size])

        order = self.order_

        test_start = train_size
        n_test = len(full_series) - test_start - horizon + 1
        if n_test <= 0:
            raise ValueError("Not enough test data for walk-forward evaluation")

        preds, actuals = [], []
        for i in range(n_test):
            history_end = test_start + i
            history = full_series[:history_end]
            actual = full_series[history_end : history_end + horizon]
            if len(actual) < horizon:
                break

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    fitted = ARIMA(history, order=order).fit()
                    forecast = fitted.forecast(steps=horizon)
                except Exception as exc:
                    logger.debug("ARIMA fit failed at window %d: %s", i, exc)
                    forecast = np.full(horizon, history[-1])  # naive fallback

            preds.append(forecast)
            actuals.append(actual)

        logger.info("ARIMA walk-forward: %d windows, order=%s", len(preds), order)
        return np.array(preds, dtype=np.float32), np.array(actuals, dtype=np.float32)

    # ------------------------------------------------------------------ #
    # Quick single-shot forecast (for demo / comparison table)            #
    # ------------------------------------------------------------------ #

    def fit_and_forecast(self, train_series: np.ndarray, horizon: int) -> np.ndarray:
        """Fit on `train_series`, return single `horizon`-step forecast."""
        ARIMA = _try_import_statsmodels()
        if ARIMA is None:
            raise ImportError("statsmodels is required for ARIMA baseline")

        if self.order_ is None:
            self.select_order(train_series)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = ARIMA(train_series, order=self.order_).fit()
            forecast = fitted.forecast(steps=horizon)

        return np.array(forecast, dtype=np.float32)
