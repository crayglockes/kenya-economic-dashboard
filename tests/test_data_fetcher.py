"""Tests for data pipeline modules."""
import sys
from pathlib import Path
# Anchor to file location — mirrors the fix in dashboard.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
import pandas as pd
import numpy as np

from data_fetcher import validate_dataframe
from data_processor import (
    clean_indicators,
    add_derived_metrics,
    compute_yoy_changes,
    run_pipeline,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df():
    years = range(2010, 2024)
    np.random.seed(42)
    return pd.DataFrame({
        "gdp_growth_pct":          np.random.normal(5, 2, len(years)),
        "inflation_pct":           np.random.normal(7, 3, len(years)),
        "gdp_per_capita_usd":      np.linspace(800, 2100, len(years)),
        "exports_pct_gdp":         np.random.normal(15, 2, len(years)),
        "imports_pct_gdp":         np.random.normal(25, 3, len(years)),
        "govt_debt_pct_gdp":       np.linspace(40, 70, len(years)),
        "tax_revenue_pct_gdp":     np.random.normal(16, 1, len(years)),
        "unemployment_pct":        np.random.normal(11, 2, len(years)),
        "financial_inclusion_pct": np.linspace(40, 79, len(years)),
        "gdp_usd":                 np.linspace(40e9, 110e9, len(years)),
    }, index=list(years))


@pytest.fixture
def df_with_gaps(sample_df):
    df = sample_df.copy()
    df.loc[2015, "inflation_pct"]  = np.nan
    df.loc[2016, "inflation_pct"]  = np.nan
    df.loc[2019, "gdp_growth_pct"] = np.nan
    return df


@pytest.fixture
def df_with_leading_nans(sample_df):
    """Simulates a series that only starts in 2013 (financial inclusion pattern)."""
    df = sample_df.copy()
    df.loc[2010, "financial_inclusion_pct"] = np.nan
    df.loc[2011, "financial_inclusion_pct"] = np.nan
    return df


# ── Validator Tests ───────────────────────────────────────────────────────────

class TestValidateDataframe:
    def test_returns_dict_with_required_keys(self, sample_df):
        result = validate_dataframe(sample_df)
        assert {"shape", "year_range", "missing_pct", "columns"}.issubset(result.keys())

    def test_shape_correct(self, sample_df):
        assert validate_dataframe(sample_df)["shape"] == sample_df.shape

    def test_no_missing_in_clean_df(self, sample_df):
        assert validate_dataframe(sample_df)["missing_pct"] == 0.0

    def test_detects_missing(self, df_with_gaps):
        assert validate_dataframe(df_with_gaps)["missing_pct"] > 0


# ── Processor Tests ───────────────────────────────────────────────────────────

class TestCleanIndicators:
    def test_fills_single_internal_gap(self, df_with_gaps):
        cleaned = clean_indicators(df_with_gaps)
        assert not pd.isna(cleaned.loc[2019, "gdp_growth_pct"])

    def test_does_not_modify_original(self, df_with_gaps):
        clean_indicators(df_with_gaps)
        assert pd.isna(df_with_gaps.loc[2015, "inflation_pct"])

    def test_fills_leading_nans_via_bfill(self, df_with_leading_nans):
        """bfill should handle leading NaNs that interpolate/ffill cannot reach."""
        cleaned = clean_indicators(df_with_leading_nans)
        assert not pd.isna(cleaned.loc[2010, "financial_inclusion_pct"])
        assert not pd.isna(cleaned.loc[2011, "financial_inclusion_pct"])


class TestDerivedMetrics:
    def test_trade_balance_computed(self, sample_df):
        result = add_derived_metrics(sample_df)
        assert "trade_balance_pct_gdp" in result.columns

    def test_trade_balance_values_correct(self, sample_df):
        result   = add_derived_metrics(sample_df)
        expected = sample_df["exports_pct_gdp"] - sample_df["imports_pct_gdp"]
        pd.testing.assert_series_equal(result["trade_balance_pct_gdp"], expected, check_names=False)

    def test_gdp_billions_scaling(self, sample_df):
        result = add_derived_metrics(sample_df)
        assert result["gdp_billion_usd"].iloc[0] == pytest.approx(sample_df["gdp_usd"].iloc[0] / 1e9)

    def test_rolling_avg_length(self, sample_df):
        result = add_derived_metrics(sample_df)
        assert result["gdp_growth_3yr_avg"].notna().sum() >= len(sample_df) - 2


class TestYoYChanges:
    def test_yoy_cols_created(self, sample_df):
        result = compute_yoy_changes(sample_df)
        assert "gdp_growth_pct_yoy_abs" in result.columns
        assert "gdp_growth_pct_yoy_pct" in result.columns

    def test_first_yoy_is_nan(self, sample_df):
        result = compute_yoy_changes(sample_df)
        assert pd.isna(result["gdp_growth_pct_yoy_abs"].iloc[0])


class TestRunPipeline:
    def test_returns_two_dataframes(self, sample_df):
        processed, summary = run_pipeline(sample_df)
        assert isinstance(processed, pd.DataFrame)
        assert isinstance(summary, pd.DataFrame)

    def test_processed_has_more_cols_than_input(self, sample_df):
        processed, _ = run_pipeline(sample_df)
        assert len(processed.columns) > len(sample_df.columns)

    def test_summary_has_latest_column(self, sample_df):
        _, summary = run_pipeline(sample_df)
        assert "latest" in summary.columns
