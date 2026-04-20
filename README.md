# 🇰🇪 Kenya Economic Indicators Dashboard

> An interactive macroeconomic dashboard tracking Kenya's key economic
> indicators from 2000–2023, built with Python, Dash, and the World Bank API.

**[🚀 Live Demo →](https://kenya-economic-dashboard.onrender.com)**

## Overview

This dashboard provides data-driven insights into Kenya's economic trajectory
through 6 interactive visualizations covering growth, inflation, trade, debt
sustainability, and financial inclusion.

## Key Features

- **14 World Bank indicators** auto-fetched and cached (24h TTL)
- **Bundled fallback dataset** committed to repo — app loads even if API is down
- **Interactive year-range filtering** across all charts and KPI cards simultaneously
- **Historical event overlay** — maps economic shocks (2007 violence, 2020 COVID) to data
- **Debt sustainability gauge** with IMF 60% benchmark marker
- **Correlation heatmap** for multivariate economic cycle analysis
- **Mobile-responsive** layout via Bootstrap grid

## Tech Stack

| Layer | Technology |
|---|---|
| Data | World Bank API (`wbgapi`) |
| Processing | Pandas, NumPy |
| Visualization | Plotly, Dash |
| UI Framework | Dash Bootstrap Components |
| Deployment | Render (Gunicorn, single worker) |
| Testing | Pytest (16 unit tests) |

## Methodology

**Data sourcing:** World Bank Open Data API (free, no key required)
**Gap handling:** Linear interpolation (≤ 2 yr internal gaps), ffill (trailing), bfill (leading)
**Derived metrics:** Trade balance, debt-to-revenue ratio, 3-year rolling GDP average

## Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/kenya-economic-dashboard
cd kenya-economic-dashboard
pip install -r requirements.txt
python app/dashboard.py
# Open http://localhost:8050
```

## Skills Demonstrated

`Data Engineering` `API Integration` `Time-Series Analysis` `Dashboard Design`
`Python` `Pandas` `Plotly Dash` `Statistical Visualization` `DevOps`

## Data Source

World Bank Open Data — [data.worldbank.org](https://data.worldbank.org)
All data is public domain and freely redistributable.
