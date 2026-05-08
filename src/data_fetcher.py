import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

COUNTRY_CODE = "KE"
START_YEAR   = 2000
END_YEAR     = datetime.now().year - 1
WB_BASE_URL  = "https://api.worldbank.org/v2"

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

CACHE_DIR         = Path("data/processed")
CACHE_TTL_HOURS   = 24
BUNDLED_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "raw" / "bundled_kenya_data.csv"
)


def _nan_series(col_name):
    full_index = range(START_YEAR, END_YEAR + 1)
    s = pd.Series(float("nan"), index=list(full_index), name=col_name)
    s.index = s.index.astype(int)
    s.index.name = "year"
    return s


def fetch_wb_indicator(indicator, col_name, retries=3, backoff=2.0):
    url = (
        f"{WB_BASE_URL}/country/{COUNTRY_CODE}/indicator/{indicator}"
        f"?format=json&date={START_YEAR}:{END_YEAR}&per_page=100"
    )
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            if not isinstance(payload, list) or len(payload) < 2:
                logger.warning(f"Unexpected response structure for {indicator}")
                return _nan_series(col_name)

            data_list = payload[1]

            if not data_list:
                logger.warning(f"No data returned for {indicator} ({col_name})")
                return _nan_series(col_name)

            records = {}
            for entry in data_list:
                year_raw = entry.get("date")
                value    = entry.get("value")
                if year_raw is not None and value is not None:
                    try:
                        records[int(year_raw)] = float(value)
                    except (ValueError, TypeError):
                        pass

            if not records:
                logger.warning(f"All values null for {indicator} ({col_name})")
                return _nan_series(col_name)

            full_index = range(START_YEAR, END_YEAR + 1)
            s = pd.Series(records, name=col_name).reindex(full_index)
            s.index = s.index.astype(int)
            s.index.name = "year"
            return s.sort_index()

        except requests.exceptions.RequestException as e:
            wait = backoff ** attempt
            logger.warning(f"Attempt {attempt+1}/{retries} failed for {indicator}: {e}. Retrying in {wait:.0f}s...")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"Error fetching {indicator}: {e}")
            return _nan_series(col_name)

    logger.error(f"All retries exhausted for {indicator}")
    return _nan_series(col_name)


def _cache_path():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / "kenya_indicators.parquet"


def _metadata_path():
    return CACHE_DIR / "fetch_metadata.json"


def _is_cache_valid():
    meta_path = _metadata_path()
    if not meta_path.exists() or not _cache_path().exists():
        return False
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        age_hours = (datetime.now() - datetime.fromisoformat(meta["fetched_at"])).total_seconds() / 3600
        logger.info(f"Cache age: {age_hours:.1f}h (TTL: {CACHE_TTL_HOURS}h)")
        return age_hours < CACHE_TTL_HOURS
    except Exception:
        return False


def _load_parquet(path):
    df = pd.read_parquet(path)
    df.index = df.index.astype(int)
    df.index.name = "year"
    return df


def _load_stale_cache():
    cache = _cache_path()
    if not cache.exists():
        return None
    try:
        df = _load_parquet(cache)
        logger.warning("Serving STALE cache — API was unreachable.")
        return df
    except Exception as e:
        logger.error(f"Could not load stale cache: {e}")
        return None


def _save_metadata(row_count):
    with open(_metadata_path(), "w") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "row_count":  row_count,
            "country":    COUNTRY_CODE,
            "year_range": f"{START_YEAR}-{END_YEAR}",
        }, f, indent=2)


def fetch_all_indicators(force_refresh=False):
    cache = _cache_path()

    if not force_refresh and _is_cache_valid():
        logger.info("Loading from valid parquet cache...")
        return _load_parquet(cache)

    logger.info(f"Fetching {len(INDICATORS)} indicators from World Bank REST API...")
    series_list = []
    failed      = []

    try:
        for wb_code, col_name in INDICATORS.items():
            series = fetch_wb_indicator(wb_code, col_name)
            series_list.append(series)
            non_null = series.notna().sum()
            logger.info(f"  {'✅' if non_null > 0 else '⚠️ '} {col_name} ({non_null}/{END_YEAR - START_YEAR + 1} years)")
            if non_null == 0:
                failed.append(wb_code)

        df = pd.concat(series_list, axis=1)
        df.index = df.index.astype(int)
        df.index.name = "year"
        df.to_parquet(cache)
        _save_metadata(len(df))
        logger.info(f"Cached {len(df)} rows x {len(df.columns)} columns.")

        if failed:
            logger.warning(f"All-null indicators (NaN columns in df): {failed}")

        return df

    except Exception as e:
        logger.error(f"Live API fetch failed: {e}")

    stale = _load_stale_cache()
    if stale is not None:
        return stale

    if BUNDLED_DATA_PATH.exists():
        logger.warning("Falling back to bundled repo CSV.")
        df = pd.read_csv(BUNDLED_DATA_PATH, index_col="year")
        df.index = df.index.astype(int)
        df.index.name = "year"
        return df

    raise RuntimeError(
        "All data sources failed. Commit data/raw/bundled_kenya_data.csv before deploying."
    )


def validate_dataframe(df):
    return {
        "shape":         df.shape,
        "index_dtype":   str(df.index.dtype),
        "year_range":    (int(df.index.min()), int(df.index.max())),
        "missing_pct":   round(df.isnull().mean().mean() * 100, 2),
        "complete_rows": int((~df.isnull().any(axis=1)).sum()),
        "columns":       df.columns.tolist(),
    }
