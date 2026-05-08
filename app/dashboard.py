import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import dash
from dash import dcc, html, Input, Output
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

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap",
    ],
    title="Kenya Economic Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server

raw_df = fetch_all_indicators()
df, summary_df = run_pipeline(raw_df)
LATEST_YEAR = int(df.index.max())


def safe_sparkline(filtered_df, col, unit, color):
    if col not in filtered_df.columns:
        return None
    series = filtered_df[col].dropna()
    if series.empty:
        return None
    return plot_kpi_sparkline(series, "", unit, color)


def kpi_card(title, value, delta, delta_positive, sparkline_fig=None):
    if isinstance(value, float) and math.isnan(value):
        value_str   = "N/A"
        delta_str   = "No data"
        delta_color = COLORS["neutral"]
        delta_icon  = "-"
    else:
        delta_color = COLORS["positive"] if delta_positive else COLORS["negative"]
        delta_icon  = "▲" if delta_positive else "▼"
        value_str   = value
        delta_str   = delta

    card_body = [
        html.P(title, style={"fontSize": "11px", "color": COLORS["neutral"], "marginBottom": "2px"}),
        html.H4(value_str, style={"color": COLORS["text"], "marginBottom": "2px", "fontWeight": "700"}),
        html.Span(f"{delta_icon} {delta_str}", style={"color": delta_color, "fontSize": "12px", "fontWeight": "600"}),
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


def build_kpi_row(filtered_df):
    latest_year = int(filtered_df.index.max())

    def get_val(col):
        if col not in filtered_df.columns:
            return float("nan"), float("nan")
        series = filtered_df[col].dropna()
        if series.empty:
            return float("nan"), float("nan")
        latest = series.iloc[-1]
        prev   = series.iloc[-2] if len(series) >= 2 else latest
        return latest, latest - prev

    def fmt_val(v):
        return "N/A" if (isinstance(v, float) and math.isnan(v)) else f"{v:.1f}%"

    def fmt_delta(d):
        return "No data" if (isinstance(d, float) and math.isnan(d)) else f"{abs(d):.1f}pp YoY"

    def is_good(d, higher_is_good=True):
        if isinstance(d, float) and math.isnan(d):
            return True
        return d >= 0 if higher_is_good else d <= 0

    gdp_val, gdp_d = get_val("gdp_growth_pct")
    inf_val, inf_d = get_val("inflation_pct")
    dbt_val, dbt_d = get_val("govt_debt_pct_gdp")
    fin_val, fin_d = get_val("financial_inclusion_pct")

    return dbc.Row([
        dbc.Col(kpi_card(
            f"GDP Growth ({latest_year})", fmt_val(gdp_val), fmt_delta(gdp_d), is_good(gdp_d, True),
            safe_sparkline(filtered_df, "gdp_growth_pct", "%", COLORS["positive"])
        ), xs=12, sm=6, lg=3, className="mb-3"),

        dbc.Col(kpi_card(
            f"Inflation ({latest_year})", fmt_val(inf_val), fmt_delta(inf_d), is_good(inf_d, False),
            safe_sparkline(filtered_df, "inflation_pct", "%", COLORS["secondary"])
        ), xs=12, sm=6, lg=3, className="mb-3"),

        dbc.Col(kpi_card(
            f"Govt Debt % GDP ({latest_year})", fmt_val(dbt_val), fmt_delta(dbt_d), is_good(dbt_d, False),
            safe_sparkline(filtered_df, "govt_debt_pct_gdp", "%", COLORS["highlight"])
        ), xs=12, sm=6, lg=3, className="mb-3"),

        dbc.Col(kpi_card(
            f"Financial Inclusion ({latest_year})", fmt_val(fin_val), fmt_delta(fin_d), is_good(fin_d, True),
            safe_sparkline(filtered_df, "financial_inclusion_pct", "%", COLORS["primary"])
        ), xs=12, sm=6, lg=3, className="mb-3"),
    ])


app.layout = dbc.Container([

    dbc.Row([
        dbc.Col([
            html.H2("🇰🇪 Kenya Economic Dashboard",
                    style={"color": COLORS["text"], "fontWeight": "700", "marginBottom": "0"}),
            html.P(f"World Bank Data · 2000–{LATEST_YEAR} · Live via API",
                   style={"color": COLORS["neutral"], "fontSize": "13px"}),
        ], xs=12, md=8),
        dbc.Col([
            dbc.Button("↻ Refresh Data", id="refresh-btn", color="success", size="sm", className="mt-2"),
            html.Span(id="last-updated", style={"color": COLORS["neutral"], "fontSize": "11px", "marginLeft": "10px"}),
        ], xs=12, md=4, className="text-md-end"),
    ], className="py-3 border-bottom border-secondary mb-4"),

    html.H6("KEY INDICATORS", style={"color": COLORS["neutral"], "letterSpacing": "2px", "fontSize": "11px", "marginBottom": "12px"}),
    html.Div(id="kpi-row-container"),

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
                    y: {"label": str(y), "style": {"color": COLORS["neutral"], "fontSize": "10px"}}
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
            dbc.Row([dbc.Col(dcc.Graph(id="trade-chart"), xs=12)], className="mt-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id="heatmap-chart", figure=plot_economic_heatmap(df)), xs=12),
            ], className="mt-3"),
        ], label="🌍 Trade & Correlations", tab_id="tab-trade"),

        dbc.Tab([
            dbc.Row([
                dbc.Col(
                    dbc.Table.from_dataframe(
                        summary_df[["latest", "5yr_avg", "min", "max", "trend"]].round(2).reset_index(),
                        striped=True, bordered=False, hover=True, dark=True,
                        style={"fontSize": "12px"}
                    ), xs=12
                )
            ], className="mt-3"),
        ], label="📊 Summary Statistics", tab_id="tab-summary"),
    ], id="main-tabs", active_tab="tab-growth"),

    dcc.Store(id="year-range-store"),

], fluid=True, style={"backgroundColor": COLORS["bg"], "minHeight": "100vh", "padding": "0 20px"})


@app.callback(
    Output("kpi-row-container", "children"),
    Output("gdp-growth-chart",  "figure"),
    Output("inflation-chart",   "figure"),
    Output("trade-chart",       "figure"),
    Output("debt-gauge",        "figure"),
    Input("year-slider",        "value"),
    Input("show-events-toggle", "value"),
)
def update_charts(year_range, show_events):
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
    fetch_all_indicators(force_refresh=True)
    return "Cache refreshed — reload page to see updated data"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
