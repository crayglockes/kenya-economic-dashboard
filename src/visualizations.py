"""
visualizations.py
-----------------
All Plotly chart factory functions for the dashboard.
Each function returns a go.Figure object.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional

from data_processor import get_event_annotations


# ── Design Tokens ─────────────────────────────────────────────────────────────

COLORS = {
    "primary":   "#006600",   # Kenya green
    "secondary": "#CC0000",   # Kenya red
    "accent":    "#000000",   # Kenya black  (do NOT use for sparklines on dark bg)
    "highlight": "#FFD700",   # Gold
    "positive":  "#2ECC71",
    "negative":  "#E74C3C",
    "neutral":   "#95A5A6",
    "bg":        "#0F1117",
    "card_bg":   "#1A1D27",
    "text":      "#E8E8E8",
    "grid":      "#2A2D3A",
}

FONT = dict(family="Inter, sans-serif", color=COLORS["text"])

BASE_LAYOUT = dict(
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["card_bg"],
    font=FONT,
    margin=dict(l=50, r=30, t=50, b=50),
    xaxis=dict(gridcolor=COLORS["grid"], showgrid=True),
    yaxis=dict(gridcolor=COLORS["grid"], showgrid=True),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    hovermode="x unified",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_base_layout(fig: go.Figure, title: str, annotations=None) -> go.Figure:
    layout_kwargs = {
        **BASE_LAYOUT,
        "title": dict(text=title, font=dict(size=15, color=COLORS["text"]), x=0.02)
    }
    if annotations:
        layout_kwargs["annotations"] = annotations
    fig.update_layout(**layout_kwargs)
    return fig


# ── Chart 1: GDP Growth Bar Chart ────────────────────────────────────────────

def plot_gdp_growth(df: pd.DataFrame, show_events: bool = True) -> go.Figure:
    """Bar chart of annual GDP growth with color coding."""
    series = df["gdp_growth_pct"].dropna()
    colors = [
        COLORS["positive"] if v >= 0 else COLORS["negative"]
        for v in series.values
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=series.index, y=series.values,
        marker_color=colors,
        name="GDP Growth (%)",
        hovertemplate="<b>%{x}</b><br>GDP Growth: %{y:.2f}%<extra></extra>",
    ))

    if "gdp_growth_3yr_avg" in df.columns:
        avg = df["gdp_growth_3yr_avg"].dropna()
        fig.add_trace(go.Scatter(
            x=avg.index, y=avg.values,
            mode="lines",
            line=dict(color=COLORS["highlight"], width=2, dash="dot"),
            name="3-Year Rolling Avg",
        ))

    fig.add_hline(y=0, line_dash="solid", line_color=COLORS["neutral"], line_width=1)
    annotations = get_event_annotations() if show_events else None
    return _apply_base_layout(fig, "Kenya GDP Growth Rate (%) — 2000–2023", annotations)


# ── Chart 2: Inflation vs GDP Per Capita (Dual Axis) ─────────────────────────

def plot_inflation_vs_gdp_per_capita(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=df.index, y=df["inflation_pct"],
        mode="lines+markers", name="Inflation (%)",
        line=dict(color=COLORS["secondary"], width=2), marker=dict(size=5),
        hovertemplate="Inflation: %{y:.1f}%<extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["gdp_per_capita_usd"],
        mode="lines+markers", name="GDP per Capita (USD)",
        line=dict(color=COLORS["primary"], width=2), marker=dict(size=5),
        hovertemplate="GDP/capita: $%{y:,.0f}<extra></extra>",
    ), secondary_y=True)

    fig.update_yaxes(title_text="Inflation (%)", secondary_y=False,
                     gridcolor=COLORS["grid"], color=COLORS["secondary"])
    fig.update_yaxes(title_text="GDP per Capita (USD)", secondary_y=True,
                     gridcolor=COLORS["grid"], color=COLORS["primary"])
    fig.update_xaxes(gridcolor=COLORS["grid"])
    fig.update_layout(
        **{k: v for k, v in BASE_LAYOUT.items() if k not in ["xaxis", "yaxis"]},
        title=dict(text="Inflation vs GDP per Capita — Kenya",
                   font=dict(size=15, color=COLORS["text"]), x=0.02)
    )
    return fig


# ── Chart 3: Debt Sustainability Gauge ───────────────────────────────────────

def plot_debt_gauge(df: pd.DataFrame) -> go.Figure:
    """
    Gauge chart for government debt % GDP.
    Returns an empty-state figure if the column is missing or all-NaN.
    """
    if "govt_debt_pct_gdp" not in df.columns or df["govt_debt_pct_gdp"].dropna().empty:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=COLORS["bg"], font=FONT, height=250,
            annotations=[dict(
                text="Govt Debt data<br>unavailable",
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=14, color=COLORS["neutral"])
            )]
        )
        return fig
    series      = df["govt_debt_pct_gdp"].dropna()
    latest_debt = series.iloc[-1]
    latest_year = series.index[-1]
    prev_debt   = series.iloc[-2] if len(series) >= 2 else latest_debt

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=latest_debt,
        title={"text": f"Gov't Debt % GDP ({latest_year})", "font": {"color": COLORS["text"]}},
        delta={
            "reference":   prev_debt,
            "relative":    False,
            "valueformat": ".1f",
        },
        gauge={
            "axis":        {"range": [0, 100], "tickcolor": COLORS["text"]},
            "bar":         {"color": COLORS["secondary"]},
            "bgcolor":     COLORS["card_bg"],
            "bordercolor": COLORS["grid"],
            "steps": [
                {"range": [0, 40],   "color": "#1A3A1A"},
                {"range": [40, 60],  "color": "#3A2A00"},
                {"range": [60, 100], "color": "#3A0A0A"},
            ],
            "threshold": {
                "line":      {"color": COLORS["highlight"], "width": 3},
                "thickness": 0.75,
                "value":     60,   # IMF benchmark
            },
        },
        number={"suffix": "%", "font": {"color": COLORS["text"]}},
    ))
    fig.update_layout(paper_bgcolor=COLORS["bg"], font=FONT, height=250)
    return fig


# ── Chart 4: Trade Balance Area Chart ────────────────────────────────────────

def plot_trade_balance(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["exports_pct_gdp"], fill=None, mode="lines",
        name="Exports (% GDP)", line=dict(color=COLORS["positive"], width=2),
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["imports_pct_gdp"],
        fill="tonexty", fillcolor="rgba(231, 76, 60, 0.15)",
        mode="lines", name="Imports (% GDP)",
        line=dict(color=COLORS["negative"], width=2),
    ))
    if "trade_balance_pct_gdp" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["trade_balance_pct_gdp"], mode="lines",
            name="Net Trade Balance",
            line=dict(color=COLORS["highlight"], width=1.5, dash="dash"),
        ))
    return _apply_base_layout(fig, "Kenya Trade: Exports vs Imports (% of GDP)")


# ── Chart 5: Correlation Heatmap ─────────────────────────────────────────────

def plot_economic_heatmap(df: pd.DataFrame) -> go.Figure:
    cols = [
        "gdp_growth_pct", "inflation_pct", "unemployment_pct",
        "exports_pct_gdp", "govt_debt_pct_gdp", "financial_inclusion_pct"
    ]
    available = [c for c in cols if c in df.columns]
    corr      = df[available].corr()
    labels    = {
        "gdp_growth_pct":          "GDP Growth",
        "inflation_pct":           "Inflation",
        "unemployment_pct":        "Unemployment",
        "exports_pct_gdp":         "Exports",
        "govt_debt_pct_gdp":       "Govt Debt",
        "financial_inclusion_pct": "Fin. Inclusion",
    }
    tick_labels = [labels.get(c, c) for c in available]

    fig = go.Figure(go.Heatmap(
        z=corr.values, x=tick_labels, y=tick_labels,
        colorscale=[[0, COLORS["negative"]], [0.5, COLORS["bg"]], [1, COLORS["positive"]]],
        zmid=0, text=np.round(corr.values, 2), texttemplate="%{text}",
        hovertemplate="%{x} × %{y}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        **{k: v for k, v in BASE_LAYOUT.items() if k not in ["xaxis", "yaxis", "hovermode"]},
        title=dict(text="Indicator Correlation Matrix",
                   font=dict(size=15, color=COLORS["text"]), x=0.02),
        height=400,
    )
    return fig


# ── Chart 6: KPI Sparklines ───────────────────────────────────────────────────

def plot_kpi_sparkline(
    series: pd.Series,
    title:  str,
    unit:   str = "",
    color:  str = None
) -> go.Figure:
    """
    Minimal sparkline for KPI cards.
    Always pass an explicit color — never use COLORS["accent"] (#000000),
    which is invisible on the dark card background.
    """
    c = color or COLORS["primary"]
    # Convert hex to RGB for rgba fill
    hex_clean = c.lstrip("#")
    r, g, b   = (int(hex_clean[i:i+2], 16) for i in (0, 2, 4))

    fig = go.Figure(go.Scatter(
        x=series.index, y=series.values,
        mode="lines", fill="tozeroy",
        fillcolor=f"rgba({r},{g},{b},0.15)",
        line=dict(color=c, width=1.5),
        hovertemplate=f"%{{x}}: %{{y:.2f}}{unit}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=20, b=0),
        height=80, showlegend=False,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        title=dict(text=title, font=dict(size=10, color=COLORS["neutral"]), x=0),
    )
    return fig
