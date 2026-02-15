library(WDI)
library(tidyverse)

# Test basic API call
test_data <- WDI(
  country = "KE",
  indicator = "NY.GDP.MKTP.CD",
  start = 2010,
  end = 2023
)

print(test_data)

# Verify data structure
str(test_data)

# Check for missing values
summary(test_data)

# Quick plot
ggplot(test_data, aes(x = year, y = NY.GDP.MKTP.CD)) +
  geom_line() +
  labs(
    title = "Kenya GDP (Current USD)",
    x = "Year",
    y = "GDP (USD)"
  )

# Find all available indicators
indicators <- WDIsearch("kenya", cache = NULL)

# View economic indicators
econ_indicators <- WDIsearch("gdp|inflation|unemployment|trade", cache = NULL)

# Save for reference
write_csv(as.data.frame(econ_indicators), "docs/available_indicators.csv")