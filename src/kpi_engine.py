"""
src/kpi_engine.py
──────────────────
KPI Computation Engine.

Input : pandas DataFrame with columns [week, revenue, users, churn]
Output: dict of computed metrics ready for the LLM + report modules.

Metrics calculated
───────────────────
• Revenue / user growth % (week-over-week)
• Churn change %
• Moving average (3-week) for revenue and users
• Average Revenue Per User (ARPU)
• Retention rate
• Period totals and peak week
"""

from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class KPIResult:
    # Latest-week identifiers
    current_week: int = 0
    previous_week: int = 0

    # Raw values (latest week)
    revenue: float = 0.0
    users: int = 0
    churn_rate: float = 0.0          # decimal, e.g. 0.05

    # Week-over-week growth
    revenue_growth_pct: float = 0.0
    user_growth_pct: float = 0.0
    churn_change_pct: float = 0.0    # negative = improvement

    # Derived ratios
    arpu: float = 0.0
    retention_rate: float = 0.0
    estimated_churned_users: int = 0

    # Moving averages (3-week)
    revenue_ma3: float = 0.0
    users_ma3: float = 0.0

    # Period summary
    total_revenue: float = 0.0
    avg_weekly_revenue: float = 0.0
    peak_revenue_week: int = 0
    peak_revenue: float = 0.0
    total_weeks: int = 0

    # Trend tags
    revenue_trend: str = "stable"
    user_trend: str = "stable"
    churn_trend: str = "stable"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_payload(self) -> dict[str, str]:
        """Compact JSON-friendly payload for the LLM prompt."""
        def signed(v: float) -> str:
            return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"

        return {
            "week": str(self.current_week),
            "revenue": f"${self.revenue:,.0f}",
            "revenue_growth": signed(self.revenue_growth_pct),
            "users": f"{self.users:,}",
            "user_growth": signed(self.user_growth_pct),
            "churn_rate": f"{self.churn_rate * 100:.2f}%",
            "churn_change": signed(self.churn_change_pct),
            "arpu": f"${self.arpu:.2f}",
            "retention_rate": f"{self.retention_rate * 100:.1f}%",
            "estimated_churned_users": str(self.estimated_churned_users),
            "revenue_ma3": f"${self.revenue_ma3:,.0f}",
            "users_ma3": f"{self.users_ma3:.0f}",
            "peak_revenue_week": str(self.peak_revenue_week),
            "total_revenue": f"${self.total_revenue:,.0f}",
            "revenue_trend": self.revenue_trend,
            "user_trend": self.user_trend,
            "churn_trend": self.churn_trend,
            "total_weeks": str(self.total_weeks),
        }


class KPIEngine:
    """
    Computes all KPIs from a cleaned DataFrame.

    Usage
    ──────
        engine = KPIEngine(df)
        result = engine.compute()
    """

    _TREND_THRESHOLD = 0.01  # 1 % threshold for trend classification

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = self._validate(df.copy())

    # ── Public ────────────────────────────────────────────────────

    def compute(self) -> KPIResult:
        df = self._df
        n = len(df)

        if n < 2:
            raise ValueError("Need at least 2 weeks of data to compute growth KPIs.")

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        r = KPIResult(
            current_week=int(curr["week"]),
            previous_week=int(prev["week"]),
            revenue=float(curr["revenue"]),
            users=int(curr["users"]),
            churn_rate=float(curr["churn"]),
        )

        # Growth
        r.revenue_growth_pct = self._pct_change(prev["revenue"], curr["revenue"])
        r.user_growth_pct = self._pct_change(prev["users"], curr["users"])
        r.churn_change_pct = self._pct_change(prev["churn"], curr["churn"])

        # Derived
        r.arpu = r.revenue / r.users if r.users else 0.0
        r.retention_rate = 1.0 - r.churn_rate
        r.estimated_churned_users = int(r.users * r.churn_rate)

        # Moving averages
        r.revenue_ma3 = float(df["revenue"].tail(3).mean())
        r.users_ma3 = float(df["users"].tail(3).mean())

        # Period summary
        r.total_revenue = float(df["revenue"].sum())
        r.avg_weekly_revenue = float(df["revenue"].mean())
        peak_idx = df["revenue"].idxmax()
        r.peak_revenue_week = int(df.loc[peak_idx, "week"])
        r.peak_revenue = float(df.loc[peak_idx, "revenue"])
        r.total_weeks = n

        # Trends
        r.revenue_trend = self._trend(r.revenue_growth_pct)
        r.user_trend = self._trend(r.user_growth_pct)
        r.churn_trend = (
            "improving" if r.churn_change_pct < -1.0
            else "worsening" if r.churn_change_pct > 1.0
            else "stable"
        )

        logger.info(
            f"KPIs computed — week={r.current_week} "
            f"rev_growth={r.revenue_growth_pct:+.1f}% "
            f"user_growth={r.user_growth_pct:+.1f}% "
            f"churn_Δ={r.churn_change_pct:+.1f}%"
        )
        return r

    def full_summary_df(self) -> pd.DataFrame:
        """Return all weeks with growth columns appended (for CSV report)."""
        df = self._df.copy()
        df["revenue_growth_pct"] = df["revenue"].pct_change() * 100
        df["user_growth_pct"] = df["users"].pct_change() * 100
        df["churn_change_pct"] = df["churn"].pct_change() * 100
        df["arpu"] = df["revenue"] / df["users"]
        df["retention_rate"] = 1 - df["churn"]
        df["revenue_ma3"] = df["revenue"].rolling(3).mean()
        return df.round(4)

    # ── Private ───────────────────────────────────────────────────

    @staticmethod
    def _validate(df: pd.DataFrame) -> pd.DataFrame:
        df.columns = [c.strip().lower() for c in df.columns]
        required = {"week", "revenue", "users", "churn"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")
        df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
        df["users"] = pd.to_numeric(df["users"], errors="coerce").fillna(0).astype(int)
        df["churn"] = pd.to_numeric(df["churn"], errors="coerce").fillna(0)
        # Normalise churn: accept both 0.05 and 5.0 style
        if df["churn"].max() > 1:
            df["churn"] /= 100
        return df

    @staticmethod
    def _pct_change(old: float, new: float) -> float:
        return round((new - old) / abs(old) * 100, 2) if old != 0 else 0.0

    def _trend(self, pct: float) -> str:
        if pct > self._TREND_THRESHOLD * 100:
            return "up"
        if pct < -self._TREND_THRESHOLD * 100:
            return "down"
        return "stable"
