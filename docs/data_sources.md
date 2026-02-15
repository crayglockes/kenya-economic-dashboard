# Data Sources Documentation

## Primary Sources

### 1. World Bank Data API (WDI)
- **Access**: R package `WDI`
- **Coverage**: 2000-2024
- **Indicators planned**:
  - GDP (current USD): `NY.GDP.MKTP.CD`
  - GDP growth (annual %): `NY.GDP.MKTP.KD.ZG`
  - Inflation, consumer prices: `FP.CPI.TOTL.ZG`
  - Unemployment total: `SL.UEM.TOTL.ZS`
  - Exports of goods/services (% GDP): `NE.EXP.GNFS.ZS`
  - Imports of goods/services (% GDP): `NE.IMP.GNFS.ZS`
  - Tax revenue (% GDP): `GC.TAX.TOTL.GD.ZS`
  - External debt stocks: `DT.DOD.DECT.CD`

- **Status**: ✅ Available via API
- **Notes**: Free, no authentication required

### 2. Kenya National Bureau of Statistics (KNBS)
- **Website**: https://www.knbs.or.ke/download/
- **Planned datasets**:
  - Quarterly GDP by sector
  - Monthly CPI data
  - Labor force surveys
  - Trade statistics

- **Status**: ⏳ To be assessed (requires manual download)
- **Notes**: May need to convert PDF reports to CSV

### 3. Central Bank of Kenya (CBK)
- **Website**: https://www.centralbank.go.ke/statistics/
- **Planned metrics**:
  - Interest rates (CBR)
  - Exchange rates (KES/USD)
  - Money supply aggregates

- **Status**: ⏳ To be assessed
- **Notes**: Likely manual extraction

## Data Quality Considerations

- **Missing data**: World Bank has gaps in certain years
- **Frequency**: Most WB data is annual; KNBS has quarterly
- **Units**: Mix of USD millions, percentages, index (2010=100)
- **Recency**: WB typically lags 1-2 years

## Fallback Plan
If KNBS/CBK data proves difficult on mobile:
- Focus exclusively on World Bank API (sufficient for quality project)
- Supplement with FRED (Federal Reserve Economic Data) for international comparisons
