"""
src/trend_analysis.py
──────────────────────
Trend Analysis Module.
Computes metric changes, multi-week trends, and moving averages.
"""

import pandas as pd


def compare_last_weeks(df: pd.DataFrame) -> dict:
    """
    Compare the last week with the previous week.
    Returns the percentage change for revenue and users.
    """
    if len(df) < 2:
        return {"revenue_change": 0.0, "user_change": 0.0}

    last_week = df.iloc[-1]
    prev_week = df.iloc[-2]

    def _safe_pct(new_val, old_val):
        if old_val == 0:
            return 0.0
        return (new_val - old_val) / old_val

    return {
        "revenue_change": _safe_pct(last_week["revenue"], prev_week["revenue"]),
        "user_change": _safe_pct(last_week["users"], prev_week["users"])
    }


def analyze_3_week_trend(df: pd.DataFrame, metric: str = "revenue") -> str:
    """
    Analyzes the trend over the last 3 weeks for a specific metric.
    Returns: 'Upward', 'Downward', or 'Mixed'
    """
    if len(df) < 3:
        return "Not enough data"
        
    w3 = df.iloc[-3][metric]
    w2 = df.iloc[-2][metric]
    w1 = df.iloc[-1][metric]
    
    if w1 > w2 > w3:
        return "Upward"
    elif w1 < w2 < w3:
        return "Downward"
    else:
        return "Mixed"


def calculate_moving_averages(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """
    Calculates moving averages for core metrics.
    """
    df_ma = df.copy()
    df_ma[f"revenue_ma{window}"] = df_ma["revenue"].rolling(window=window, min_periods=1).mean()
    df_ma[f"users_ma{window}"] = df_ma["users"].rolling(window=window, min_periods=1).mean()
    return df_ma
