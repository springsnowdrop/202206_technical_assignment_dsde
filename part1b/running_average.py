"""365-day running average of PM2.5 in Kolkata and Lucknow, from the CPCB station exports
collected by ScrapeCPCB.py (one .xlsx file of daily PM2.5 per station in part1b/data/).

1. Daily city value = mean of the stations that reported that day (missing days are ignored,
   not counted as zeros).
2. 365-day running average = trailing mean over the 365 days ending on the plotted date,
   only shown when the whole window is within the data period and at least MIN_COVERAGE of
   its days have data.

Outputs (part1b/results/):
  pm25_daily.csv            daily PM2.5 per station
  pm25_city.csv             daily city average, number of stations, 365-day running average
  pm25_running_average.html interactive chart (+ .png if Chrome is available for kaleido)

Usage:  python part1b/running_average.py
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent
WINDOW_DAYS = 365
MIN_COVERAGE = 0.75
COLORS = {"Kolkata": "#2a78d6", "Lucknow": "#eb6834"}
INK, INK_2, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def read_station(path: Path) -> pd.DataFrame:
    """Parse one CPCB export: a metadata header, then a 'From Date / To Date / PM2.5' table."""
    raw = pd.read_excel(path, header=None)
    meta = dict(zip(raw[0].astype(str).str.strip(), raw[1]))
    header = raw.index[raw[0] == "From Date"][0]
    df = raw.iloc[header + 1:, [0, 2]].set_axis(["date", "pm25"], axis=1)
    return pd.DataFrame({
        "city": meta["City"],
        "station": meta["Station"],
        "date": pd.to_datetime(df["date"], format="%d-%m-%Y %H:%M").dt.normalize(),
        "pm25": pd.to_numeric(df["pm25"], errors="coerce"),  # 'None' -> NaN
    })


def city_running_average(daily: pd.DataFrame) -> pd.DataFrame:
    city = (daily.dropna(subset=["pm25"])
            .groupby(["city", "date"])["pm25"].agg(pm25="mean", n_stations="count")
            .reset_index())
    out = []
    for name, d in city.groupby("city"):
        # reindex on a full calendar so that days without any station count as missing
        d = d.set_index("date").reindex(pd.date_range(daily["date"].min(), daily["date"].max()))
        d["city"] = name
        d["n_stations"] = d["n_stations"].fillna(0).astype(int)
        d["pm25_365d"] = d["pm25"].rolling(WINDOW_DAYS, min_periods=int(MIN_COVERAGE * WINDOW_DAYS)).mean()
        # windows reaching back before the first day would miss part of the seasonal cycle
        d.iloc[:WINDOW_DAYS - 1, d.columns.get_loc("pm25_365d")] = float("nan")
        out.append(d.rename_axis("date").reset_index())
    return pd.concat(out)[["city", "date", "n_stations", "pm25", "pm25_365d"]]


def make_figure(city: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for name, d in city.groupby("city"):
        fig.add_scatter(
            x=d["date"], y=d["pm25"], name=f"{name} - daily", mode="lines", visible="legendonly",
            line=dict(color=COLORS[name], width=1), opacity=0.35, legendgroup=name,
            hovertemplate=f"{name} daily: %{{y:.0f}} µg/m³<extra></extra>",
        )
    for name, d in city.groupby("city"):
        d = d.dropna(subset=["pm25_365d"])
        fig.add_scatter(
            x=d["date"], y=d["pm25_365d"], name=f"{name} - 365-day average", mode="lines",
            line=dict(color=COLORS[name], width=2.5), legendgroup=name,
            customdata=d[["n_stations"]],
            hovertemplate=(f"<b>{name}</b> %{{y:.1f}} µg/m³"
                           "<br>(365 days ending %{x|%d %b %Y}; %{customdata[0]} stations that day)<extra></extra>"),
        )
        last = d.iloc[-1]
        fig.add_annotation(x=last["date"], y=last["pm25_365d"], text=f"<b>{name}</b> {last['pm25_365d']:.0f}",
                           xanchor="left", showarrow=False, xshift=6, font=dict(color=INK, size=13))
    first = city.dropna(subset=["pm25_365d"])["date"].min()
    fig.update_xaxes(range=[first - pd.Timedelta(days=10), city["date"].max() + pd.Timedelta(days=60)],
                     gridcolor=GRID, linecolor=AXIS, tickfont_color=INK_2, rangeslider=dict(visible=True))
    fig.update_yaxes(title_text="PM2.5 (µg/m³)", rangemode="tozero", gridcolor=GRID, zeroline=False,
                     linecolor=AXIS, tickfont_color=INK_2)
    fig.update_layout(
        title=dict(text="PM2.5 in Kolkata and Lucknow: 365-day running average of the stations' daily mean"
                        f"<br><span style='font-size:13px;color:{INK_2}'>Source: CPCB CAAQM portal, "
                        "6 stations per city · each point averages the 365 days ending on that date"
                        "<br>(shown when ≥75% of days have data) · click the legend to show daily values</span>",
                   x=0.01, font=dict(size=18, color=INK)),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK_2),
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, hovermode="x unified",
        width=1100, height=580, margin=dict(l=70, r=30, t=120, b=40),
        legend=dict(x=0.01, y=0.03, xanchor="left", yanchor="bottom", bgcolor="rgba(252,252,251,0.85)"),
    )
    return fig


def main():
    daily = pd.concat(read_station(f) for f in sorted((ROOT / "data").glob("*.xlsx")))
    print(daily.groupby("city")["station"].nunique().to_string())
    city = city_running_average(daily)

    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    daily.to_csv(results / "pm25_daily.csv", index=False)
    city.to_csv(results / "pm25_city.csv", index=False)
    fig = make_figure(city)
    fig.write_html(results / "pm25_running_average.html", include_plotlyjs="cdn")
    try:
        fig.update_xaxes(rangeslider_visible=False).write_image(results / "pm25_running_average.png", scale=2)
    except Exception as e:  # kaleido needs a Chrome install
        print(f"PNG not written: {e}")
    print(city.dropna(subset=["pm25_365d"]).groupby("city").agg(
        first=("date", "min"), last=("date", "max"),
        min_365d=("pm25_365d", "min"), max_365d=("pm25_365d", "max")).to_string())


if __name__ == "__main__":
    main()
