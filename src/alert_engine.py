"""
src/alert_engine.py
────────────────────
Business Alerts System.
Generates rule-based alerts based on KPI metrics.
"""

import pandas as pd


def generate_alerts(df: pd.DataFrame, kpi_result) -> list[str]:
    """
    Generate business alerts from data and KPIs.
    """
    alerts = []
    
    # Needs at least 2 weeks of data for some checks
    if len(df) < 2:
        return alerts

    # Get metrics
    revenue_change = kpi_result.revenue_growth_pct / 100.0  # Convert back to decimal
    churn = kpi_result.churn_rate
    
    # 1. Revenue Drop Check
    if revenue_change < -0.1:
        alerts.append("🚨 Revenue dropped significantly (>$10% decrease)")

    # 2. Churn Rate Check
    if churn > 0.07:
        alerts.append("🚨 High churn rate detected (>7%)")

    # 3. Retention declining trend (checking if churn increased for 2 consecutive periods implies retention decline)
    if len(df) >= 3:
        churn_w1 = df.iloc[-1]["churn"]
        churn_w2 = df.iloc[-2]["churn"]
        churn_w3 = df.iloc[-3]["churn"]
        
        # If churn is increasing, retention is decreasing
        if churn_w1 > churn_w2 > churn_w3:
            alerts.append("⚠️ Retention declining trend (2 weeks straight)")

    return alerts
