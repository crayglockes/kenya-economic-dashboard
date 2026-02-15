# ============================================================================
# Kenya Economic Dashboard - Data Collection
# ============================================================================
# Purpose: Fetch economic indicators from World Bank API
# Author: [Your Name]
# Date: [Today's Date]
# ============================================================================

# Load libraries
library(tidyverse)
library(WDI)
library(lubridate)
library(here)

# Set working directory (RStudio Cloud specific)
setwd("~/kenya-economic-dashboard")  # Adjust if needed

# Create output directories if they don't exist
dir.create("data/raw", recursive = TRUE, showWarnings = FALSE)

# ============================================================================
# Define World Bank Indicators
# ============================================================================

indicators <- c(
  "NY.GDP.MKTP.CD"     = "gdp_current_usd",
  "NY.GDP.MKTP.KD.ZG"  = "gdp_growth_annual",
  "FP.CPI.TOTL.ZG"     = "inflation_cpi",
  "SL.UEM.TOTL.ZS"     = "unemployment_total",
  "NE.EXP.GNFS.ZS"     = "exports_pct_gdp",
  "NE.IMP.GNFS.ZS"     = "imports_pct_gdp",
  "GC.TAX.TOTL.GD.ZS"  = "tax_revenue_pct_gdp",
  "DT.DOD.DECT.CD"     = "external_debt_usd",
  "NY.GDP.PCAP.CD"     = "gdp_per_capita_usd",
  "NE.TRD.GNFS.ZS"     = "trade_pct_gdp"
)

# Display indicators for verification
print("Fetching the following indicators:")
print(indicators)

# ============================================================================
# Fetch Data from World Bank API
# ============================================================================

# Fetch Kenya data (2000-2024)
message("Fetching data from World Bank API...")

kenya_raw <- WDI(
  country = "KE",
  indicator = names(indicators),
  start = 2000,
  end = 2024,
  extra = TRUE  # Gets additional metadata
)

message(sprintf("Fetched %d rows", nrow(kenya_raw)))

# Quick inspection
glimpse(kenya_raw)

# ============================================================================
# Clean and Rename Columns
# ============================================================================

kenya_clean <- kenya_raw %>%
  # Rename using our clean names
  rename(all_of(setNames(names(indicators), indicators))) %>%
  
  # Select relevant columns (remove metadata)
  select(
    year, 
    country, 
    iso2c,
    iso3c,
    all_of(indicators)
  ) %>%
  
  # Arrange by year
  arrange(year)

# Verify structure
glimpse(kenya_clean)

# Check data range
message(sprintf("Data ranges from %d to %d", min(kenya_clean$year), max(kenya_clean$year)))

# ============================================================================
# Save Raw Data
# ============================================================================

# Save as CSV
write_csv(
  kenya_clean, 
  "data/raw/worldbank_kenya_indicators.csv"
)

message("Raw data saved to: data/raw/worldbank_kenya_indicators.csv")

# Create a data dictionary
data_dict <- tibble(
  column_name = names(kenya_clean),
  description = c(
    "Year",
    "Country name",
    "ISO 2-character code",
    "ISO 3-character code",
    "GDP in current USD",
    "GDP growth rate (annual %)",
    "Inflation, consumer prices (annual %)",
    "Unemployment, total (% of labor force)",
    "Exports of goods and services (% of GDP)",
    "Imports of goods and services (% of GDP)",
    "Tax revenue (% of GDP)",
    "External debt stocks, total (current USD)",
    "GDP per capita (current USD)",
    "Trade (% of GDP)"
  ),
  data_type = sapply(kenya_clean, class)
)

write_csv(data_dict, "docs/data_dictionary.csv")
message("Data dictionary saved")