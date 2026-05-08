import logging
import numpy as np
import pandas as pd
from typing import Tuple

logger = logging.getLogger(__name__)


def clean_indicators(df):
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].interpolate(method="linear", limit=2)
        df[col] = df[col].ffill(limit=1)
        if df[col].isna().any():
            df[col] = df[col].bfill(limit=2)
    return df


def add_derived_metrics(df):
    df = df.copy()
    if "exports_pct_gdp" in df.columns and "imports_pct_gdp" in df.columns:
        df["trade_balance_pct_gdp"] = df["exports_pct_gdp"] - df["imports_pct_gdp"]
    if "gdp_usd" in df.columns:
        df["gdp_billion_usd"] = df["gdp_usd"] / 1e9
    if "gdp_per_capita_usd" in df.columns:
        df["gdp_per_capita_growth_pct"] = df["gdp_per_capita_usd"].pct_change() * 100
    if "tax_revenue_pct_gdp" in df.columns and "govt_debt_pct_gdp" in df.columns:
        df["debt_to_revenue_ratio"] = df["govt_debt_pct_gdp"] / df["tax_revenue_pct_gdp"]
    if "gdp_growth_pct" in df.columns:
        df["gdp_growth_3yr_avg"] = df["gdp_growth_pct"].rolling(3, min_periods=2).mean()
    return df


def compute_yoy_changes(df):
    df = df.copy()
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[f"{col}_yoy_abs"] = df[col].diff()
        df[f"{col}_yoy_pct"] = df[col].pct_change() * 100
    return df


def get_summary_stats(df):
    numeric_df = df.select_dtypes(include=[np.number])
    stats = numeric_df.describe().T
    stats["latest"]  = numeric_df.iloc[-1]
    stats["5yr_avg"] = numeric_df.tail(5).mean()
    stats["trend"]   = np.where(
        numeric_df.tail(3).mean() > numeric_df.tail(6).head(3).mean(), "↑", "↓"
    )
    return stats


KENYA_EVENTS = [
    {"year": 2007, "label": "Post-Election Violence"},
    {"year": 2008, "label": "Global Financial Crisis"},
    {"year": 2011, "label": "Drought / East Africa Famine"},
    {"year": 2017, "label": "Election Uncertainty"},
    {"year": 2020, "label": "COVID-19 Pandemic"},
    {"year": 2022, "label": "Drought + Debt Pressures"},
    {"year": 2023, "label": "Finance Bill Protests"},
]


def get_event_annotations():
    return [
        {
            "x": event["year"], "yref": "paper", "y": 1.05,
            "text": event["label"], "showarrow": True, "arrowhead": 2,
            "arrowcolor": "#FF6B6B",
            "font": {"size": 9, "color": "#FF6B6B"},
            "textangle": -45,
        }
        for event in KENYA_EVENTS
    ]


def run_pipeline(raw_df):
    df      = clean_indicators(raw_df)
    df      = add_derived_metrics(df)
    df      = compute_yoy_changes(df)
    summary = get_summary_stats(df)
    return df, summary
