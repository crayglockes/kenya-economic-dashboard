"""
data_fetcher.py
---------------
Fetches Kenyan economic indicators directly from the World Bank REST API v2.

Fallback chain (most to least fresh):
  1. Valid parquet cache (< 24h)       — fastest, no network
  2. Live API fetch + write new cache  — current data
  3. Stale parquet cache (> 24h)       — API was down, serve what we have
  4. Bundled CSV committed to repo     — last resort, committed at build time
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
# for Kenya at country level. Returns empty list, not an error.
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

    Returns a Series with an INTEGER year index, or None if the fetch
    fails or the indicator has no data for Kenya.

    Index type is enforced as int here — not left to the caller —
    because a string year index causes df.loc[2005:2023] to silently
    return an empty DataFrame, producing blank charts.
    """
    url = (
        f"{WB_BASE_URL}/country/{COUNTRY_CODE}/indicator/{indicator}"
        f"?format=json&date={START_YEAR}:{END_YEAR}&per_page=100"
    )

    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            try:
                payload = resp.json()
            except ValueError as e:
                raise ValueError(
                    f"Could not parse JSON for {indicator}. "
                    f"Raw response (first 200 chars): {resp.text[:200]}"
                ) from e

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
                        # int() here is the critical step — ensures integer
                        # year keys so loc-based slicing in the dashboard works
                        records[int(year_raw)] = float(value)
                    except (ValueError, TypeError):
                        pass

            if not records:
                logger.warning(f"All values null for {indicator} ({col_name})")
                return None

            full_index = range(START_YEAR, END_YEAR + 1)
            series = pd.Series(records, name=col_name).reindex(full_index)
            series.index = series.index.astype(int)   # belt-and-suspenders
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
    """True only if cache exists AND is younger than CACHE_TTL_HOURS."""
    meta_path = _metadata_path()
    if not meta_path.exists() or not _cache_path().exists():
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


def _load_parquet(path: Path) -> pd.DataFrame:
    """
    Load a parquet file and enforce integer year index.

    This is the single place where parquet is read — enforcing int index
    here means every code path (valid cache, stale cache) gets the right type.
    """
    df = pd.read_parquet(path)
    df.index = df.index.astype(int)
    df.index.name = "year"
    return df


def _load_stale_cache() -> Optional[pd.DataFrame]:
    """
    Load the parquet cache regardless of age.

    Used as a fallback when the live API is unreachable. Stale data is
    always fresher than the bundled CSV committed at build time.
    """
    cache = _cache_path()
    if not cache.exists():
        return None
    try:
        df = _load_parquet(cache)
        logger.warning(
            "⚠️  Serving STALE cache (API unreachable). "
            "Data may be up to several days old. "
            "Cache will refresh automatically on next successful API call."
        )
        return df
    except Exception as e:
        logger.error(f"Could not load stale cache: {e}")
        return None


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
    Return a DataFrame of all indicators indexed by integer year.

    Fallback chain:
      1. Valid parquet cache (< 24h old)  → return immediately
      2. Live API fetch                   → write new cache, return
      3. Stale parquet cache (any age)    → return with warning
      4. Bundled CSV from repo            → return with warning
      5. RuntimeError                     → nothing worked

    The stale-cache tier (step 3) is the critical addition: it ensures
    the dashboard stays functional across API outages that outlast the
    24-hour cache TTL, which is the failure mode seen in deployment.
    """
    cache = _cache_path()

    # ── Tier 1: valid cache ────────────────────────────────────────────────
    if not force_refresh and _is_cache_valid():
        logger.info("Loading from valid parquet cache...")
        return _load_parquet(cache)

    # ── Tier 2: live API fetch ─────────────────────────────────────────────
    logger.info(f"Fetching {len(INDICATORS)} indicators from World Bank REST API...")
    series_list = []
    failed      = []

    try:
        for wb_code, col_name in INDICATORS.items():
            series = fetch_wb_indicator(wb_code, col_name)
            if series is not None:
                series_list.append(series)
                non_null = series.notna().sum()
                logger.info(f"  ✅ {col_name} ({non_null}/{END_YEAR - START_YEAR + 1} years)")
            else:
                failed.append(wb_code)
                logger.error(f"  ❌ {col_name}")

        if not series_list:
            raise RuntimeError("No indicators fetched successfully from API.")

        df = pd.concat(series_list, axis=1)
        df.index = df.index.astype(int)   # enforce int after concat
        df.index.name = "year"

        df.to_parquet(cache)
        _save_metadata(len(df))
        logger.info(f"✅ Cached {len(df)} rows × {len(df.columns)} columns.")

        if failed:
            logger.warning(f"Failed indicators (NaN columns): {failed}")

        return df

    except Exception as e:
        logger.error(f"Live API fetch failed: {e}")

    # ── Tier 3: stale parquet cache ────────────────────────────────────────
    stale = _load_stale_cache()
    if stale is not None:
        return stale

    # ── Tier 4: bundled CSV committed to repo ─────────────────────────────
    if BUNDLED_DATA_PATH.exists():
        logger.warning("⚠️  Falling back to bundled repo CSV (oldest data source).")
        df = pd.read_csv(BUNDLED_DATA_PATH, index_col="year")
        df.index = df.index.astype(int)   # CSV index may read as int64 or object
        df.index.name = "year"
        return df

    # ── Tier 5: nothing worked ─────────────────────────────────────────────
    raise RuntimeError(
        "All data sources failed: API unreachable, no parquet cache, "
        "and no bundled CSV found at data/raw/bundled_kenya_data.csv. "
        "Run fetch_all_indicators(force_refresh=True) in Colab and commit "
        "the output CSV before redeploying."
    )


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_dataframe(df: pd.DataFrame) -> dict:
    return {
        "shape":         df.shape,
        "index_dtype":   str(df.index.dtype),          # new: confirm int not object
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
