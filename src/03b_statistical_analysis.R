# ============================================================================
# Statistical Analysis for Key Insights
# ============================================================================

library(tidyverse)

kenya_data <- read_csv("data/processed/kenya_economic_clean.csv")

# ==== ANALYSIS 1: Economic Cycles ====
# Identify recession years
recessions <- kenya_data %>%
  filter(gdp_growth_annual < 0) %>%
  select(year, gdp_growth_annual, inflation_cpi, unemployment_rate)

print("Recession years:")
print(recessions)

# Economic boom years (growth > 6%)
booms <- kenya_data %>%
  filter(gdp_growth_annual > 6) %>%
  select(year, gdp_growth_annual, gdp_current_usd)

print("High growth years (>6%):")
print(booms)

# ==== ANALYSIS 2: Phillips Curve (Inflation-Unemployment) ====
# Test if Kenya follows Phillips Curve relationship

# Filter to years with both inflation and unemployment data
phillips_data <- kenya_data %>%
  filter(!is.na(inflation_cpi), !is.na(unemployment_rate))

if(nrow(phillips_data) > 5) {
  # Run regression
  phillips_model <- lm(inflation_cpi ~ unemployment_rate, data = phillips_data)
  
  print("Phillips Curve Analysis:")
  print(summary(phillips_model))
  
  # Interpretation
  coef <- coef(phillips_model)[2]
  interpretation <- ifelse(coef < 0, 
                           "Negative relationship (supports Phillips Curve)", 
                           "Positive relationship (contradicts Phillips Curve)")
  
  message(interpretation)
  
  # Save model output
  capture.output(summary(phillips_model), file = "outputs/phillips_curve_model.txt")
} else {
  message("Insufficient data for Phillips Curve analysis")
}

# ==== ANALYSIS 3: Trade Dependency Over Time ====
trade_trend <- kenya_data %>%
  mutate(decade = floor(year/10)*10) %>%
  group_by(decade) %>%
  summarise(
    avg_exports = mean(exports_pct_gdp, na.rm = TRUE),
    avg_imports = mean(imports_pct_gdp, na.rm = TRUE),
    avg_trade_balance = mean(trade_balance_pct_gdp, na.rm = TRUE),
    years_in_deficit = sum(trade_balance_pct_gdp < 0, na.rm = TRUE),
    total_years = n()
  )

print("Trade analysis by decade:")
print(trade_trend)

write_csv(trade_trend, "outputs/trade_analysis_by_decade.csv")

# ==== ANALYSIS 4: Debt Sustainability ====
debt_analysis <- kenya_data %>%
  select(year, debt_to_gdp_ratio, gdp_growth_annual) %>%
  mutate(
    debt_category = case_when(
      debt_to_gdp_ratio < 40 ~ "Low Risk (<40%)",
      debt_to_gdp_ratio < 60 ~ "Moderate Risk (40-60%)",
      TRUE ~ "High Risk (>60%)"
    )
  )

debt_summary <- debt_analysis %>%
  group_by(debt_category) %>%
  summarise(
    years = n(),
    avg_gdp_growth = mean(gdp_growth_annual, na.rm = TRUE)
  )

print("Debt sustainability analysis:")
print(debt_summary)

write_csv(debt_analysis, "outputs/debt_sustainability_analysis.csv")

# ==== ANALYSIS 5: GDP per Capita Growth ====
gdp_per_capita_growth <- kenya_data %>%
  mutate(
    gdp_pc_change = ((gdp_per_capita - lag(gdp_per_capita)) / lag(gdp_per_capita)) * 100
  ) %>%
  summarise(
    first_year = first(year),
    last_year = last(year),
    first_gdp_pc = first(gdp_per_capita),
    last_gdp_pc = last(gdp_per_capita),
    total_growth_pct = ((last_gdp_pc - first_gdp_pc) / first_gdp_pc) * 100,
    avg_annual_growth = mean(gdp_pc_change, na.rm = TRUE)
  )

print("GDP per capita growth:")
print(gdp_per_capita_growth)

# Save all analysis results
analysis_results <- list(
  recessions = recessions,
  booms = booms,
  trade_trend = trade_trend,
  debt_summary = debt_summary,
  gdp_per_capita_growth = gdp_per_capita_growth
)

saveRDS(analysis_results, "outputs/statistical_analysis_results.rds")
message("✓ Statistical analysis complete")