"""
dashboard.py
------------
Main Dash application. Assembles all components into a
multi-tab interactive dashboard.
"""

# Anchor sys.path to this file's location so Gunicorn's working directory
# (the repo root on Render) resolves 'src/' correctly regardless of where
# Python is invoked from. sys.path.append("../src") is fragile and breaks
# on every cold start.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go

from data_fetcher import fetch_all_indicators
from data_processor import run_pipeline
from visualizations import (
    plot_gdp_growth,
    plot_inflation_vs_gdp_per_capita,
    plot_debt_gauge,
    plot_trade_balance,
    plot_economic_heatmap,
    plot_kpi_sparkline,
    COLORS,
)

# ── Bootstrap app ─────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap",
    ],
    title="Kenya Economic Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server   # expose Flask server for Gunicorn


# ── Load Data ─────────────────────────────────────────────────────────────────

raw_df = fetch_all_indicators()
df, summary_df = run_pipeline(raw_df)
LATEST_YEAR = int(df.index.max())


# ── KPI Card Component ────────────────────────────────────────────────────────

def kpi_card(title, value, delta, delta_positive, sparkline_fig=None):
    delta_color = COLORS["positive"] if delta_positive else COLORS["negative"]
    delta_icon  = "▲" if delta_positive else "▼"
    card_body   = [
        html.P(title, style={"fontSize": "11px", "color": COLORS["neutral"], "marginBottom": "2px"}),
        html.H4(value, style={"color": COLORS["text"], "marginBottom": "2px", "fontWeight": "700"}),
        html.Span(f"{delta_icon} {delta}",
                  style={"color": delta_color, "fontSize": "12px", "fontWeight": "600"}),
    ]
    if sparkline_fig:
        card_body.append(dcc.Graph(
            figure=sparkline_fig,
            config={"displayModeBar": False},
            style={"height": "60px", "marginTop": "8px"}
        ))
    return dbc.Card(
        dbc.CardBody(card_body),
        style={
            "backgroundColor": COLORS["card_bg"],
            "border":          f"1px solid {COLORS['grid']}",
            "borderRadius":    "10px",
            "padding":         "14px",
        }
    )


# ── KPI Row Builder ───────────────────────────────────────────────────────────

def build_kpi_row(filtered_df: pd.DataFrame) -> dbc.Row:
    """Build the four KPI cards for a given year-filtered DataFrame."""
    latest_year = int(filtered_df.index.max())

    def get_latest_and_delta(col):
        if col not in filtered_df.columns:
            return float("nan"), float("nan")
        series = filtered_df[col].dropna()
        if series.empty:
            return float("nan"), float("nan")
        latest = series.iloc[-1]
        prev   = series.iloc[-2] if len(series) >= 2 else latest
        return latest, latest - prev

    gdp_val, gdp_d = get_latest_and_delta("gdp_growth_pct")
    inf_val, inf_d = get_latest_and_delta("inflation_pct")
    dbt_val, dbt_d = get_latest_and_delta("govt_debt_pct_gdp")
    fin_val, fin_d = get_latest_and_delta("financial_inclusion_pct")

    return dbc.Row([
        dbc.Col(kpi_card(
            f"GDP Growth ({latest_year})", f"{gdp_val:.1f}%",
            f"{abs(gdp_d):.1f}pp YoY", gdp_d >= 0,
            plot_kpi_sparkline(filtered_df["gdp_growth_pct"].dropna(), "", "%", COLORS["positive"])
        ), xs=12, sm=6, lg=3, className="mb-3"),

        dbc.Col(kpi_card(
            f"Inflation ({latest_year})", f"{inf_val:.1f}%",
            f"{abs(inf_d):.1f}pp YoY", inf_d <= 0,   # lower = positive
            plot_kpi_sparkline(filtered_df["inflation_pct"].dropna(), "", "%", COLORS["secondary"])
        ), xs=12, sm=6, lg=3, className="mb-3"),

        dbc.Col(kpi_card(
            f"Govt Debt % GDP ({latest_year})", f"{dbt_val:.1f}%",
            f"{abs(dbt_d):.1f}pp YoY", dbt_d <= 0,   # lower = positive
            plot_kpi_sparkline(filtered_df["govt_debt_pct_gdp"].dropna(), "", "%", COLORS["highlight"])
        ), xs=12, sm=6, lg=3, className="mb-3"),

        dbc.Col(kpi_card(
            f"Financial Inclusion ({latest_year})", f"{fin_val:.1f}%",
            f"{abs(fin_d):.1f}pp YoY", fin_d >= 0,
            # Use COLORS["primary"] (Kenya green) — never COLORS["accent"] (#000000)
            # which is invisible on the dark card background.
            plot_kpi_sparkline(filtered_df["financial_inclusion_pct"].dropna(), "", "%", COLORS["primary"])
        ), xs=12, sm=6, lg=3, className="mb-3"),
    ])


