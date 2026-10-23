"""Chart of the share of population living within 5, 10, 50 km (and beyond) of a monitoring
station, from the outputs of coverage.py.

Left:  100% stacked bar per country, one segment per distance band.
Right: cumulative share of population vs distance to the nearest station.

Writes part1a/results/coverage.html (interactive) and coverage.png (static; needs Chrome
for plotly/kaleido - set BROWSER_PATH if it is not found).

Usage:  python part1a/plot.py [--suffix _xyz] [--subtitle "..."]
"""
import argparse

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from common import COUNTRIES, RADII_KM, RESULTS

# Ordinal blue ramp for distance bands: nearest = darkest
BAND_COLORS = ["#104281", "#256abf", "#5598e7", "#86b6ef"]
BAND_TEXT = ["#ffffff", "#ffffff", "#0b0b0b", "#0b0b0b"]
# Categorical slots, fixed order (one per country, in COUNTRIES order)
COUNTRY_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def make_figure(bands: pd.DataFrame, cumulative: pd.DataFrame, subtitle: str, flag=()) -> go.Figure:
    band_labels = list(dict.fromkeys(bands["band"]))
    share = bands.pivot(index="country", columns="band", values="share")[band_labels]
    n_stations = bands.groupby("country")["n_stations"].first()
    # Best covered (within 10 km) at the top
    order = share[band_labels[:2]].sum(axis=1).sort_values().index.tolist()
    ylabels = [f"{c}{'*' if c in flag else ''}  <span style='color:{MUTED}'>({n_stations[c]:,} st.)</span>"
               for c in order]

    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.52, 0.48], horizontal_spacing=0.09,
        subplot_titles=["Population by distance to the nearest station",
                        "Cumulative share of population within distance"],
    )
    for label, color, text_color in zip(band_labels, BAND_COLORS, BAND_TEXT):
        values = share.loc[order, label]
        fig.add_bar(
            y=ylabels, x=values, name=label, orientation="h", legend="legend",
            marker=dict(color=color, line=dict(color=SURFACE, width=2)),
            text=[f"{v:.0%}" if v >= 0.045 else "" for v in values],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(color=text_color, size=12),
            customdata=[[c, v] for c, v in zip(order, values)],
            hovertemplate="<b>%{customdata[0]}</b><br>" + label + ": %{customdata[1]:.1%}<extra></extra>",
            row=1, col=1,
        )

    for (iso2, name), color in zip(COUNTRIES.items(), COUNTRY_COLORS):
        d = cumulative[cumulative["iso2"] == iso2]
        fig.add_scatter(
            x=d["distance_km"], y=d["share_within"], name=name, mode="lines", legend="legend2",
            line=dict(color=color, width=2),
            hovertemplate=f"<b>{name}</b><br>%{{y:.1%}} within %{{x}} km<extra></extra>",
            row=1, col=2,
        )
    for r in RADII_KM:
        fig.add_vline(x=r, line=dict(color=AXIS, width=1, dash="dot"), row=1, col=2)

    fig.update_xaxes(tickformat=".0%", range=[0, 1], dtick=0.25, row=1, col=1)
    fig.update_xaxes(type="log", range=[-0.3, 2.3], tickvals=[1, 2, 5, 10, 20, 50, 100, 200],
                     title_text="Distance to nearest station (km, log scale)", row=1, col=2)
    fig.update_yaxes(tickformat=".0%", range=[0, 1.01], dtick=0.25, row=1, col=2)
    fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False, linecolor=AXIS, tickfont_color=INK_2)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=AXIS, tickfont_color=INK_2)
    fig.update_yaxes(showgrid=False, row=1, col=1)
    fig.update_annotations(font=dict(size=14, color=INK), xanchor="left", x=None)
    for ann, dom in zip(fig.layout.annotations, [fig.layout.xaxis.domain, fig.layout.xaxis2.domain]):
        ann.x = dom[0]

    fig.update_layout(
        title=dict(text="Share of population living near an air quality monitoring station"
                        f"<br><span style='font-size:13px;color:{INK_2}'>{subtitle}</span>",
                   x=0.01, y=1, yref="container", yanchor="top", pad=dict(t=22),
                   font=dict(size=19, color=INK)),
        barmode="stack", bargap=0.35, hovermode="closest",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK_2),
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
        width=1200, height=600, margin=dict(l=20, r=20, t=165, b=60),
        legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", xanchor="left",
                    title_text="Distance: ", traceorder="normal"),
        legend2=dict(x=fig.layout.xaxis2.domain[0] + 0.01, y=1.0, xanchor="left", yanchor="top",
                     bgcolor="rgba(252,252,251,0.85)"),
    )
    # Subplot titles sit above the band legend
    for ann in fig.layout.annotations:
        ann.y = 1.09
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suffix", default="")
    parser.add_argument("--subtitle", default=(
        "Stations: OpenAQ archive, monitors reporting ≥30 days in a year 2022-2025, low-cost sensors excluded"
        " · Population: GPWv4 2020<br>* Philippines: PM2.5-only sites, almost all in Metro Manila and"
        " probably indicative sensors - no regulatory network found in OpenAQ"))
    parser.add_argument("--flag", nargs="*", default=["Philippines"], help="countries to mark with *")
    args = parser.parse_args()

    bands = pd.read_csv(RESULTS / f"coverage{args.suffix}.csv")
    cumulative = pd.read_csv(RESULTS / f"coverage_cumulative{args.suffix}.csv")
    fig = make_figure(bands, cumulative, args.subtitle, args.flag)
    fig.write_html(RESULTS / f"coverage{args.suffix}.html", include_plotlyjs="cdn")
    fig.write_image(RESULTS / f"coverage{args.suffix}.png", scale=2)
    print(f"written {RESULTS / f'coverage{args.suffix}'}.html / .png")


if __name__ == "__main__":
    main()
