# ============================================================================
# Kenya Economic Dashboard - Exploratory Analysis
# ============================================================================
# Purpose: Generate initial insights and visualizations
# Author: [Your Name]
# Date: [Today's Date]
# ============================================================================

library(tidyverse)
library(plotly)
library(scales)

# Load cleaned data
kenya_data <- kenya_enriched

# Summary statistics
summary_stats <- kenya_data %>%
  select(
    year,
    gdp_current_usd,
    gdp_growth_annual,
    inflation_cpi,
    unemployment_rate,
    trade_balance_pct_gdp,
    debt_to_gdp_ratio
  ) %>%
  summary()

# Save summary
capture.output(summary_stats, file = "outputs/summary_statistics.txt")

# Key metrics by decade
decade_summary <- kenya_data %>%
  group_by(decade) %>%
  summarise(
    avg_gdp_growth = mean(gdp_growth_annual, na.rm = TRUE),
    avg_inflation = mean(inflation_cpi, na.rm = TRUE),
    avg_trade_balance = mean(trade_balance_pct_gdp, na.rm = TRUE),
    years = n()
  )

print("Economic performance by decade:")
print(decade_summary)

write_csv(decade_summary, "outputs/decade_summary.csv")

# GDP Growth Over Time
p1 <- ggplot(kenya_data, aes(x = year, y = gdp_current_usd / 1e9)) +  # Convert to billions
  geom_line(color = "#006600", size = 1.2) +
  geom_point(color = "#006600", size = 2) +
  scale_y_continuous(labels = scales::dollar_format(suffix = "B")) +
  labs(
    title = "Kenya GDP Growth (2000-2023)",
    subtitle = "Steady expansion from $14B to $113B",
    x = "Year",
    y = "GDP (Current USD)",
    caption = "Source: World Bank WDI"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(face = "bold", size = 14),
    plot.subtitle = element_text(size = 10, color = "gray30")
  )

# Save
ggsave("outputs/figures/01_gdp_trend.png", p1, width = 10, height = 6, dpi = 300)
message("✓ GDP trend plot saved")

# GDP Growth Rate with Recessions Highlighted
p2 <- ggplot(kenya_data, aes(x = year, y = gdp_growth_annual)) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "red", alpha = 0.5) +
  geom_line(color = "#0066CC", size = 1) +
  geom_point(aes(color = gdp_growth_annual > 0), size = 2.5) +
  scale_color_manual(values = c("TRUE" = "#006600", "FALSE" = "#CC0000")) +
  labs(
    title = "Kenya GDP Growth Rate (2000-2023)",
    subtitle = "Annual % change - Negative growth in COVID-19 period",
    x = "Year",
    y = "GDP Growth (%)",
    caption = "Source: World Bank WDI"
  ) +
  theme_minimal() +
  theme(legend.position = "none")

ggsave("outputs/figures/02_gdp_growth_rate.png", p2, width = 10, height = 6, dpi = 300)
message("✓ GDP growth rate plot saved")

# Inflation with Moving Average
p3 <- ggplot(kenya_data, aes(x = year)) +
  geom_line(aes(y = inflation_cpi), color = "gray60", size = 0.8) +
  geom_line(aes(y = inflation_ma3), color = "#FF6600", size = 1.2) +
  geom_point(aes(y = inflation_cpi), color = "gray40", size = 1.5, alpha = 0.6) +
  labs(
    title = "Kenya Inflation Rate (2000-2023)",
    subtitle = "Consumer prices (annual %) with 3-year moving average",
    x = "Year",
    y = "Inflation (%)",
    caption = "Source: World Bank WDI | Orange line = 3-year MA"
  ) +
  theme_minimal()

ggsave("outputs/figures/03_inflation_trend.png", p3, width = 10, height = 6, dpi = 300)
message("✓ Inflation plot saved")

# Trade Balance
p4 <- ggplot(kenya_data, aes(x = year, y = trade_balance_pct_gdp)) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray50") +
  geom_area(aes(fill = trade_balance_pct_gdp > 0), alpha = 0.3) +
  geom_line(size = 1) +
  scale_fill_manual(values = c("TRUE" = "#006600", "FALSE" = "#CC0000")) +
  labs(
    title = "Kenya Trade Balance (2000-2023)",
    subtitle = "Net exports as % of GDP - Persistent deficit",
    x = "Year",
    y = "Trade Balance (% of GDP)",
    caption = "Source: World Bank WDI | Negative = Trade Deficit"
  ) +
  theme_minimal() +
  theme(legend.position = "none")

ggsave("outputs/figures/04_trade_balance.png", p4, width = 10, height = 6, dpi = 300)
message("✓ Trade balance plot saved")

# Correlation Matrix
cor_data <- kenya_data %>%
  select(
    gdp_growth_annual,
    inflation_cpi,
    unemployment_rate,
    exports_pct_gdp,
    imports_pct_gdp,
    debt_to_gdp_ratio
  ) %>%
  na.omit()

cor_matrix <- cor(cor_data)

# Save
write_csv(as.data.frame(cor_matrix), "outputs/correlation_matrix.csv")

# Correlation heatmap
library(reshape2)
cor_long <- melt(cor_matrix)

p5 <- ggplot(cor_long, aes(x = Var1, y = Var2, fill = value)) +
  geom_tile() +
  geom_text(aes(label = round(value, 2)), size = 3) +
  scale_fill_gradient2(low = "#CC0000", mid = "white", high = "#006600", midpoint = 0) +
  labs(
    title = "Correlation Matrix: Kenya Economic Indicators",
    x = "",
    y = ""
  ) +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

ggsave("outputs/figures/05_correlation_heatmap.png", p5, width = 10, height = 8, dpi = 300)
message("✓ Correlation heatmap saved")

# Save the fully processed dataset
write_csv(kenya_enriched, "data/processed/kenya_economic_clean.csv")
message("✓ Processed data saved")

# Create a processing log
processing_log <- tibble(
  step = c("Data collection", "Data cleaning", "Feature engineering", "EDA"),
  date = Sys.Date(),
  status = "Complete",
  notes = c(
    sprintf("%d indicators from World Bank", length(indicators)),
    sprintf("%d years of data", nrow(kenya_clean)),
    sprintf("%d derived variables created", ncol(kenya_enriched) - ncol(kenya_clean)),
    sprintf("%d visualizations created", 5)
  )
)

write_csv(processing_log, "outputs/processing_log.csv")