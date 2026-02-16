# ============================================================================
# Kenya Economic Dashboard - Data Cleaning
# ============================================================================
# Purpose: Clean and transform raw World Bank data for analysis
# Author: [Your Name]
# Date: [Today's Date]
# ============================================================================

library(tidyverse)
library(lubridate)
library(here)

# Load raw data
kenya_raw <- read_csv("data/raw/worldbank_kenya_indicators.csv")

# Inspect data quality
glimpse(kenya_raw)

# Check for missing values
missing_summary <- kenya_raw %>%
  summarise(across(everything(), ~sum(is.na(.))))

print("Missing values per column:")
print(missing_summary)

# Identify years with complete data
complete_years <- kenya_raw %>%
  filter(complete.cases(.)) %>%
  pull(year)

message(sprintf("Years with complete data: %d to %d", 
                min(complete_years, na.rm = TRUE), 
                max(complete_years, na.rm = TRUE)))

# ============================================================================
# Missing Data Strategy
# ============================================================================

# Calculate missingness percentage
missingness <- kenya_raw %>%
  summarise(across(where(is.numeric), ~mean(is.na(.)) * 100)) %>%
  pivot_longer(everything(), names_to = "variable", values_to = "pct_missing") %>%
  arrange(desc(pct_missing))

print("Missingness by variable:")
print(missingness)

# Strategy:
# - <5% missing: Forward fill or linear interpolation
# - 5-20% missing: Keep but flag in visualizations
# - >20% missing: Consider dropping variable

# Clean data
kenya_clean <- kenya_raw %>%
  # Sort by year
  arrange(year) %>%
  
  # Forward fill (use with caution)
  # Only for small gaps (1-2 years)
  fill(everything(), .direction = "down") %>%
  
  # Filter to years with minimal missing data
  # Keep 2000-2023 (2024 might be incomplete)
  filter(year <= 2023)

# Verify improvement
missing_after <- kenya_clean %>%
  summarise(across(where(is.numeric), ~sum(is.na(.))))

print("Missing values after cleaning:")
print(missing_after)

# ============================================================================
# Feature Engineering
# ============================================================================

kenya_enriched <- kenya_clean %>%
  mutate(
    # ==== Trade Metrics ====
    trade_balance_pct_gdp = exports_pct_gdp - imports_pct_gdp,
    net_importer = ifelse(imports_pct_gdp > exports_pct_gdp, 1, 0),
    
    # ==== Debt Metrics ====
    debt_to_gdp_ratio = (external_debt_usd / gdp_current_usd) * 100,
    
    # ==== Year-over-Year Changes ====
    gdp_change_usd = gdp_current_usd - lag(gdp_current_usd),
    gdp_change_pct = ((gdp_current_usd - lag(gdp_current_usd)) / lag(gdp_current_usd)) * 100,
    
    # ==== Moving Averages (3-year) ====
    inflation_ma3 = zoo::rollmean(inflation_cpi, k = 3, fill = NA, align = "right"),
    gdp_growth_ma3 = zoo::rollmean(gdp_growth_annual, k = 3, fill = NA, align = "right"),
    
    # ==== Economic Periods (for segmentation) ====
    decade = paste0(floor(year / 10) * 10, "s"),
    post_2010 = ifelse(year >= 2010, "2010-2023", "2000-2009"),
    
    # ==== Normalized GDP (Index: 2000 = 100) ====
    gdp_index = (gdp_current_usd / first(gdp_current_usd)) * 100
  )

# Verify new columns
glimpse(kenya_enriched)