# ── Layout ────────────────────────────────────────────────────────────────────

app.layout = dbc.Container([

    # Header
    dbc.Row([
        dbc.Col([
            html.H2("🇰🇪 Kenya Economic Dashboard",
                    style={"color": COLORS["text"], "fontWeight": "700", "marginBottom": "0"}),
            html.P(f"World Bank Data · 2000–{LATEST_YEAR} · Live via API",
                   style={"color": COLORS["neutral"], "fontSize": "13px"}),
        ], xs=12, md=8),
        dbc.Col([
            dbc.Button("↻ Refresh Data", id="refresh-btn", color="success", size="sm", className="mt-2"),
            html.Span(id="last-updated",
                      style={"color": COLORS["neutral"], "fontSize": "11px", "marginLeft": "10px"}),
        ], xs=12, md=4, className="text-md-end"),
    ], className="py-3 border-bottom border-secondary mb-4"),

    # KPI Row — reactive: updates on year-slider change AND after data refresh
    html.H6("KEY INDICATORS",
            style={"color": COLORS["neutral"], "letterSpacing": "2px",
                   "fontSize": "11px", "marginBottom": "12px"}),
    html.Div(id="kpi-row-container"),  # populated by callback

    # Year Range Slider
    html.Hr(style={"borderColor": COLORS["grid"]}),
    dbc.Row([
        dbc.Col([
            html.Label("Year Range", style={"color": COLORS["neutral"], "fontSize": "12px"}),
            dcc.RangeSlider(
                id="year-slider",
                min=int(df.index.min()),
                max=int(df.index.max()),
                step=1,
                value=[2005, int(df.index.max())],
                marks={
                    y: {"label": str(y),
                        "style": {"color": COLORS["neutral"], "fontSize": "10px"}}
                    for y in range(int(df.index.min()), int(df.index.max()) + 1, 5)
                },
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ], xs=12, md=8),
        dbc.Col([
            html.Label("Show Events", style={"color": COLORS["neutral"], "fontSize": "12px"}),
            dbc.Switch(id="show-events-toggle", value=True, label="Historical Events"),
        ], xs=12, md=4),
    ], className="mb-4"),

    # Tabs
    dbc.Tabs([
        dbc.Tab([
            dbc.Row([
                dbc.Col(dcc.Graph(id="gdp-growth-chart"), xs=12, lg=8),
                dbc.Col(dcc.Graph(id="debt-gauge"),        xs=12, lg=4),
            ], className="mt-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id="inflation-chart"), xs=12),
            ], className="mt-3"),
        ], label="📈 Growth & Stability", tab_id="tab-growth"),

        dbc.Tab([
            dbc.Row([
                dbc.Col(dcc.Graph(id="trade-chart"), xs=12),
            ], className="mt-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id="heatmap-chart",
                                  figure=plot_economic_heatmap(df)), xs=12),
            ], className="mt-3"),
        ], label="🌍 Trade & Correlations", tab_id="tab-trade"),

        dbc.Tab([
            dbc.Row([
                dbc.Col(
                    dbc.Table.from_dataframe(
                        summary_df[["latest","5yr_avg","min","max","trend"]].round(2).reset_index(),
                        striped=True, bordered=False, hover=True, dark=True,
                        style={"fontSize": "12px"}
                    ), xs=12
                )
            ], className="mt-3"),
        ], label="📊 Summary Statistics", tab_id="tab-summary"),
    ], id="main-tabs", active_tab="tab-growth"),

    dcc.Store(id="year-range-store"),

], fluid=True,
   style={"backgroundColor": COLORS["bg"], "minHeight": "100vh", "padding": "0 20px"})


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("kpi-row-container",  "children"),
    Output("gdp-growth-chart",   "figure"),
    Output("inflation-chart",    "figure"),
    Output("trade-chart",        "figure"),
    Output("debt-gauge",         "figure"),
    Input("year-slider",         "value"),
    Input("show-events-toggle",  "value"),
)
def update_charts(year_range, show_events):
    """
    Single callback drives both KPI cards and all charts.
    KPI cards are reactive (not baked into static layout) so they stay
    accurate after a data refresh and when the year slider is moved.
    """
    start, end = year_range
    filtered = df.loc[start:end]
    return (
        build_kpi_row(filtered),
        plot_gdp_growth(filtered, show_events=show_events),
        plot_inflation_vs_gdp_per_capita(filtered),
        plot_trade_balance(filtered),
        plot_debt_gauge(filtered),
    )


@app.callback(
    Output("last-updated", "children"),
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=True
)
def refresh_data(n_clicks):
    """
    Writes fresh data to the on-disk cache.
    The user reloads the page to pick up the new data.
    (Mutating module-level globals is avoided — with a single Gunicorn worker
    it would technically work, but writing to disk is the correct pattern.)
    """
    fetch_all_indicators(force_refresh=True)
    return "Cache refreshed — reload page to see updated data"


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
