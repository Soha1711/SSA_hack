"""
baseline.py - Baseline forecasting models for GGCL quarterly CNG volume.

Provides rolling-origin (expanding window) one-step-ahead benchmarks:
1. Naive (lag 1): Predicts the volume of the immediately preceding quarter (y_{t-1}).
2. Seasonal Naive (lag 4): Predicts the volume of the same quarter last year (y_{t-4}).

Both models are strictly causal and never use future information.
"""

from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict[str, float]:
    """Compute MAE, RMSE, and MAPE between actual and predicted values."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    
    if len(actual) == 0:
        raise ValueError("Cannot compute metrics on empty arrays.")
    
    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    mape = float(np.mean(np.abs((actual - predicted) / actual)) * 100.0)
    
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


def load_master_data(master_path: str = "data/processed/quarterly_master.csv") -> pd.DataFrame:
    """Load quarterly master table and extract series with known volume."""
    path = Path(master_path)
    if not path.is_file():
        raise FileNotFoundError(f"Master table not found at {path.resolve()}")
    
    df = pd.read_csv(path)
    return df


def get_test_slices(
    df: pd.DataFrame, n_test_quarters: int = 10
) -> Tuple[pd.DataFrame, List[int], List[str]]:
    """
    Filter to quarters with known volume and locate the last n test quarters.
    
    Returns:
        known_df: DataFrame of quarters with observed volume
        test_indices: 0-indexed positions in known_df for the test quarters
        test_quarters: List of fiscal quarter strings (e.g. ['Q4 FY24', ...])
    """
    known_df = df.dropna(subset=["cng_volume_mmscmd"]).copy().reset_index(drop=True)
    n_known = len(known_df)
    
    if n_known < n_test_quarters + 4:
        raise ValueError(
            f"Not enough historical quarters ({n_known}) to evaluate {n_test_quarters} "
            f"test quarters with seasonal lag-4."
        )
    
    test_indices = list(range(n_known - n_test_quarters, n_known))
    test_quarters = known_df.loc[test_indices, "quarter"].tolist()
    
    return known_df, test_indices, test_quarters


def run_baselines(
    master_path: str = "data/processed/quarterly_master.csv", n_test: int = 10
) -> pd.DataFrame:
    """
    Execute rolling-origin one-step-ahead forecasts for Naive and Seasonal Naive.
    
    Returns a DataFrame with columns:
        quarter, actual, naive_pred, seasonal_naive_pred
    """
    df = load_master_data(master_path)
    known_df, test_indices, test_quarters = get_test_slices(df, n_test_quarters=n_test)
    
    actuals = known_df.loc[test_indices, "cng_volume_mmscmd"].values
    
    # 1. Naive: y_{t-1}
    naive_preds = [known_df.loc[t - 1, "cng_volume_mmscmd"] for t in test_indices]
    
    # 2. Seasonal Naive: y_{t-4}
    snaive_preds = [known_df.loc[t - 4, "cng_volume_mmscmd"] for t in test_indices]
    
    results_df = pd.DataFrame({
        "quarter": test_quarters,
        "actual": actuals,
        "naive_pred": naive_preds,
        "seasonal_naive_pred": snaive_preds,
    })
    
    return results_df


def main():
    print("=" * 60)
    print("BASELINE FORECAST EVALUATION (PS000002)")
    print("=" * 60)
    
    results_df = run_baselines()
    actuals = results_df["actual"].values
    naive_preds = results_df["naive_pred"].values
    snaive_preds = results_df["seasonal_naive_pred"].values
    
    m_naive = compute_metrics(actuals, naive_preds)
    m_snaive = compute_metrics(actuals, snaive_preds)
    
    print("\nQuarter-by-Quarter Forecasts (mmscmd):")
    print(results_df.to_string(index=False))
    
    print("\nBaseline Error Summary (Last 10 Quarters):")
    summary = pd.DataFrame([
        {"Model": "Naive (lag 1)", **m_naive},
        {"Model": "Seasonal Naive (lag 4)", **m_snaive},
    ])
    print(summary.to_string(index=False))
    print("=" * 60)


if __name__ == "__main__":
    main()
