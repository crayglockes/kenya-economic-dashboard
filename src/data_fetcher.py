"""
data_fetcher.py
---------------
Fetches Kenyan economic indicators from the World Bank API.
Handles retries, caching, bundled fallback data, and validation.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import wbgapi as wb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

COUNTRY_CODE = "KE"
START_YEAR   = 2000
END_YEAR     = datetime.now().year - 1

INDICATORS = {
    "NY.GDP.MKTP.CD":      "gdp_usd",
    "NY.GDP.MKTP.KD.ZG":   "gdp_growth_pct",
    "NY.GDP.PCAP.CD":      "gdp_per_capita_usd",
    "FP.CPI.TOTL.ZG":      "inflation_pct",
    "NE.EXP.GNFS.ZS":      "exports_pct_gdp",
    "NE.IMP.GNFS.ZS":      "imports_pct_gdp",
    "BN.CAB.XOKA.GD.ZS":   "current_account_pct_gdp",
    "GC.DOD.TOTL.GD.ZS":   "govt_debt_pct_gdp",
    "GC.TAX.TOTL.GD.ZS":   "tax_revenue_pct_gdp",
    "SL.UEM.TOTL.ZS":      "unemployment_pct",
    "SI.POV.DDAY":          "poverty_headcount_pct",
    "DT.DOD.DECT.GN.ZS":   "external_debt_pct_gni",
    "BX.RES.TOTL.CD":      "foreign_reserves_usd",
    "FX.OWN.TOTL.ZS":      "financial_inclusion_pct",
}

CACHE_DIR        = Path("data/processed")
CACHE_TTL_HOURS  = 24

# Bundled CSV committed to the repo — used when the API is unreachable
# (Render free tier wipes the filesystem on cold starts; the API can take
# 10–30 s and fail under rate limits, causing 500 errors before the first
# page load). Generate this file once with force_refresh=True then commit it.
BUNDLED_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "raw" / "bundled_kenya_data.csv"
)


# ── Cache Helpers ──────────────────────────────────────────────────────────────

def _cache_path() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / "kenya_indicators.parquet"


def _metadata_path() -> Path:
    return CACHE_DIR / "fetch_metadata.json"


def _is_cache_valid() -> bool:
    meta_path = _metadata_path()
    if not meta_path.exists():
        return False
    with open(meta_path) as f:
        meta = json.load(f)
    fetched_at = datetime.fromisoformat(meta["fetched_at"])
    age_hours  = (datetime.now() - fetched_at).total_seconds() / 3600
    logger.info(f"Cache age: {age_hours:.1f}h (TTL: {CACHE_TTL_HOURS}h)")
    return age_hours < CACHE_TTL_HOURS


def _save_metadata(row_count: int) -> None:
    with open(_metadata_path(), "w") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "row_count":  row_count,
            "country":    COUNTRY_CODE,
            "year_range": f"{START_YEAR}-{END_YEAR}",
        }, f, indent=2)


# ── Fetching ──────────────────────────────────────────────────────────────────

def fetch_single_indicator(
    wb_code:  str,
    col_name: str,
    retries:  int   = 3,
    backoff:  float = 2.0
) -> Optional[pd.Series]:
    """Fetch one indicator for Kenya with retry logic."""
    for attempt in range(retries):
        try:
            df = wb.data.DataFrame(
                wb_code,
                economy=COUNTRY_CODE,
                time=range(START_YEAR, END_YEAR + 1)
            )
            series = df.iloc[:, 0]
            series.name  = col_name
            series.index = (
                series.index.astype(str)
                .str.replace("YR", "")
                .astype(int)
            )
            return series.sort_index()
        except Exception as e:
            wait = backoff ** attempt
            logger.warning(
                f"Attempt {attempt+1}/{retries} failed for {wb_code}: {e}. "
                f"Retrying in {wait:.0f}s..."
            )
            time.sleep(wait)
    logger.error(f"All retries exhausted for {wb_code}")
    return None


def fetch_all_indicators(force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetch all indicators, using cache if available.
    Falls back to the bundled CSV committed to the repo if the API fails —
    this prevents cold-start 500 errors on Render's ephemeral filesystem.

    Parameters
    ----------
    force_refresh : bool
        If True, bypass cache and re-fetch from API.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by year (int) with one column per indicator.
    """
    cache = _cache_path()

    if not force_refresh and cache.exists() and _is_cache_valid():
        logger.info("Loading from cache...")
        return pd.read_parquet(cache)

    logger.info(f"Fetching {len(INDICATORS)} indicators from World Bank API...")
    series_list = []
    failed      = []

    try:
        for wb_code, col_name in INDICATORS.items():
            series = fetch_single_indicator(wb_code, col_name)
            if series is not None:
                series_list.append(series)
                logger.info(f"  ✅ {col_name}")
            else:
                failed.append(wb_code)
                logger.error(f"  ❌ {col_name}")

        df = pd.concat(series_list, axis=1)
        df.index.name = "year"
        df.to_parquet(cache)
        _save_metadata(len(df))
        logger.info(f"Saved {len(df)} rows × {len(df.columns)} columns to cache.")

        if failed:
            logger.warning(f"Failed indicators: {failed}")

        return df

    except Exception as e:
        logger.error(f"Live API fetch failed: {e}")
        if BUNDLED_DATA_PATH.exists():
            logger.warning("Falling back to bundled repo data.")
            return pd.read_csv(BUNDLED_DATA_PATH, index_col="year")
        raise RuntimeError(
            "API unreachable and no bundled data found. "
            "Run fetch_all_indicators(force_refresh=True) in Colab and commit "
            "the output to data/raw/bundled_kenya_data.csv."
        ) from e


# ── Exchange Rate (World Bank) ─────────────────────────────────────────────────

def fetch_kes_usd_rate() -> pd.Series:
    """Fetch USD/KES exchange rate. Returns a Series indexed by year."""
    try:
        df = wb.data.DataFrame(
            "PA.NUS.FCRF",
            economy=COUNTRY_CODE,
            time=range(START_YEAR, END_YEAR + 1)
        )
        series = df.iloc[:, 0]
        series.name  = "kes_per_usd"
        series.index = (
            series.index.astype(str)
            .str.replace("YR", "")
            .astype(int)
        )
        return series.sort_index()
    except Exception as e:
        logger.error(f"Could not fetch exchange rate: {e}")
        return pd.Series(dtype=float, name="kes_per_usd")


# ── Validation ────────────────────────────────────────────────────────────────

def validate_dataframe(df: pd.DataFrame) -> dict:
    """Return a validation summary dict."""
    return {
        "shape":         df.shape,
        "year_range":    (int(df.index.min()), int(df.index.max())),
        "missing_pct":   round(df.isnull().mean().mean() * 100, 2),
        "complete_rows": int((~df.isnull().any(axis=1)).sum()),
        "columns":       df.columns.tolist(),
    }


if __name__ == "__main__":
    # First run: fetch from API, cache, then commit bundled CSV
    df = fetch_all_indicators(force_refresh=True)
    df.to_csv(
        Path(__file__).resolve().parent.parent / "data" / "raw" / "bundled_kenya_data.csv",
        index_label="year"
    )
    print("✅ Bundled CSV written. Commit data/raw/bundled_kenya_data.csv to GitHub.")
    summary = validate_dataframe(df)
    print("\n=== VALIDATION SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
