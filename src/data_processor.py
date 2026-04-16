"""
data_processor.py
-----------------
Cleans, transforms, and enriches the raw indicator data.
Produces analysis-ready DataFrames for the dashboard.
"""

import logging

import numpy as np
import pandas as pd
from typing import Tuple

logger = logging.getLogger(__name__)


# ── Cleaning ──────────────────────────────────────────────────────────────────

def clean_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing values and obvious outliers.
    Strategy:
      1. Linear interpolation for internal gaps ≤ 2 years.
      2. Forward-fill for trailing NaNs (most-recent year sometimes missing).
      3. Backward-fill for leading NaNs (some indicators begin mid-series,
         e.g. financial inclusion data starts 2011).
    """
    df = df.copy()

    for col in df.columns:
        # Fill internal gaps via linear interpolation
        df[col] = df[col].interpolate(method="linear", limit=2)
        # Fill trailing NaNs forward
        df[col] = df[col].ffill(limit=1)
        # Fill leading NaNs backward (bfill) — avoid silent NaN propagation
        if df[col].isna().any():
            leading = int(df[col].isna()[::-1].cumprod()[::-1].sum())
            if leading > 0:
                df[col] = df[col].bfill(limit=2)
                logger.debug(f"{col}: {leading} leading NaN(s) back-filled")

    return df


# ── Derived Metrics ───────────────────────────────────────────────────────────

def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add computed columns useful for dashboard insights."""
    df = df.copy()

    if "exports_pct_gdp" in df.columns and "imports_pct_gdp" in df.columns:
        df["trade_balance_pct_gdp"] = df["exports_pct_gdp"] - df["imports_pct_gdp"]

    if "gdp_usd" in df.columns:
        df["gdp_billion_usd"] = df["gdp_usd"] / 1e9

    if "gdp_per_capita_usd" in df.columns:
        df["gdp_per_capita_growth_pct"] = df["gdp_per_capita_usd"].pct_change() * 100

    if "tax_revenue_pct_gdp" in df.columns and "govt_debt_pct_gdp" in df.columns:
        df["debt_to_revenue_ratio"] = (
            df["govt_debt_pct_gdp"] / df["tax_revenue_pct_gdp"]
        )

    if "gdp_growth_pct" in df.columns:
        df["gdp_growth_3yr_avg"] = (
            df["gdp_growth_pct"].rolling(3, min_periods=2).mean()
        )

    return df


# ── YoY & Period Analysis ─────────────────────────────────────────────────────

def compute_yoy_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Add year-over-year absolute and percentage changes."""
    df = df.copy()
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        df[f"{col}_yoy_abs"] = df[col].diff()
        df[f"{col}_yoy_pct"] = df[col].pct_change() * 100

    return df


def get_summary_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Return descriptive statistics for the dashboard's summary panel."""
    numeric_df = df.select_dtypes(include=[np.number])
    stats = numeric_df.describe().T
    stats["latest"]  = numeric_df.iloc[-1]
    stats["5yr_avg"] = numeric_df.tail(5).mean()
    stats["trend"]   = np.where(
        numeric_df.tail(3).mean() > numeric_df.tail(6).head(3).mean(),
        "↑", "↓"
    )
    return stats


# ── Crisis Period Annotations ─────────────────────────────────────────────────

KENYA_EVENTS = [
    {"year": 2007, "label": "Post-Election Violence"},
    {"year": 2008, "label": "Global Financial Crisis"},
    {"year": 2011, "label": "Drought / East Africa Famine"},
    {"year": 2017, "label": "Election Uncertainty"},
    {"year": 2020, "label": "COVID-19 Pandemic"},
    {"year": 2022, "label": "Drought + Debt Pressures"},
    {"year": 2023, "label": "Finance Bill Protests"},
]


def get_event_annotations() -> list:
    return [
        {
            "x":          event["year"],
            "yref":       "paper",
            "y":          1.05,
            "text":       event["label"],
            "showarrow":  True,
            "arrowhead":  2,
            "arrowcolor": "#FF6B6B",
            "font":       {"size": 9, "color": "#FF6B6B"},
            "textangle":  -45,
        }
        for event in KENYA_EVENTS
    ]


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────

def run_pipeline(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full processing pipeline.

    Returns
    -------
    processed_df : pd.DataFrame — analysis-ready data with all derived metrics.
    summary_df   : pd.DataFrame — summary statistics table.
    """
    df      = clean_indicators(raw_df)
    df      = add_derived_metrics(df)
    df      = compute_yoy_changes(df)
    summary = get_summary_stats(df)
    return df, summary
