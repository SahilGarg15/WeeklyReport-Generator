"""
src/anomaly_detection.py
─────────────────────────
Statistical anomaly detection for weekly business metrics.

Detection methods
──────────────────
1. Z-score  — flags any week where |z| > threshold (default 2.0)
2. Spike    — week-over-week increase > spike_pct_threshold (default +20%)
3. Drop     — week-over-week drop    < drop_pct_threshold  (default -15%)
4. Trend deviation — value deviates significantly from its 3-week moving average

Returns a structured AnomalyReport used by both the LLM prompt and PDF report.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Anomaly:
    week: int
    metric: str
    kind: str           # "z_score" | "spike" | "drop" | "trend_deviation"
    value: float
    z_score: float | None
    description: str


@dataclass
class AnomalyReport:
    anomalies: list[Anomaly] = field(default_factory=list)
    checked_metrics: list[str] = field(default_factory=list)
    total_weeks: int = 0

    @property
    def has_anomalies(self) -> bool:
        return len(self.anomalies) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_anomalies": len(self.anomalies),
            "checked_metrics": self.checked_metrics,
            "anomalies": [
                {
                    "week": a.week,
                    "metric": a.metric,
                    "kind": a.kind,
                    "value": a.value,
                    "z_score": a.z_score,
                    "description": a.description,
                }
                for a in self.anomalies
            ],
        }

    def summary_lines(self) -> list[str]:
        if not self.anomalies:
            return ["No anomalies detected across all metrics."]
        return [f"Week {a.week} — {a.metric}: {a.description}" for a in self.anomalies]


class AnomalyDetector:
    """
    Detects anomalies in a weekly metrics DataFrame.

    Usage
    ──────
        detector = AnomalyDetector(df)
        report = detector.detect()
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df.copy()
        from src.config import cfg
        anomaly_cfg = cfg.get("anomaly", {})
        self._z_threshold: float = float(anomaly_cfg.get("z_score_threshold", 2.0))
        self._spike_pct: float = float(anomaly_cfg.get("spike_pct_threshold", 20.0))
        self._drop_pct: float = float(anomaly_cfg.get("drop_pct_threshold", -15.0))

    def detect(self, metrics: list[str] | None = None) -> AnomalyReport:
        """
        Run all detection passes on the specified metrics.

        Parameters
        ──────────
        metrics : list[str] | None
            Column names to check. Defaults to ["revenue", "users"].
        """
        if metrics is None:
            metrics = ["revenue", "users"]

        report = AnomalyReport(
            checked_metrics=metrics,
            total_weeks=len(self._df),
        )

        for metric in metrics:
            if metric not in self._df.columns:
                logger.warning(f"Metric '{metric}' not found in DataFrame; skipping.")
                continue
            self._z_score_check(metric, report)
            self._spike_drop_check(metric, report)
            self._trend_deviation_check(metric, report)

        # Also flag churn volatility if present
        if "churn" in self._df.columns:
            self._churn_volatility_check(report)

        if report.has_anomalies:
            logger.warning(f"Anomaly detection: {len(report.anomalies)} anomaly(ies) found.")
        else:
            logger.info("Anomaly detection: no anomalies found.")

        return report

    # ── Detection methods ─────────────────────────────────────────

    def _z_score_check(self, metric: str, report: AnomalyReport) -> None:
        series = self._df[metric].astype(float)
        mean = series.mean()
        std = series.std()
        if std == 0:
            return
        z_scores = (series - mean) / std
        for idx, (z, val) in enumerate(zip(z_scores, series)):
            if abs(z) > self._z_threshold:
                week = int(self._df.iloc[idx]["week"])
                direction = "above" if z > 0 else "below"
                report.anomalies.append(Anomaly(
                    week=week,
                    metric=metric,
                    kind="z_score",
                    value=round(float(val), 2),
                    z_score=round(float(z), 3),
                    description=(
                        f"{metric} = {val:,.2f} is {abs(z):.2f}σ {direction} average "
                        f"(mean={mean:,.2f})"
                    ),
                ))

    def _spike_drop_check(self, metric: str, report: AnomalyReport) -> None:
        series = self._df[metric].astype(float)
        prev = series.shift(1)
        pct_change = ((series - prev) / prev.abs() * 100).fillna(0)
        for idx in range(1, len(self._df)):
            pct = float(pct_change.iloc[idx])
            val = float(series.iloc[idx])
            week = int(self._df.iloc[idx]["week"])
            if pct >= self._spike_pct:
                report.anomalies.append(Anomaly(
                    week=week,
                    metric=metric,
                    kind="spike",
                    value=round(val, 2),
                    z_score=None,
                    description=f"{metric} spiked +{pct:.1f}% vs prior week",
                ))
            elif pct <= self._drop_pct:
                report.anomalies.append(Anomaly(
                    week=week,
                    metric=metric,
                    kind="drop",
                    value=round(val, 2),
                    z_score=None,
                    description=f"{metric} dropped {pct:.1f}% vs prior week",
                ))

    def _trend_deviation_check(self, metric: str, report: AnomalyReport) -> None:
        series = self._df[metric].astype(float)
        ma3 = series.rolling(3).mean()
        std = series.std()
        if std == 0:
            return
        for idx in range(3, len(self._df)):
            val = float(series.iloc[idx])
            avg = float(ma3.iloc[idx])
            if abs(val - avg) > 1.5 * std:
                week = int(self._df.iloc[idx]["week"])
                report.anomalies.append(Anomaly(
                    week=week,
                    metric=metric,
                    kind="trend_deviation",
                    value=round(val, 2),
                    z_score=None,
                    description=(
                        f"{metric} ({val:,.2f}) deviates significantly from "
                        f"3-week MA ({avg:,.2f})"
                    ),
                ))

    def _churn_volatility_check(self, report: AnomalyReport) -> None:
        churn = self._df["churn"].astype(float)
        std = churn.std()
        for idx in range(1, len(self._df)):
            delta = float(churn.iloc[idx] - churn.iloc[idx - 1])
            if abs(delta) > std:
                week = int(self._df.iloc[idx]["week"])
                direction = "increased" if delta > 0 else "decreased"
                report.anomalies.append(Anomaly(
                    week=week,
                    metric="churn",
                    kind="spike" if delta > 0 else "drop",
                    value=round(float(churn.iloc[idx]) * 100, 2),
                    z_score=None,
                    description=(
                        f"Churn {direction} sharply by {abs(delta) * 100:.2f}pp "
                        f"to {churn.iloc[idx] * 100:.2f}%"
                    ),
                ))
