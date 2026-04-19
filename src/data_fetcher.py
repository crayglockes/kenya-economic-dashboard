"""
data_fetcher.py
---------------
Fetches Kenyan economic indicators directly from the World Bank REST API v2.
Uses requests — avoids wbgapi JSON decode errors and gives explicit control
over parsing. Handles retries, 24h cache, and bundled CSV fallback.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────────

COUNTRY_CODE = "KE"
START_YEAR   = 2000
END_YEAR     = datetime.now().year - 1
WB_BASE_URL  = "https://api.worldbank.org/v2"

# BX.RES.TOTL.CD (Foreign Reserves) removed — World Bank publishes no data
# for this indicator at the Kenya country level. Attempting to fetch it
# returns an empty list, not an error, causing silent NaN columns.
INDICATORS = {
    "NY.GDP.MKTP.CD":    "gdp_usd",
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
    "NY.GDP.PCAP.CD":    "gdp_per_capita_usd",
    "FP.CPI.TOTL.ZG":    "inflation_pct",
    "NE.EXP.GNFS.ZS":    "exports_pct_gdp",
    "NE.IMP.GNFS.ZS":    "imports_pct_gdp",
    "BN.CAB.XOKA.GD.ZS": "current_account_pct_gdp",
    "GC.DOD.TOTL.GD.ZS": "govt_debt_pct_gdp",
    "GC.TAX.TOTL.GD.ZS": "tax_revenue_pct_gdp",
    "SL.UEM.TOTL.ZS":    "unemployment_pct",
    "SI.POV.DDAY":        "poverty_headcount_pct",
    "DT.DOD.DECT.GN.ZS": "external_debt_pct_gni",
    "FX.OWN.TOTL.ZS":    "financial_inclusion_pct",
}

CACHE_DIR       = Path("data/processed")
CACHE_TTL_HOURS = 24

BUNDLED_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "raw" / "bundled_kenya_data.csv"
)


# ── World Bank REST API ────────────────────────────────────────────────────────

def fetch_wb_indicator(
    indicator: str,
    col_name:  str,
    retries:   int   = 3,
    backoff:   float = 2.0,
) -> Optional[pd.Series]:
    """
    Fetch one indicator from World Bank REST API v2 for Kenya.

    The API returns [metadata_dict, data_list]. Each item in data_list
    has {"date": "2023", "value": 5.2} or {"date": "2023", "value": null}.
    Only non-null values are included in the output Series.

    Returns
    -------
    pd.Series indexed by integer year, or None if the fetch fails or
    the indicator has no data for Kenya.
    """
    url = (
        f"{WB_BASE_URL}/country/{COUNTRY_CODE}/indicator/{indicator}"
        f"?format=json&date={START_YEAR}:{END_YEAR}&per_page=100"
    )

    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            # Explicit JSON parsing with clear error message
            try:
                payload = resp.json()
            except ValueError as e:
                raise ValueError(
                    f"Could not parse JSON for {indicator}. "
                    f"Raw response (first 200 chars): {resp.text[:200]}"
                ) from e

            # World Bank always wraps data as [metadata, data_list]
            if not isinstance(payload, list) or len(payload) < 2:
                logger.warning(
                    f"Unexpected response structure for {indicator}: "
                    f"expected list of 2, got {type(payload)}"
                )
                return None

            data_list = payload[1]
            if not data_list:
                logger.warning(
                    f"No data returned for {indicator} ({col_name}). "
                    f"This indicator may not be published for Kenya."
                )
                return None

            records = {}
            for entry in data_list:
                year_raw = entry.get("date")
                value    = entry.get("value")
                if year_raw is not None and value is not None:
                    try:
                        records[int(year_raw)] = float(value)
                    except (ValueError, TypeError):
                        pass  # skip malformed entries

            if not records:
                logger.warning(f"All values null for {indicator} ({col_name})")
                return None

            series = pd.Series(records, name=col_name)
            series.index.name = "year"
            return series.sort_index()

        except requests.exceptions.RequestException as e:
            wait = backoff ** attempt
            logger.warning(
                f"Attempt {attempt + 1}/{retries} failed for {indicator}: {e}. "
                f"Retrying in {wait:.0f}s..."
            )
            time.sleep(wait)
        except (ValueError, KeyError, IndexError) as e:
            logger.error(f"Parse error for {indicator}: {e}")
            return None

    logger.error(f"All retries exhausted for {indicator}")
    return None


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
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        fetched_at = datetime.fromisoformat(meta["fetched_at"])
        age_hours  = (datetime.now() - fetched_at).total_seconds() / 3600
        logger.info(f"Cache age: {age_hours:.1f}h (TTL: {CACHE_TTL_HOURS}h)")
        return age_hours < CACHE_TTL_HOURS
    except (json.JSONDecodeError, KeyError, ValueError):
        return False


def _save_metadata(row_count: int) -> None:
    with open(_metadata_path(), "w") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "row_count":  row_count,
            "country":    COUNTRY_CODE,
            "year_range": f"{START_YEAR}-{END_YEAR}",
        }, f, indent=2)


# ── Main Fetch ────────────────────────────────────────────────────────────────

def fetch_all_indicators(force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetch all indicators via World Bank REST API v2.

    Falls back to the bundled CSV committed to data/raw/ if the live
    API fails — prevents cold-start 500 errors on Render's ephemeral
    filesystem where the parquet cache is wiped on every spin-up.

    Parameters
    ----------
    force_refresh : bool
        Bypass cache and re-fetch from API.

    Returns
    -------
    pd.DataFrame indexed by year (int), one column per indicator.
    """
    cache = _cache_path()

    if not force_refresh and cache.exists() and _is_cache_valid():
        logger.info("Loading from parquet cache...")
        return pd.read_parquet(cache)

    logger.info(f"Fetching {len(INDICATORS)} indicators from World Bank REST API v2...")
    series_list = []
    failed      = []

    try:
        for wb_code, col_name in INDICATORS.items():
            series = fetch_wb_indicator(wb_code, col_name)
            if series is not None:
                # Reindex to full year range so all series align on concat
                full_index = range(START_YEAR, END_YEAR + 1)
                series = series.reindex(full_index)
                series_list.append(series)
                non_null = series.notna().sum()
                logger.info(f"  ✅ {col_name} ({non_null}/{len(full_index)} years)")
            else:
                failed.append(wb_code)
                logger.error(f"  ❌ {col_name}")

        if not series_list:
            raise RuntimeError("No indicators fetched successfully from API.")

        df = pd.concat(series_list, axis=1)
        df.index.name = "year"
        df.to_parquet(cache)           # requires pyarrow — now in requirements.txt
        _save_metadata(len(df))
        logger.info(f"Cached {len(df)} rows × {len(df.columns)} columns.")

        if failed:
            logger.warning(f"Failed indicators (will be NaN columns): {failed}")

        return df

    except Exception as e:
        logger.error(f"Live API fetch failed: {e}")
        if BUNDLED_DATA_PATH.exists():
            logger.warning("Falling back to bundled repo CSV.")
            return pd.read_csv(BUNDLED_DATA_PATH, index_col="year")
        raise RuntimeError(
            "API unreachable and no bundled data found. "
            "Run fetch_all_indicators(force_refresh=True) in Colab and commit "
            "the output to data/raw/bundled_kenya_data.csv."
        ) from e


# ── Validation ─────────────────────────────────────────────────────────────────

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
    df  = fetch_all_indicators(force_refresh=True)
    out = BUNDLED_DATA_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index_label="year")
    print(f"✅ Bundled CSV written to {out}")
    print("\n=== VALIDATION SUMMARY ===")
    for k, v in validate_dataframe(df).items():
        print(f"  {k}: {v}")
